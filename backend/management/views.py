from datetime import timedelta
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import TeamPermission
from common.periods import period_from_params

from . import audit, export
from .models import AuditLog, ExpenseCategory, LedgerEntry, MonthlyFinance, OtherExpense
from .rules import CONFIRMED, INTENT_ABILITY, NEW, entry_abilities, month_state
from .serializers import VALUE_FIELDS, MonthlySaveSerializer, UnconfirmSerializer

CONFLICT_MESSAGE = "다른 사람이 먼저 저장했습니다. 새로고침 후 다시 입력하세요."


class Conflict(APIException):
    """동시 수정: 화면을 불러온 뒤 다른 사람이 먼저 저장함 (HTTP 409)"""

    status_code = 409
    default_detail = CONFLICT_MESSAGE


class ManagementApiView(APIView):
    """경영지원팀 API 공통: 조회는 경영지원팀 열람 권한, 입력은 수정 권한 (= 대표·관리자·경영지원팀 소속)"""

    team = "management"
    permission_classes = [TeamPermission]


def _check_year_month(year, month):
    if not 2000 <= year <= 2100:
        raise ValidationError({"year": "year는 2000~2100 사이여야 합니다."})
    if not 1 <= month <= 12:
        raise ValidationError({"month": "month는 1~12 사이여야 합니다."})


def _previous(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _get_finance(year, month, lock=False):
    qs = MonthlyFinance.objects.filter(year=year, month=month)
    if lock:
        qs = qs.select_for_update()  # 확인과 저장 사이에 다른 저장이 끼어들지 못하게 그 줄을 잠근다
    return qs.prefetch_related("other_expenses").first()


def _values(finance):
    return {f: getattr(finance, f) if finance else 0 for f in VALUE_FIELDS}


def _other_amounts(finance):
    return {e.category_id: e.amount for e in finance.other_expenses.all()} if finance else {}


def _visible_categories(finance):
    """입력 화면에 보일 "그 외 지출" 항목: 사용 중인 항목 + 이 달에 금액이 있는 비활성 항목"""
    used_here = {cid for cid, amount in _other_amounts(finance).items() if amount}
    return [c for c in ExpenseCategory.objects.all() if c.is_active or c.id in used_here]


def _status(finance):
    return finance.status if finance else NEW


def _abilities(user, finance, year, month):
    return entry_abilities(user, _status(finance), month_state(year, month, timezone.localdate()))


def _check_not_changed(finance, expected):
    """동시 수정 확인: 화면을 불러올 때의 수정 시각(expected)과 지금이 다르면 409"""
    current = finance.updated_at if finance else None
    if current != expected:
        raise Conflict()


def monthly_payload(user, year, month):
    finance = _get_finance(year, month)
    amounts = _other_amounts(finance)
    prev = _get_finance(*_previous(year, month))
    return {
        "year": year,
        "month": month,
        "status": _status(finance),
        "month_state": month_state(year, month, timezone.localdate()),
        "abilities": _abilities(user, finance, year, month),
        "values": _values(finance),
        "cash_balance": finance.cash_balance if finance else None,
        "other_expenses": [
            {"category_id": c.id, "name": c.name, "is_active": c.is_active, "amount": amounts.get(c.id, 0)}
            for c in _visible_categories(finance)
        ],
        # 자릿수 실수 확인용 전월 값 (전월 데이터가 없으면 null)
        "previous": (
            {"values": _values(prev), "other_expenses": {str(k): v for k, v in _other_amounts(prev).items()}}
            if prev
            else None
        ),
        "confirmed_at": finance.confirmed_at if finance else None,
        # 저장할 때 그대로 돌려보낸다 (동시 수정 확인)
        "updated_at": finance.updated_at if finance else None,
        "updated_by": _name(finance.updated_by) if finance and finance.updated_by else None,
    }


def _name(user):
    return f"{user.last_name}{user.first_name}" or user.username


class MonthlyFinanceView(ManagementApiView):
    """GET/PUT /api/management/monthly/{year}/{month}/ — 월별 실적 조회·임시저장·확정"""

    def get(self, request, year, month):
        _check_year_month(year, month)
        return Response(monthly_payload(request.user, year, month))

    def put(self, request, year, month):
        _check_year_month(year, month)
        serializer = MonthlySaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        intent = data["intent"]

        try:
            with transaction.atomic():
                finance = _get_finance(year, month, lock=True)
                abilities = _abilities(request.user, finance, year, month)
                if not abilities[INTENT_ABILITY[intent]]:
                    raise PermissionDenied(abilities["notice"] or "이 작업을 할 권한이 없습니다.")
                _check_not_changed(finance, data["expected_updated_at"])

                # 그 외 지출 항목: 있는 항목만, 비활성 항목은 이 달에 이미 금액이 있을 때만
                allowed = {c.id: c.name for c in _visible_categories(finance)}
                if any(e["category_id"] not in allowed for e in data["other_expenses"]):
                    raise ValidationError({"other_expenses": "사용할 수 없는 지출 항목이 있습니다. 새로고침 후 다시 입력하세요."})

                before = audit.monthly_snapshot(finance)
                if finance is None:
                    finance = MonthlyFinance(year=year, month=month, created_by=request.user)
                for field, value in data["values"].items():
                    setattr(finance, field, value)
                finance.cash_balance = data["cash_balance"]
                finance.status = MonthlyFinance.Status.DRAFT if intent == "draft" else MonthlyFinance.Status.CONFIRMED
                if intent == "confirm":
                    finance.confirmed_at = timezone.now()
                elif intent == "draft":
                    finance.confirmed_at = None
                finance.updated_by = request.user
                finance.save()
                for e in data["other_expenses"]:
                    OtherExpense.objects.update_or_create(
                        monthly=finance, category_id=e["category_id"], defaults={"amount": e["amount"]}
                    )

                # 확정·확정 후 수정만 기록 (임시저장은 기록하지 않음 — 조원 저장소 2026-10-25 결정)
                if intent != "draft":
                    after = {
                        "status": finance.status,
                        "values": dict(data["values"]),
                        "others": {**(before["others"] if before else {}), **{e["category_id"]: e["amount"] for e in data["other_expenses"]}},
                        "cash_balance": data["cash_balance"],
                    }
                    names = {c.id: c.name for c in ExpenseCategory.objects.all()}
                    audit.record_audit(
                        actor=request.user,
                        screen="entry",
                        action="CONFIRM" if intent == "confirm" else "UPDATE_CONFIRMED",
                        target_type="MonthlyFinance",
                        target_id=finance.pk,
                        target_label=audit.monthly_label(year, month),
                        changes=audit.monthly_changes(before, after, names),
                    )
        except IntegrityError:
            # 새 달을 두 사람이 동시에 만들면 (연·월 하나에 한 줄 규칙 위반) → 동시 수정으로 안내
            raise Conflict()

        label = f"{year}년 {month}월"
        message = {
            "draft": f"{label} 임시저장했습니다.",
            "confirm": f"{label} 확정했습니다. 대시보드에 반영됩니다.",
            "update_confirmed": f"{label} 확정된 데이터를 수정했습니다.",
        }[intent]
        return Response({**monthly_payload(request.user, year, month), "message": message})


class MonthlyUnconfirmView(ManagementApiView):
    """POST /api/management/monthly/{year}/{month}/unconfirm/ — 확정 취소 (확정 → 임시저장)"""

    def post(self, request, year, month):
        _check_year_month(year, month)
        serializer = UnconfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            finance = _get_finance(year, month, lock=True)
            if finance is None or finance.status != CONFIRMED:
                raise ValidationError({"detail": "확정된 데이터가 없습니다."})
            abilities = entry_abilities(request.user, CONFIRMED, month_state(year, month, timezone.localdate()))
            if not abilities["can_unconfirm"]:
                raise PermissionDenied(abilities["notice"] or "확정을 취소할 권한이 없습니다.")
            _check_not_changed(finance, serializer.validated_data["expected_updated_at"])
            finance.status = MonthlyFinance.Status.DRAFT
            finance.confirmed_at = None
            finance.updated_by = request.user
            finance.save()
            audit.record_audit(
                actor=request.user,
                screen="entry",
                action="UNCONFIRM",
                target_type="MonthlyFinance",
                target_id=finance.pk,
                target_label=audit.monthly_label(year, month),
                changes=[{"field": "status", "label": "상태", "before": "확정", "after": "임시저장"}],
            )
        return Response(
            {
                **monthly_payload(request.user, year, month),
                "message": f"{year}년 {month}월 확정을 취소했습니다. 임시저장 상태로 바뀌었고 대시보드 집계에서 빠집니다.",
            }
        )


class MonthlyLedgerView(ManagementApiView):
    """GET /api/management/monthly/{year}/{month}/ledger/ — [경영지원 관리에서 불러오기]용 그 달 장부 행

    외상매입금·미지급비용(직원·업체)만, 숨긴 행 제외. 읽기만 하고 저장하지 않는다 (채우기·저장은 화면에서 사람이)
    """

    def get(self, request, year, month):
        _check_year_month(year, month)
        abilities = _abilities(request.user, _get_finance(year, month), year, month)
        if abilities["read_only"]:
            raise PermissionDenied(abilities["notice"] or "이 달을 입력할 권한이 없습니다.")
        rows = LedgerEntry.objects.filter(year=year, month=month, deleted_at__isnull=True).exclude(kind=LedgerEntry.Kind.AR)
        return Response(
            {
                "rows": [
                    {
                        "kind": r.kind,
                        "amount": r.amount,
                        "purchase_type": r.purchase_type or None,
                        "expense_type": r.expense_type or None,
                        "auto_transfer": r.auto_transfer,
                    }
                    for r in rows
                ],
                "expense_type_labels": dict(LedgerEntry.ExpenseType.choices),
            }
        )


class MonthlyExportView(ManagementApiView):
    """GET /api/management/monthly/export/?year=&period=month|quarter|year&month=&quarter= — 월간 입력 엑셀 내려받기

    저장된 값으로 만든다. 합계 시트는 확정된 달만 더한다. 내려받은 사실을 변경 기록에 남긴다.
    """

    def get(self, request):
        period = period_from_params(request.query_params)
        sheets = export.plan_sheets(period)
        if not sheets:
            raise ValidationError({"detail": "아직 시작하지 않은 기간은 내려받을 수 없습니다."})
        name = export.file_name(period)
        content = export.build_workbook(sheets)
        audit.record_audit(
            actor=request.user,
            screen="entry-export",
            action="EXPORT",
            target_type="MonthlyFinance",
            target_id=name,
            target_label=f"{period.label} 월간 입력",
            meta={"period": period.label, "sheet_count": len(sheets), "file_name": name},
        )
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f"attachment; filename=\"entry.xlsx\"; filename*=UTF-8''{quote(name)}"
        return response


HISTORY_PAGE_SIZE = 50
HISTORY_DEFAULT_DAYS = 30


class HistoryView(ManagementApiView):
    """GET /api/management/history/?from=&to=&actor=&screen=&action=&q=&page= — 변경 이력 (최근 기록부터)

    기간 기본값 = 오늘 포함 최근 30일. 틀린 값은 버리고 기본값을 쓴다.
    """

    def get(self, request):
        p = request.query_params
        today = timezone.localdate()
        to = parse_date(p.get("to") or "") or today
        start = parse_date(p.get("from") or "") or today - timedelta(days=HISTORY_DEFAULT_DAYS - 1)
        if start > to:
            start, to = to, start
        qs = AuditLog.objects.filter(occurred_at__date__gte=start, occurred_at__date__lte=to)
        if p.get("actor", "").isdigit():
            qs = qs.filter(actor_id=int(p["actor"]))
        if p.get("screen") in audit.SCREEN_LABELS:
            qs = qs.filter(screen=p["screen"])
        if p.get("action") in audit.ACTION_LABELS:
            qs = qs.filter(action=p["action"])
        if p.get("q", "").strip():
            q = p["q"].strip()[:100]
            qs = qs.filter(Q(target_label__icontains=q) | Q(actor_username__icontains=q))

        total = qs.count()
        page_count = max(1, -(-total // HISTORY_PAGE_SIZE))
        page = min(max(int(p["page"]) if p.get("page", "").isdigit() else 1, 1), page_count)
        logs = qs.select_related("actor")[(page - 1) * HISTORY_PAGE_SIZE : page * HISTORY_PAGE_SIZE]

        # 사람 고르기 목록: 기록을 남긴 적 있는 사람만 "이름(아이디)"
        actor_ids = AuditLog.objects.exclude(actor=None).values_list("actor_id", flat=True).distinct()
        actors = {u.id: f"{_name(u)}({u.username})" for u in User.objects.filter(id__in=actor_ids)}
        return Response(
            {
                "from": start,
                "to": to,
                "rows": [audit.present(log) for log in logs],
                "total": total,
                "page": page,
                "page_count": page_count,
                "actors": sorted(({"id": k, "label": v} for k, v in actors.items()), key=lambda a: a["label"]),
                "screens": [{"key": k, "label": v} for k, v in audit.SCREEN_LABELS.items()],
                "actions": [{"key": k, "label": v} for k, v in audit.ACTION_LABELS.items()],
            }
        )
