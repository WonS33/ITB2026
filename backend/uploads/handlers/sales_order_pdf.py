"""수주서 PDF 업로드 규칙 (specs/05-production.md 1절·4절)

- PDF 1페이지 = 수주서 1건. 확인 표는 "제품 1개 = 1행"이고, 주문 정보(판매번호·판매처 등)는 행마다 반복한다
- 중복 확인 기준: 판매번호 (이미 저장된 판매번호의 수주서는 통째로 건너뜀)
- 긴 값이 "…"로 잘려 있으면 오류로 표시해서 사람이 전체 값으로 고치게 한다
- 사업구분 원문은 산업 분야(7개)로 바꿔 함께 보여준다 (production/industry_map.py)
"""

import re

from production.industry_map import INDUSTRIES, to_industry
from production.models import SalesOrder, SalesOrderItem

from .base import UploadHandler, parse_iso_date
from .pdf_form import TRUNCATED, read_pages

LABELS = [
    "브랜드 구분", "작업 구분", "사업 구분", "수출 구분", "판매번호", "수주일", "판매처", "최종발주처 / EPC", "사업명",
    "수주번호", "출고된 리모컨 수", "납기일", "매출액", "제작관련 공통사양 / 납품 관련 사항 / 비고", "납품일 / 출장일",
    "납품처 담당자 (연락처)", "생산/출장 담당자", "수주서류", "영업/계약/결제 관련 특이사항", "결제방법",
    "세금계산서 발행일", "견적서", "영업 담당자", "수금일",
]
HEADINGS = ["구분", "판매정보", "제품정보", "결제정보"]
ITEM_HEADERS = ["품명", "전원", "Flange", "RPM/OT", "스템/부시가공", "수량"]

# 주문 정보: 확인 표 열 key → PDF 항목 이름
ORDER_FIELDS = {
    "sales_no": "판매번호",
    "order_date": "수주일",
    "business_type_raw": "사업 구분",
    "customer": "판매처",
    "final_orderer": "최종발주처 / EPC",
    "project_name": "사업명",
    "order_no": "수주번호",
    "due_date": "납기일",
    "delivery_date": "납품일 / 출장일",
    "order_doc_no": "수주서류",
    "note": "제작관련 공통사양 / 납품 관련 사항 / 비고",
}
ITEM_FIELDS = {
    "product_name": "품명",
    "quantity": "수량",
    "power": "전원",
    "flange": "Flange",
    "rpm_ot": "RPM/OT",
    "stem_bush": "스템/부시가공",
}
ORDER_KEYS = list(ORDER_FIELDS) + ["industry"]
DATE_FIELDS = ("order_date", "due_date", "delivery_date")


class SalesOrderPdfHandler(UploadHandler):
    kind = "sales_order_pdf"
    team = "production"
    allowed_extensions = (".pdf",)
    key_field = "sales_no"
    columns = [
        ("sales_no", "판매번호"),
        ("item_no", "품목 순번"),
        ("due_date", "납기일"),
        ("order_date", "수주일"),
        ("business_type_raw", "사업구분"),
        ("industry", "산업 분야"),
        ("customer", "판매처"),
        ("final_orderer", "최종발주처/EPC"),
        ("project_name", "사업명"),
        ("product_name", "품명"),
        ("quantity", "수량"),
        ("power", "전원"),
        ("flange", "Flange"),
        ("rpm_ot", "RPM/OT"),
        ("stem_bush", "스템/부시가공"),
        ("order_no", "수주번호"),
        ("order_doc_no", "수주서류 번호"),
        ("delivery_date", "납품일/출장일"),
        ("note", "비고"),
    ]

    def parse(self, file):
        rows = []
        for page_no, page in enumerate(read_pages(file), start=1):
            if page.find("판매번호") is None:
                continue
            order = {key: (page.value(label, LABELS, HEADINGS) or "").replace("\n", " ").strip()
                     for key, label in ORDER_FIELDS.items()}
            # 수주서류 "#26024 파일이름.p…" → 번호 26024만 저장
            m = re.search(r"#?\s*(\d+)", order["order_doc_no"])
            order["order_doc_no"] = m.group(1) if m else order["order_doc_no"]
            order["industry"] = to_industry(order["business_type_raw"])

            items = page.table(ITEM_HEADERS, ["합계"]) or [{}]  # 제품이 없어도 1행은 보여줌
            for item_no, item in enumerate(items, start=1):
                values = {**order, "item_no": str(item_no)}
                for key, header in ITEM_FIELDS.items():
                    values[key] = item.get(header, "")
                values["quantity"] = re.sub(r"[^\d]", "", values["quantity"])  # "1 대" → 1
                rows.append({"row_no": page_no, "sheet": f"{page_no}쪽", "values": values})
        if not rows:
            raise ValueError("'판매번호' 항목을 찾을 수 없습니다. 수주서 PDF인지 확인해 주세요.")
        return rows, 0

    def duplicate_key(self, values):
        # 같은 판매번호 안에서 품목 순번이 겹치면 "파일 안 중복"
        sales_no = (values.get("sales_no") or "").strip()
        return f"{sales_no}|{values.get('item_no', '').strip()}" if sales_no else None

    def existing_keys(self, keys):
        sales_nos = {k.split("|")[0] for k in keys}
        saved = set(SalesOrder.objects.filter(sales_no__in=sales_nos).values_list("sales_no", flat=True))
        return {k for k in keys if k.split("|")[0] in saved}

    def validate(self, values):
        errors = {}
        if not values.get("sales_no", "").strip():
            errors["sales_no"] = "판매번호가 없습니다."
        if not values.get("product_name", "").strip():
            errors["product_name"] = "품명이 없습니다."
        quantity = values.get("quantity", "").strip()
        if not quantity.isdigit() or int(quantity) == 0:
            errors["quantity"] = "수량은 1 이상의 숫자입니다."
        if values.get("industry") not in INDUSTRIES:
            errors["industry"] = f"다음 중 하나: {', '.join(INDUSTRIES)}"
        for field in DATE_FIELDS:
            try:
                if parse_iso_date(values.get(field)) is None and field == "due_date":
                    errors[field] = "납기일이 없습니다 (판매량 집계 기준)."
            except ValueError:
                errors[field] = "날짜 형식: YYYY-MM-DD"
        for key, _label in self.columns:
            if TRUNCATED in values.get(key, "") and key not in errors:
                errors[key] = "PDF에서 잘린 값(…)입니다. 전체 값으로 고쳐 주세요."
        for key, model in [(k, SalesOrder) for k in ORDER_KEYS] + [(k, SalesOrderItem) for k in ITEM_FIELDS]:
            limit = getattr(model._meta.get_field(key), "max_length", None)
            if limit and len(values.get(key, "")) > limit and key not in errors:
                errors[key] = f"{limit}자 이하로 입력해 주세요."
        return errors

    def validate_all(self, active_rows):
        """같은 판매번호의 행끼리 주문 정보가 같아야 한다 (한 수주서로 저장되므로)"""
        first = {}
        for row in active_rows:
            sales_no = row["values"].get("sales_no", "").strip()
            if not sales_no:
                continue
            if sales_no not in first:
                first[sales_no] = row["values"]
                continue
            for key in ORDER_KEYS:
                if row["values"].get(key, "").strip() != first[sales_no].get(key, "").strip():
                    row["errors"].setdefault(key, "같은 판매번호의 첫 행과 값이 다릅니다.")

    def save(self, rows, user):
        orders = {}
        for row in rows:
            v = {k: (val or "").strip() for k, val in row["values"].items()}
            if v["sales_no"] not in orders:
                fields = {k: v[k] for k in ORDER_KEYS}
                for field in DATE_FIELDS:
                    fields[field] = parse_iso_date(fields[field])
                orders[v["sales_no"]] = SalesOrder.objects.create(**fields, created_by=user)
            SalesOrderItem.objects.create(
                order=orders[v["sales_no"]],
                quantity=int(v["quantity"]),
                **{k: v[k] for k in ITEM_FIELDS if k != "quantity"},
            )
        return len(rows)
