"""유상 A/S 견적서 PDF 업로드 → 부품 단가 (specs/06-service.md)

샘플에서 확인한 양식 (2026-10-26)
- 위쪽 표: 항목 이름 **오른쪽**에 값이 있다 (예: "견적 번호 | NTK-…", "날 짜 | 2026-08-14").
  항목 이름 글자 사이에 공백이 들어 있어("날       짜") 공백을 빼고 비교한다.
- 품목 표: 번호 | 품명 및 규격 | 수량 | 단가(원) | 금액(원). 머리글이 칸 가운데 정렬이라
  숫자 3칸(수량·단가·금액)은 머리글과 가장 가까운 칸으로, 그 왼쪽 글자는 번호·품명으로 나눈다.
- 1페이지 = 견적서 1건. 품목 1줄 = 확인 표 1행 = 부품 단가 1줄

저장 규칙
- 단가 = 단가(원) 칸 (부가세 제외), 적용 시작일 = 견적서 날짜
- 견적서 품명 → 부품명: 대응표(QuotePartAlias)에 있으면 자동으로 채우고, 없으면 확인 화면에서 고른다(기억함)
- 중복 기준: 견적 번호 + 견적서 품명 (같은 견적서를 두 번 올려도 한 번만 저장)
- 견적 단가는 출장 거리·작업 강도 등에 따라 달라질 수 있어, 이유를 참고할 수 있게
  업체명(방문한 회사)·사업명·비고(사업명 아래 칸 + 아래쪽 비고 칸)를 함께 저장한다 (2026-10-26)
- 수신자·담당자·연락처는 읽지 않는다 (개인정보)
"""

import re
from datetime import date

from service.models import PartPrice, QuotePartAlias, TripReportPart

from .base import UploadHandler
from .pdf_form import TRUNCATED, read_pages

ITEM_HEADERS = ["번호", "품명및규격", "수량", "단가(원)", "금액(원)"]
NUMBER_HEADERS = ["수량", "단가(원)", "금액(원)"]
TABLE_END = ["납기", "공급가액", "총량"]
# 위쪽 표의 항목 이름 (값을 읽을 때 오른쪽 다음 항목 이름에서 멈춘다)
HEADER_LABELS = {"견적번호", "날짜", "업체명", "수신자", "합계금액", "등록번호", "상호", "대표", "주소", "업태", "종목",
                 "전화번호", "팩스번호", "사업명", "비고"}


def compact(text):
    return re.sub(r"\s+", "", text or "")


def to_int(text):
    """'800,000' → 800000. 숫자가 아니면 None"""
    digits = re.sub(r"[,\s원]", "", text or "")
    return int(digits) if digits.isdigit() else None


def find_label(page, label):
    return next((w for w in page.words if compact(w.text) == label), None)


def value_right_of(page, label):
    """항목 이름과 같은 줄, 오른쪽 글자 (오른쪽에 다음 항목 이름이 나오면 그 앞까지)"""
    found = find_label(page, label)
    if found is None:
        return ""
    same_line = sorted((w for w in page.words if abs(w.top - found.top) < 3 and w.x0 > found.x1), key=lambda w: w.x0)
    texts = []
    for w in same_line:
        if compact(w.text) in HEADER_LABELS:
            break
        texts.append(w.text.strip())
    return " ".join(texts)


def bottom_note(page):
    """아래쪽 큰 비고 칸: 왼쪽에 '비'·'고'가 세로로 따로 적혀 있고, 그 오른쪽이 내용이다"""
    bi = next((w for w in page.words if w.text.strip() == "비"), None)
    go = next((w for w in page.words if w.text.strip() == "고" and bi and w.top > bi.top), None)
    if bi is None or go is None:
        return ""
    top, bottom, left = bi.top - 15, go.bottom + 15, max(bi.x1, go.x1) + 5
    words = [w for w in page.words if top <= w.top <= bottom and w.x0 > left and not w.text.startswith("『")]
    return "\n".join(page._lines(words))


def read_items(page):
    """품목 표 → [{"item": 품명, "quantity": "1", "unit_price": "800,000", "amount": "800,000"}]"""
    headers = {compact(w.text): w for w in page.words if compact(w.text) in ITEM_HEADERS}
    if any(h not in headers for h in ITEM_HEADERS):
        return None
    top = headers["번호"].top
    ends = [w.top for w in page.words if w.top > top + 1 and compact(w.text) in TABLE_END]
    bottom = min(ends, default=page.height + 1)
    centers = {name: (headers[name].x0 + headers[name].x1) / 2 for name in NUMBER_HEADERS}
    number_left = headers["수량"].x0 - 20  # 이보다 오른쪽은 숫자 칸
    no_right = headers["번호"].x1 + 5  # 이보다 왼쪽에서 끝나면 번호 칸

    body = sorted((w for w in page.words if top + 1 < w.top < bottom), key=lambda w: (round(w.top), w.x0))
    lines = []
    for w in body:
        if lines and abs(lines[-1][0] - w.top) < 1.5:
            lines[-1][1].append(w)
        else:
            lines.append((w.top, [w]))

    items = []
    for _top, words in lines:
        row = {"no": "", "item": [], "quantity": "", "unit_price": "", "amount": ""}
        for w in words:
            if w.x0 >= number_left:
                name = min(centers, key=lambda n: abs((w.x0 + w.x1) / 2 - centers[n]))
                row[{"수량": "quantity", "단가(원)": "unit_price", "금액(원)": "amount"}[name]] = w.text.strip()
            elif w.x1 <= no_right:
                row["no"] = w.text.strip()
            else:
                row["item"].append(w.text.strip())
        item = " ".join(row["item"])
        if not row["no"] and items and item and not row["unit_price"]:
            items[-1]["item"] += " " + item  # 품명이 두 줄로 넘어간 경우
        elif item or row["unit_price"]:
            items.append({"item": item, "quantity": row["quantity"], "unit_price": row["unit_price"],
                          "amount": row["amount"]})
    return items


class QuotePdfHandler(UploadHandler):
    kind = "quote_pdf"
    team = "service"
    allowed_extensions = (".pdf",)
    key_field = "quote_item"  # 오류 메시지를 붙일 칸 (실제 기준은 견적 번호 + 견적서 품명)
    columns = [
        ("quote_no", "견적 번호"),
        ("effective_date", "적용 시작일(견적 날짜)"),
        ("quote_item", "견적서 품명"),
        ("part_name", "부품명(출장보고서와 같은 이름)", {"suggestions": "part_names"}),
        ("unit_price", "단가(원, 부가세 제외)"),
        ("quantity", "수량"),
        ("amount", "금액(원)"),
        ("quote_company", "업체명(방문한 회사)"),
        ("quote_project", "사업명"),
        ("quote_note", "비고(단가가 달라진 이유 등)", {"multiline": True}),
    ]

    def suggestions(self):
        """확인 화면의 추천 목록: 출장보고서에 나온 부품명 + 이미 단가가 있는 부품명"""
        names = set(TripReportPart.objects.values_list("part_name", flat=True))
        names |= set(PartPrice.objects.values_list("part_name", flat=True))
        return {"part_names": sorted(names)}

    def parse(self, file):
        aliases = dict(QuotePartAlias.objects.values_list("quote_item", "part_name"))
        rows = []
        for page_no, page in enumerate(read_pages(file), start=1):
            quote_no = value_right_of(page, "견적번호")
            items = read_items(page)
            if not quote_no or items is None:
                continue
            quote_date = value_right_of(page, "날짜")
            context = {
                "quote_company": value_right_of(page, "업체명"),
                "quote_project": value_right_of(page, "사업명"),
                "quote_note": "\n".join(t for t in (value_right_of(page, "비고"), bottom_note(page)) if t),
            }
            for item in items:
                rows.append({
                    "row_no": len(rows) + 1,
                    "sheet": f"{page_no}쪽",
                    "values": {
                        "quote_no": quote_no,
                        "effective_date": quote_date,
                        "quote_item": item["item"],
                        "part_name": aliases.get(item["item"], ""),
                        "unit_price": item["unit_price"],
                        "quantity": item["quantity"],
                        "amount": item["amount"],
                        **context,
                    },
                })
        if not rows:
            raise ValueError("'견적 번호'와 품목 표를 찾을 수 없습니다. 유상 A/S 견적서 PDF인지 확인해 주세요.")
        return rows, 0

    def duplicate_key(self, values):
        parts = [(values.get(k) or "").strip() for k in ("quote_no", "quote_item")]
        return "|".join(parts) if all(parts) else None

    def existing_keys(self, keys):
        found = set()
        for key in keys:
            quote_no, item = key.split("|", 1)
            if PartPrice.objects.filter(quote_no=quote_no, quote_item=item).exists():
                found.add(key)
        return found

    def validate(self, values):
        errors = {}
        v = {k: (values.get(k) or "").strip() for k, *_ in self.columns}
        if not v["quote_no"]:
            errors["quote_no"] = "견적 번호가 없습니다."
        try:
            effective = date.fromisoformat(v["effective_date"])
        except ValueError:
            effective, errors["effective_date"] = None, "날짜 형식: YYYY-MM-DD"
        if not v["quote_item"]:
            errors["quote_item"] = "견적서 품명이 없습니다."
        if not v["part_name"]:
            errors["part_name"] = "연결할 부품명을 고르거나 입력해 주세요."
        elif len(v["part_name"]) > 100:
            errors["part_name"] = "100자 이하로 입력해 주세요."
        elif effective and PartPrice.objects.filter(part_name=v["part_name"], effective_date=effective).exists():
            errors["part_name"] = f"이 부품은 {effective} 단가가 이미 있습니다. 부품 단가 화면에서 확인해 주세요."

        price, qty, amount = to_int(v["unit_price"]), to_int(v["quantity"]), to_int(v["amount"])
        if price is None:
            errors["unit_price"] = "단가를 숫자로 입력해 주세요 (원 단위)."
        if qty is None or qty == 0:
            errors["quantity"] = "수량은 1 이상의 숫자입니다."
        if price is not None and qty and amount is not None and price * qty != amount:
            errors["amount"] = f"수량 × 단가({price * qty:,})가 금액과 다릅니다. PDF를 확인해 주세요."
        for key, limit in (("quote_company", 100), ("quote_project", 200)):
            if len(v[key]) > limit:
                errors[key] = f"{limit}자 이하로 입력해 주세요."
        for key in ("quote_no", "quote_item", "part_name"):
            if TRUNCATED in v[key] and key not in errors:
                errors[key] = "잘린 값(…)입니다. 전체 값으로 고쳐 주세요."
        return errors

    def validate_all(self, active_rows):
        """같은 파일 안에서 같은 부품·같은 날짜가 두 번 나오면 단가 이력이 겹치므로 오류"""
        seen = {}
        for row in active_rows:
            key = ((row["values"].get("part_name") or "").strip(), (row["values"].get("effective_date") or "").strip())
            if not all(key):
                continue
            if key in seen and "part_name" not in row["errors"]:
                row["errors"]["part_name"] = f"이 파일의 {seen[key]}번째 줄과 같은 부품·같은 날짜입니다. 하나만 남겨 주세요."
            seen.setdefault(key, row["row_no"])

    def save(self, rows, user):
        for row in rows:
            v = {k: (val or "").strip() for k, val in row["values"].items()}
            PartPrice.objects.create(
                part_name=v["part_name"],
                unit_price=to_int(v["unit_price"]),
                effective_date=date.fromisoformat(v["effective_date"]),
                source=PartPrice.Source.QUOTE,
                quote_no=v["quote_no"],
                quote_item=v["quote_item"],
                quote_company=v.get("quote_company", ""),
                quote_project=v.get("quote_project", ""),
                quote_note=v.get("quote_note", ""),
                created_by=user,
            )
            # 확인 화면에서 고른 부품명을 기억 → 다음 견적서부터 자동으로 채움
            QuotePartAlias.objects.update_or_create(quote_item=v["quote_item"], defaults={"part_name": v["part_name"]})
        return len(rows)
