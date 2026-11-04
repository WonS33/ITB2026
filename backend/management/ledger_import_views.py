"""경영지원 관리 엑셀 이관 API (조원 저장소 ledger/import/actions.ts·save-import.ts 를 옮김)

추출 → 사람이 확인·선택 → 저장 (CLAUDE.md 6절)
- POST import/preview/: 파일을 읽어 미리보기만 돌려준다 (DB에 아무것도 쓰지 않음)
- POST import/: 같은 파일을 다시 보내 저장. 파일 SHA-256·같은 달 기존 행 수가 미리보기 때와 같아야 한다
- 덮어쓰기 = 같은 기준년월의 기존 행을 숨김(삭제 아님) 뒤 저장 / 추가 = 그대로 두고 더함
- 변경 기록은 요약 1건 (행마다 남기지 않음)
"""

import hashlib
import json
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit
from .ledger_import import KINDS, MAX_BYTES, build_plan, default_settled_on, parse_ledger_sheet, select_sheet
from .ledger_views import FIELDS, _check_month
from .models import LedgerEntry
from .views import Conflict, ManagementApiView


def _existing(year, month):
    rows = LedgerEntry.objects.filter(year=year, month=month, deleted_at__isnull=True)
    return {k: rows.filter(kind=k).count() for k in KINDS}


def _load(request):
    """기준년월 → 파일 검사 → 읽기 → 시트 고르기 → 해석 (미리보기·가져오기 공용)"""
    try:
        year, month = int(request.data.get("year")), int(request.data.get("month"))
    except (TypeError, ValueError):
        raise ValidationError({"detail": "기준년월을 고르세요."})
    _check_month(year, month)
    files = request.FILES.getlist("file")
    if len(files) != 1:
        raise ValidationError({"detail": "파일 1개를 고르세요."})
    f = files[0]
    if f.size == 0:
        raise ValidationError({"detail": "빈 파일입니다."})
    if not f.name.lower().endswith(".xlsx"):
        raise ValidationError({"detail": ".xlsx 파일만 올릴 수 있습니다."})
    if f.size > MAX_BYTES:
        raise ValidationError({"detail": "파일이 5MB를 넘습니다."})
    content = f.read()
    try:
        wb = load_workbook(BytesIO(content))  # 수식 그대로 (수식 여부·병합·글자색·배경색)
        wv = load_workbook(BytesIO(content), data_only=True)  # 엑셀이 저장해 둔 계산값
    except Exception:
        raise ValidationError({"detail": "엑셀 파일을 열 수 없습니다. 파일이 손상됐거나 .xlsx 형식이 아닙니다."})

    month_text = f"{year}-{month:02d}"
    name, info = select_sheet(wb, month_text, request.data.get("sheet") or None)
    if name is None:
        if info["reason"] == "none":
            raise ValidationError({"detail": '경영지원_관리 양식이 아닙니다. C열에 "외상매출금" 같은 블록 제목이 있는 파일을 올려 주세요.'})
        raise ValidationError({
            "detail": f"이 파일에는 양식 시트가 여러 장 있고 기준년월({month_text})과 같은 이름이 없습니다. 가져올 시트를 고르세요.",
            "sheet_choices": info["candidates"],
        })
    today = timezone.localdate()
    return {
        "year": year, "month": month, "today": today, "file_name": f.name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "parsed": parse_ledger_sheet(wb[name], wv[name], year, month, today),
        "sheet_candidates": info["candidates"], "sheet_note": info["note"],
        "existing": _existing(year, month),
    }


class LedgerImportPreviewView(ManagementApiView):
    """POST /api/management/ledger/import/preview/ (file, year, month, sheet?) — 미리보기"""

    def post(self, request):
        x = _load(request)
        p = x["parsed"]
        blocks = []
        for b in p["blocks"]:
            ok = [r for r in b["rows"] if r["amount"] is not None]
            blocks.append({
                "kind": b["kind"], "rows": b["rows"],
                "sum": sum(r["amount"] for r in ok),
                "auto_transfer_sum": sum(r["amount"] for r in ok if r["auto_transfer"]),
                "skipped_code_only": b["skipped"]["code_only"], "skipped_zero": b["skipped"]["zero"],
                "totals": b["totals"],
            })
        return Response({
            "file_name": x["file_name"], "file_sha256": x["sha256"], "sheet_name": p["sheet_name"],
            "sheet_candidates": x["sheet_candidates"], "sheet_note": x["sheet_note"],
            "year": x["year"], "month": x["month"], "fatal": p["fatal"], "blocks": blocks,
            "existing": x["existing"], "existing_total": sum(x["existing"].values()),
            # 완료일이 없는 당월 수금 행 기본값 (미분류를 당월 수금으로 고를 때도)
            "default_settled_on": default_settled_on(x["year"], x["month"], x["today"]),
        })


class LedgerImportView(ManagementApiView):
    """POST /api/management/ledger/import/ (file, year, month, sheet?, file_sha256, mode, expected_existing, choices) — 저장"""

    def post(self, request):
        x = _load(request)
        if request.data.get("file_sha256") != x["sha256"]:
            raise ValidationError({"detail": "미리보기한 파일과 다른 파일입니다. 다시 미리보기 해 주세요."})
        try:
            expected = int(request.data.get("expected_existing"))
            choices = json.loads(request.data.get("choices") or "{}")
        except (TypeError, ValueError):
            raise ValidationError({"detail": "요청 값을 확인하세요. 다시 미리보기 해 주세요."})
        if not isinstance(choices, dict):
            raise ValidationError({"detail": "선택값 형식이 틀렸습니다."})
        existing_total = sum(x["existing"].values())
        if existing_total != expected:
            raise Conflict("미리보기 후 같은 기준년월 데이터가 바뀌었습니다. 다시 미리보기 해 주세요.")
        mode = request.data.get("mode")
        mode = mode if mode in ("overwrite", "append") else None
        mode = "append" if existing_total == 0 else mode  # 기존 행이 없으면 구분 없음

        year, month, today = x["year"], x["month"], x["today"]
        plan = build_plan(x["parsed"], choices, year, month, today, mode, existing_total)
        if plan["blockers"]:
            raise ValidationError({"detail": plan["blockers"][0]["message"], "blockers": plan["blockers"]})

        excluded = sum(len(b["skipped"]["code_only"]) + len(b["skipped"]["zero"]) for b in x["parsed"]["blocks"])
        now = timezone.now()
        month_text = f"{year}-{month:02d}"
        with transaction.atomic():
            current = LedgerEntry.objects.select_for_update().filter(year=year, month=month, deleted_at__isnull=True)
            if current.count() != expected:
                raise Conflict("미리보기 후 같은 기준년월 데이터가 바뀌었습니다. 다시 미리보기 해 주세요.")
            hidden = current.update(deleted_at=now, deleted_by=request.user, updated_by=request.user) if mode == "overwrite" else 0
            for e in plan["entries"]:  # 엑셀 행 순서 그대로 (입력 순서 = created_at)
                d = e["fields"]
                LedgerEntry.objects.create(
                    year=year, month=month, kind=d["kind"], **{f: d[f] for f in FIELDS},
                    created_by=request.user, updated_by=request.user,
                )
            blocks = [{"kind": k, "count": plan["summary"][k]["count"], "sum": plan["summary"][k]["sum"]} for k in KINDS]
            audit.record_audit(
                actor=request.user, screen="ledger-import", action="IMPORT", target_type="LedgerMonth", target_id=month_text,
                target_label=f"경영지원 관리 엑셀 이관 · {month_text} · {x['file_name']}",
                meta={
                    "file_name": x["file_name"], "file_sha256": x["sha256"], "sheet_name": x["parsed"]["sheet_name"],
                    "month": month_text, "mode": "덮어쓰기" if mode == "overwrite" else "추가",
                    "saved_rows": len(plan["entries"]), "hidden_rows": hidden, "excluded_rows": excluded, "blocks": blocks,
                },
            )
        return Response({"year": year, "month": month, "hidden": hidden, "blocks": blocks, "saved": len(plan["entries"])})
