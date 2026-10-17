"""일련번호 조회 (specs/05-production.md 2절)

- 검색: 숫자 1~4자리면 4자리 번호(serial_short)로, 그 외에는 전체 번호(serial_full)로 찾는다
- 상세: 조회 항목 11개를 specs 순서대로 돌려준다
"""

import re

from django.db.models import Q

from .models import ManufacturingRecord, SalesOrderItem

SEARCH_LIMIT = 50


def search_serials(query):
    q = (query or "").strip().upper()
    if not q:
        return ManufacturingRecord.objects.none()
    if re.fullmatch(r"\d{1,4}", q):
        condition = Q(serial_short=q.zfill(4))  # 1 → 0001
    else:
        condition = Q(serial_full=q)
    return ManufacturingRecord.objects.filter(condition).order_by("-manufactured_date", "serial_full")[:SEARCH_LIMIT]


def format_bush(value):
    """부시 가공 숫자 6자리 → 엑셀 표시 형식과 같게 (301008 → Ø30x10x08)"""
    if value and re.fullmatch(r"\d{6}", value):
        return f"Ø{value[0:2]}x{value[2:4]}x{value[4:6]}"
    return value


def _date(value):
    return value.isoformat() if value else ""


def flanges_for(record):
    """플랜지 보완: 제조내역 PO번호와 같은 "수주서류 번호"를 가진 수주서의 Flange 값

    ⚠️ 두 파일을 잇는 기준 번호는 기업 확인 전이다. 샘플에서 형식이 같아(#26006 / #26024) 임시로 이렇게 잇는다.
    """
    if not record.po_no:
        return None
    values = SalesOrderItem.objects.filter(order__order_doc_no=record.po_no).exclude(flange="")
    flanges = sorted(set(values.values_list("flange", flat=True)))
    return ", ".join(flanges) or None


def serial_detail(record):
    spec = {
        "모델명": record.model_name,
        "부시 가공": format_bush(record.bush_machining),
        "rpm": record.rpm,
        "전원": record.power,
        # 플랜지는 제조내역 엑셀에 열이 없고 수주서 PDF에만 있다 → 수주서에서 보완 (없으면 None)
        "Flange": flanges_for(record),
    }
    order_numbers = {
        "PO번호": f"#{record.po_no}" if record.po_no else "",
        "SO번호": record.so_no,
    }
    return {
        "serial_full": record.serial_full,
        "items": [
            {"no": 1, "label": "제품 사양", "value": spec},
            {"no": 2, "label": "제조년월", "value": _date(record.manufactured_date)},
            {"no": 3, "label": "검사일자", "value": _date(record.inspection_date)},
            {"no": 4, "label": "검사번호", "value": record.inspection_no},
            {"no": 5, "label": "수주번호", "value": order_numbers},
            {"no": 6, "label": "판매처", "value": record.customer},
            {"no": 7, "label": "최종발주처", "value": record.final_orderer},
            {"no": 8, "label": "사업명", "value": record.project_name},
            {"no": 9, "label": "출고일자", "value": _date(record.shipped_date)},
            {"no": 10, "label": "납기일자", "value": _date(record.due_date)},
            {"no": 11, "label": "비고", "value": record.note},
        ],
    }
