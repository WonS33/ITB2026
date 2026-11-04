"""미수금 건별 기록 API (조원 저장소 receivables/actions.ts 를 옮김)

- 등록·수정·수금 처리·수금 취소·숨김·복구 — 모두 변경 기록(같은 transaction)과 동시 수정 확인
- 권한: 경영지원팀 수정 권한(대표·관리자·경영지원팀 소속)이면 모두 가능 (조원 규칙: 경영지원팀 = 확정 권한까지)
- 숨긴 건은 복구 말고는 아무것도 못 한다. 수금 완료 건은 [수금 처리] 대신 수정·수금 취소
"""

import calendar
from datetime import date
from urllib.parse import quote

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from common.periods import make_period, period_from_params

from . import audit, export
from .metrics import receivables as ar_receivables
from .models import AuditLog, Receivable
from .receivables import date_errors, item_receivables, row_status
from .serializers import ReceivableActionSerializer, ReceivableSerializer
from .views import Conflict, ManagementApiView, _name


def _row(r, today):
    return {
        "id": r.id,
        "customer_name": r.customer_name,
        "occurred_on": r.occurred_on,
        "amount": r.amount,
        "due_on": r.due_on,
        "note": r.note,
        "is_collected": r.is_collected,
        "collected_on": r.collected_on,
        "hidden": r.deleted_at is not None,
        "deleted_at": r.deleted_at,
        "deleted_by": _name(r.deleted_by) if r.deleted_by else None,
        "updated_at": r.updated_at,  # 동시 수정 확인용
        "updated_by": _name(r.updated_by) if r.updated_by else None,
        **row_status(r, today),
    }


def _basis(today):
    """화면 맨 위 비교: 대시보드 미수금(장부 외상매출금, 올해 입력이 있는 마지막 달) ↔ 이 화면 합계 (같은 기준일)"""
    ar = ar_receivables(make_period("year", today.year), today)
    if ar["month"]:
        m = ar["month"]
        as_of = min(date(m["year"], m["month"], calendar.monthrange(m["year"], m["month"])[1]), today)
    else:
        as_of = today
    return {
        "ar_month": ar["month"],
        "ar_total": ar.get("total", 0),
        "item_total": item_receivables(as_of)["total"],
        "as_of": as_of,
    }


class ReceivablesView(ManagementApiView):
    """GET/POST /api/management/receivables/ — 목록(숨긴 건 포함, 화면에서 나눔)·등록"""

    def get(self, request):
        today = timezone.localdate()
        rows = Receivable.objects.select_related("updated_by", "deleted_by")
        names = sorted({r.customer_name for r in rows if r.deleted_at is None})
        return Response({
            "today": today,
            "rows": [_row(r, today) for r in rows],
            "customer_names": names,  # 거래처 자동완성 (숨긴 건 제외)
            "basis": _basis(today),
        })

    def post(self, request):
        serializer = ReceivableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        errors = date_errors(d["occurred_on"], timezone.localdate(), due_on=d["due_on"])
        if errors:
            raise ValidationError({"detail": errors[0]})
        with transaction.atomic():
            r = Receivable.objects.create(
                customer_name=d["customer_name"], occurred_on=d["occurred_on"], amount=d["amount"],
                due_on=d["due_on"], note=d["note"], created_by=request.user, updated_by=request.user,
            )
            audit.record_audit(
                actor=request.user, screen="receivables", action="CREATE", target_type="Receivable",
                target_id=r.pk, target_label=audit.receivable_label(r),
                changes=audit.diff_fields(None, audit.receivable_snapshot(r), audit.RECEIVABLE_FIELDS),
            )
        return Response({"message": f"{r.customer_name} 미수금을 등록했습니다."}, status=201)


def _load(pk, expected, hidden=False):
    """잠근 채로 한 건을 불러와 동시 수정·숨김 상태를 확인 (transaction 안에서 부른다)"""
    r = get_object_or_404(Receivable.objects.select_for_update(), pk=pk)
    if r.updated_at != expected:
        raise Conflict("다른 사람이 먼저 수정했습니다. 새로고침 후 다시 시도하세요.")
    if hidden and r.deleted_at is None:
        raise ValidationError({"detail": "이미 복구된 항목입니다. 새로고침하세요."})
    if not hidden and r.deleted_at is not None:
        raise ValidationError({"detail": "숨긴 항목입니다. 복구한 뒤 수정하세요."})
    return r


def _save(request, r, before, action, track_changes=True):
    r.updated_by = request.user
    r.save()
    audit.record_audit(
        actor=request.user, screen="receivables", action=action, target_type="Receivable", target_id=r.pk,
        target_label=audit.receivable_label(r),
        # 숨김·복구는 동작만, 나머지는 바뀐 칸
        changes=audit.diff_fields(before, audit.receivable_snapshot(r), audit.RECEIVABLE_FIELDS) if track_changes else [],
    )


class ReceivableDetailView(ManagementApiView):
    """PUT /api/management/receivables/{id}/ — 수정 (수금 완료 건이면 수금일도 함께)"""

    def put(self, request, pk):
        serializer = ReceivableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if d["expected_updated_at"] is None:
            raise ValidationError({"expected_updated_at": "불러온 시각이 필요합니다."})
        with transaction.atomic():
            r = _load(pk, d["expected_updated_at"])
            if not r.is_collected and d["collected_on"] is not None:
                raise ValidationError({"detail": "미수 건은 [수금 처리]로 수금일을 입력하세요."})
            errors = date_errors(d["occurred_on"], timezone.localdate(), due_on=d["due_on"],
                                 collected_on=d["collected_on"], check_collected=r.is_collected)
            if errors:
                raise ValidationError({"detail": errors[0]})
            before = audit.receivable_snapshot(r)
            for f in ("customer_name", "occurred_on", "amount", "due_on", "note"):
                setattr(r, f, d[f])
            if r.is_collected:
                r.collected_on = d["collected_on"]
            _save(request, r, before, "UPDATE")
        return Response({"message": f"{r.customer_name} 미수금을 수정했습니다."})


class ReceivableActionView(ManagementApiView):
    """POST /api/management/receivables/{id}/{collect|uncollect|hide|restore}/"""

    def post(self, request, pk, action):
        serializer = ReceivableActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        today = timezone.localdate()
        with transaction.atomic():
            r = _load(pk, d["expected_updated_at"], hidden=action == "restore")
            before = audit.receivable_snapshot(r)
            if action == "collect":
                if r.is_collected:
                    raise ValidationError({"detail": "이미 수금 완료된 건입니다."})
                errors = date_errors(r.occurred_on, today, collected_on=d["collected_on"], check_collected=True)
                if errors:
                    raise ValidationError({"detail": errors[0]})
                r.is_collected, r.collected_on = True, d["collected_on"]
                _save(request, r, before, "COLLECT")
                message = f"{r.customer_name} {r.collected_on} 수금 처리했습니다."
            elif action == "uncollect":
                if not r.is_collected:
                    raise ValidationError({"detail": "수금 완료된 건이 아닙니다."})
                r.is_collected, r.collected_on = False, None
                _save(request, r, before, "UNCOLLECT")
                message = f"{r.customer_name} 수금을 취소하고 미수로 되돌렸습니다."
            elif action == "hide":
                r.deleted_at, r.deleted_by = timezone.now(), request.user
                _save(request, r, before, "HIDE", track_changes=False)
                message = f"{r.customer_name} 건을 숨겼습니다. 목록·통계에서 제외됩니다."
            elif action == "restore":
                r.deleted_at, r.deleted_by = None, None
                _save(request, r, before, "RESTORE", track_changes=False)
                message = f"{r.customer_name} 건을 복구했습니다."
            else:
                raise ValidationError({"detail": "알 수 없는 동작입니다."})
        return Response({"message": message})


class ReceivablesExportView(ManagementApiView):
    """GET /api/management/receivables/export/?(기간) — 미수금 건별 엑셀. 기준일 = min(기간 말일, 오늘), 숨긴 건 제외"""

    def get(self, request):
        period = period_from_params(request.query_params)
        as_of = min(period.end, timezone.localdate())
        result = item_receivables(as_of)
        name = f"미수금_{as_of.isoformat()}.xlsx"
        content = export.build_receivables_workbook(result)
        audit.record_audit(
            actor=request.user, screen="receivables-export", action="EXPORT", target_type="Receivable",
            target_id=name, target_label=f"{as_of.isoformat()} 기준 미수금",
            meta={"period": f"{as_of.isoformat()} 기준", "sheet_count": 2, "file_name": name},
        )
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename=\"receivables.xlsx\"; filename*=UTF-8''{quote(name)}"
        return response


class RowHistoryView(ManagementApiView):
    """GET /api/management/history/row/?type=Receivable&id=3 — 한 건의 변경 기록 (최근부터)"""

    TYPES = ("Receivable", "LedgerEntry")

    def get(self, request):
        target_type, target_id = request.query_params.get("type"), request.query_params.get("id", "")
        if target_type not in self.TYPES or not target_id.isdigit():
            raise ValidationError({"detail": "대상을 확인하세요."})
        logs = AuditLog.objects.filter(target_type=target_type, target_id=target_id).select_related("actor")
        return Response({"rows": [audit.present(log) for log in logs]})
