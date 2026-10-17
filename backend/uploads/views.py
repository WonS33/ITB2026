"""업로드 API (specs/08-api.md 6절) — 추출 → 확인·수정 → 저장

POST  /api/uploads/               파일 업로드 + 추출 (DB에는 아직 저장하지 않음)
PATCH /api/uploads/{id}/          확인 화면에서 고친 값·제외 여부 반영 후 다시 검사
POST  /api/uploads/{id}/confirm/  최종 저장 (이미 있는 기준 번호는 건너뜀)
POST  /api/uploads/{id}/cancel/   업로드 취소

권한: 파일 종류를 담당하는 팀의 수정 권한 (예: 제조내역 엑셀 → 생산팀 수정 권한)
"""

import logging
from pathlib import Path

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .handlers import HANDLERS
from .handlers.base import check_rows, summarize
from .models import UploadBatch

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _check_edit_permission(user, handler):
    if not user.can_edit(handler.team):
        raise PermissionDenied("이 파일을 업로드할 권한이 없습니다.")


def _batch_data(batch):
    data = batch.extracted_data
    return {
        "id": batch.id,
        "kind": batch.kind,
        "kind_display": batch.get_kind_display(),
        "file_name": batch.file_name,
        "status": batch.status,
        "columns": data.get("columns", []),
        "rows": data.get("rows", []),
        "summary": summarize(data.get("rows", []), data.get("skipped_count", 0)),
        "saved_count": batch.saved_count,
    }


class UploadCreateView(APIView):
    def post(self, request):
        kind = request.data.get("kind")
        handler = HANDLERS.get(kind)
        if handler is None:
            raise ValidationError({"kind": "아직 지원하지 않는 파일 종류입니다."})
        _check_edit_permission(request.user, handler)

        file = request.FILES.get("file")
        if file is None:
            raise ValidationError({"file": "파일을 선택해 주세요."})
        if Path(file.name).suffix.lower() not in handler.allowed_extensions:
            raise ValidationError({"file": f"{', '.join(handler.allowed_extensions)} 파일만 올릴 수 있습니다."})
        if file.size > MAX_FILE_SIZE:
            raise ValidationError({"file": "10MB 이하 파일만 올릴 수 있습니다."})

        try:
            rows, skipped = handler.parse(file)
        except ValueError as e:
            raise ValidationError({"file": str(e)})
        except Exception:
            logger.exception("파일 추출 실패: %s", file.name)
            raise ValidationError({"file": "파일을 읽을 수 없습니다. 양식과 파일 형식을 확인해 주세요."})

        for i, row in enumerate(rows):
            row.update(id=i, excluded=False)
        check_rows(handler, rows)
        batch = UploadBatch.objects.create(
            kind=kind,
            file_name=file.name,
            extracted_data={
                "columns": [{"key": k, "label": label} for k, label in handler.columns],
                "rows": rows,
                "skipped_count": skipped,
            },
            created_by=request.user,
        )
        return Response(_batch_data(batch), status=status.HTTP_201_CREATED)


class UploadBatchMixin:
    def get_batch(self, request, pk, lock=False):
        # lock=True: 저장 중에는 같은 업로드를 다른 요청이 동시에 처리하지 못하게 잠근다 (두 번 클릭 방지)
        queryset = UploadBatch.objects.select_for_update() if lock else UploadBatch.objects
        batch = get_object_or_404(queryset, pk=pk)
        handler = HANDLERS[batch.kind]
        _check_edit_permission(request.user, handler)
        if batch.status != UploadBatch.Status.EXTRACTED:
            raise ValidationError({"detail": f"이미 처리된 업로드입니다 ({batch.get_status_display()})."})
        return batch, handler


class UploadDetailView(UploadBatchMixin, APIView):
    def patch(self, request, pk):
        batch, handler = self.get_batch(request, pk)
        rows = batch.extracted_data["rows"]
        editable = {k for k, _label in handler.columns}
        by_id = {row["id"]: row for row in rows}

        for change in request.data.get("rows", []):
            row = by_id.get(change.get("id"))
            if row is None:
                continue
            for key, value in (change.get("values") or {}).items():
                if key in editable:
                    row["values"][key] = "" if value is None else str(value)
            if "excluded" in change:
                row["excluded"] = bool(change["excluded"])

        check_rows(handler, rows)
        batch.save(update_fields=["extracted_data", "updated_at"])
        return Response(_batch_data(batch))


class UploadConfirmView(UploadBatchMixin, APIView):
    def post(self, request, pk):
        with transaction.atomic():
            batch, handler = self.get_batch(request, pk, lock=True)
            rows = check_rows(handler, batch.extracted_data["rows"])  # 저장 직전에 중복을 다시 확인
            summary = summarize(rows)
            if summary["error_rows"]:
                batch.save(update_fields=["extracted_data", "updated_at"])
                return Response(
                    {"detail": f"오류가 있는 행이 {summary['error_rows']}개 있습니다. 고치거나 제외한 뒤 저장해 주세요.",
                     "batch": _batch_data(batch)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            to_save = [r for r in rows if not r["excluded"] and not r["duplicate"]]
            batch.saved_count = handler.save(to_save, request.user)
            batch.status = UploadBatch.Status.SAVED
            batch.save()
        return Response(_batch_data(batch))


class UploadCancelView(UploadBatchMixin, APIView):
    def post(self, request, pk):
        batch, _handler = self.get_batch(request, pk)
        batch.status = UploadBatch.Status.CANCELLED
        batch.save(update_fields=["status", "updated_at"])
        return Response(_batch_data(batch))
