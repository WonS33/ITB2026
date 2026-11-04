"""경영지원 관리 장부 API (조원 저장소 ledger/actions.ts, copy-actions.ts 를 옮김)

- 기준년월별 거래처 잔액. 이번 달 이후의 달은 보거나 입력할 수 없다
- 행 추가·수정·숨김·복구 — 변경 기록(같은 transaction)과 동시 수정 확인. 구분(kind)은 바꿀 수 없다
- 날짜: 완료일은 오늘 이후 불가. 외상매출금은 "당월 수금"일 때만 완료일을 넣고, 그때는 필수
- [지난달 내용 불러오기]: 이번 달이 비어 있을 때만. 당월 수금 행은 기본 제외(포함하면 당월 수금예정으로), 완료일은 모두 비움
- 권한: 경영지원팀 수정 권한이면 모두 가능 (조원 규칙)
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit
from .models import LedgerEntry
from .serializers import LedgerFieldsSerializer
from .views import Conflict, ManagementApiView, _check_year_month, _name

K, S = LedgerEntry.Kind, LedgerEntry.ArStatus
FIELDS = audit.LEDGER_SNAPSHOT_FIELDS


def _month_index(year, month):
    return year * 12 + month - 1


def _check_month(year, month):
    _check_year_month(year, month)
    today = timezone.localdate()
    if _month_index(year, month) > _month_index(today.year, today.month):
        raise ValidationError({"detail": "이번 달 이후의 기준년월에는 입력할 수 없습니다."})


def _previous(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _date_error(d, today):
    """완료일 규칙 (외상매출금은 당월 수금일 때만, 그때는 필수)"""
    is_ar = d["kind"] == K.AR
    collected = is_ar and d["ar_status"] == S.COLLECTED
    settled = d["settled_on"]
    if settled is None:
        return "수금 완료일을 입력하세요." if collected else None
    if settled > today:
        return "완료일은 오늘 이후로 입력할 수 없습니다."
    if is_ar and not collected:
        return "완료일은 당월 수금일 때만 입력합니다."
    return None


def _row(e):
    return {
        "id": e.id,
        "kind": e.kind,
        **{f: getattr(e, f) for f in FIELDS},
        "hidden": e.deleted_at is not None,
        "deleted_at": e.deleted_at,
        "deleted_by": _name(e.deleted_by) if e.deleted_by else None,
        "updated_at": e.updated_at,  # 동시 수정 확인용
        "updated_by": _name(e.updated_by) if e.updated_by else None,
    }


def _choices(model_choices):
    return [{"value": v, "label": label} for v, label in model_choices]


class LedgerView(ManagementApiView):
    """GET/POST /api/management/ledger/?year=&month= — 기준년월의 모든 행(숨긴 행 포함, 입력 순서대로)·행 추가"""

    def get(self, request):
        today = timezone.localdate()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            raise ValidationError({"detail": "기준년월을 확인하세요."})
        _check_month(year, month)
        rows = LedgerEntry.objects.filter(year=year, month=month).select_related("updated_by", "deleted_by").order_by("created_at", "id")
        return Response({
            "year": year,
            "month": month,
            "today": today,
            "rows": [_row(e) for e in rows],
            "kinds": _choices(K.choices),
            "ar_statuses": _choices(S.choices),
            "purchase_types": _choices(LedgerEntry.PurchaseType.choices),
            "expense_types": _choices(LedgerEntry.ExpenseType.choices),
        })

    def post(self, request):
        try:
            year, month = int(request.data.get("year")), int(request.data.get("month"))
        except (TypeError, ValueError):
            raise ValidationError({"detail": "기준년월을 확인하세요."})
        _check_month(year, month)
        serializer = LedgerFieldsSerializer(data=request.data.get("fields") or {})
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        error = _date_error(d, timezone.localdate())
        if error:
            raise ValidationError({"detail": error})
        with transaction.atomic():
            e = LedgerEntry.objects.create(
                year=year, month=month, kind=d["kind"], **{f: d[f] for f in FIELDS},
                created_by=request.user, updated_by=request.user,
            )
            audit.record_audit(
                actor=request.user, screen="ledger", action="CREATE", target_type="LedgerEntry", target_id=e.pk,
                target_label=audit.ledger_label(e),
                changes=audit.diff_fields(None, audit.ledger_snapshot(e), audit.ledger_fields(e.kind)),
            )
        return Response({"message": f"{e.get_kind_display()} {e.partner_name} 행을 추가했습니다."}, status=201)


def _load(pk, expected, hidden=False):
    e = get_object_or_404(LedgerEntry.objects.select_for_update(), pk=pk)
    if e.updated_at != expected:
        raise Conflict("다른 사람이 먼저 수정했습니다. 새로고침 후 다시 시도하세요.")
    if hidden and e.deleted_at is None:
        raise ValidationError({"detail": "이미 복구된 항목입니다. 새로고침하세요."})
    if not hidden and e.deleted_at is not None:
        raise ValidationError({"detail": "숨긴 항목입니다. 복구한 뒤 수정하세요."})
    return e


def _expected(request):
    value = request.data.get("expected_updated_at")
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        raise ValidationError({"expected_updated_at": "불러온 시각이 필요합니다."})
    return parsed


class LedgerDetailView(ManagementApiView):
    """PUT /api/management/ledger/{id}/ — 행 수정 (구분은 바꿀 수 없음)"""

    def put(self, request, pk):
        expected = _expected(request)
        serializer = LedgerFieldsSerializer(data=request.data.get("fields") or {})
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        with transaction.atomic():
            e = _load(pk, expected)
            if e.kind != d["kind"]:
                raise ValidationError({"detail": "구분은 바꿀 수 없습니다. 숨긴 뒤 새 행으로 추가하세요."})
            error = _date_error(d, timezone.localdate())
            if error:
                raise ValidationError({"detail": error})
            before = audit.ledger_snapshot(e)
            for f in FIELDS:
                setattr(e, f, d[f])
            e.updated_by = request.user
            e.save()
            audit.record_audit(
                actor=request.user, screen="ledger", action="UPDATE", target_type="LedgerEntry", target_id=e.pk,
                target_label=audit.ledger_label(e),
                changes=audit.diff_fields(before, audit.ledger_snapshot(e), audit.ledger_fields(e.kind)),
            )
        return Response({"message": f"{e.partner_name} 행을 저장했습니다."})


class LedgerActionView(ManagementApiView):
    """POST /api/management/ledger/{id}/hide|restore/"""

    def post(self, request, pk, action):
        if action not in ("hide", "restore"):
            raise ValidationError({"detail": "알 수 없는 동작입니다."})
        expected = _expected(request)
        with transaction.atomic():
            e = _load(pk, expected, hidden=action == "restore")
            if action == "hide":
                e.deleted_at, e.deleted_by = timezone.now(), request.user
            else:
                e.deleted_at, e.deleted_by = None, None
            e.updated_by = request.user
            e.save()
            audit.record_audit(
                actor=request.user, screen="ledger", action="HIDE" if action == "hide" else "RESTORE",
                target_type="LedgerEntry", target_id=e.pk, target_label=audit.ledger_label(e),
            )
        if action == "hide":
            return Response({"message": f"{e.partner_name} 행을 숨겼습니다. [숨긴 항목 보기]에서 복구할 수 있습니다."})
        return Response({"message": f"{e.partner_name} 행을 복구했습니다."})


# ---------- 지난달 내용 불러오기 ----------


def plan_copy(rows, include_collected):
    """복사할 행: 당월 수금은 기본 제외(포함하면 당월 수금예정으로), 완료일은 모두 비움"""
    entries, collected = [], {"count": 0, "amount": 0}
    for r in rows:
        is_collected = r.kind == K.AR and r.ar_status == S.COLLECTED
        if is_collected:
            collected["count"] += 1
            collected["amount"] += r.amount
            if not include_collected:
                continue
        entries.append({
            "kind": r.kind,
            **{f: getattr(r, f) for f in FIELDS},
            "ar_status": S.SCHEDULED if is_collected else r.ar_status,
            "settled_on": None,
        })
    kinds = [
        {"kind": k, "count": sum(1 for e in entries if e["kind"] == k), "amount": sum(e["amount"] for e in entries if e["kind"] == k)}
        for k, _ in K.choices
    ]
    return entries, {"kinds": kinds, "collected": collected, "total": len(entries)}


def _visible(year, month):
    return LedgerEntry.objects.filter(year=year, month=month, deleted_at__isnull=True)


class LedgerCopyView(ManagementApiView):
    """GET  /api/management/ledger/copy/?year=&month= — 미리보기 (DB 쓰기 없음)
    POST /api/management/ledger/copy/ {year, month, include_collected, expected_source_count} — 저장
    이번 달이 비어 있고 지난달 행 수가 미리보기 때와 같을 때만. 변경 기록은 요약 1건"""

    def get(self, request):
        year, month = int(request.query_params.get("year", 0)), int(request.query_params.get("month", 0))
        _check_month(year, month)
        fy, fm = _previous(year, month)
        source = list(_visible(fy, fm).order_by("created_at", "id"))
        _, summary = plan_copy(source, include_collected=False)
        return Response({
            "from": f"{fy}-{fm:02d}",
            "existing": _visible(year, month).count(),  # 1 이상이면 불러올 수 없음
            "source_count": len(source),
            **summary,
        })

    def post(self, request):
        try:
            year, month = int(request.data.get("year")), int(request.data.get("month"))
            expected_count = int(request.data.get("expected_source_count"))
        except (TypeError, ValueError):
            raise ValidationError({"detail": "입력값을 확인하세요."})
        include = bool(request.data.get("include_collected"))
        _check_month(year, month)
        fy, fm = _previous(year, month)
        now = timezone.now()
        month_text, from_text = f"{year}-{month:02d}", f"{fy}-{fm:02d}"
        with transaction.atomic():
            # 같은 달을 두 사람이 동시에 불러오지 못하게 그 두 달의 행을 잠근다
            list(LedgerEntry.objects.select_for_update().filter(year__in=(year, fy), month__in=(month, fm)))
            if _visible(year, month).exists():
                raise Conflict(f"{month_text}에 이미 입력된 행이 있어 불러올 수 없습니다. 새로고침 후 확인하세요.")
            source = list(_visible(fy, fm).order_by("created_at", "id"))
            if len(source) != expected_count:
                raise Conflict(f"{from_text} 내용이 미리보기 뒤에 바뀌었습니다. 다시 열어 확인하세요.")
            entries, summary = plan_copy(source, include)
            if not entries:
                raise Conflict(f"{from_text}에 불러올 행이 없습니다.")
            for e in entries:  # 지난달 순서 그대로 (입력 순서 = created_at)
                LedgerEntry.objects.create(year=year, month=month, created_by=request.user, updated_by=request.user, **e)
            audit.record_audit(
                actor=request.user, screen="ledger-copy", action="CREATE", target_type="LedgerMonth", target_id=month_text,
                target_label=f"경영지원 관리 {month_text} · 지난달({from_text}) 내용 불러오기",
                meta={
                    "month": month_text, "from": from_text, "saved_rows": len(entries),
                    "collected_rows": summary["collected"]["count"], "include_collected": "포함" if include else "제외",
                },
            )
        return Response({"message": f"{from_text} 내용 {len(entries)}행을 {month_text}로 불러왔습니다. 잔액을 이번 달 값으로 고치세요."})
