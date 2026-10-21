"""출장보고서 PDF 업로드 규칙 (specs/06-service.md 3절)

- PDF 1페이지 = 보고서 1건 = 확인 표 1행
- 여러 개인 값은 한 칸에 줄바꿈으로 나눠 넣는다: 동행자, 교체 부품, 제품 목록("모델명 | 사양 | 일련번호 | 수량")
- 요청처 → 시·도·시·군: 대응표(RequesterRegion)에 있으면 자동으로 채우고, 없으면 확인 화면에서 고른다.
  시·군 목록은 고른 시·도에 따라 바뀐다 (특별·광역시·세종시는 시·군 없음). 저장할 때 고른 값을 대응표에 기억한다.
- 잘린 값(…)은 오류로 표시해 사람이 고치게 한다 (부품명·요청처 등)
- 검사·저장 규칙은 웹 직접 입력과 같다 → service/trip_input.py (확인 표 한 행을 보고서 데이터로 바꿔 넘긴다)
- 중복 확인 기준: 출장 시작일 + 요청처 (보고서 고유 번호가 없어서 — 기업 확인 필요)
  같은 날 같은 곳에 실제로 두 번 간 경우, 확인 화면에서 "중복 아님"을 체크하면 저장할 수 있다
"""

import re

from service.models import RequesterRegion, TripReport
from service.regions import DISTRICTS, REGIONS
from service.trip_input import PAID_TYPES, clean_report, save_report, validate_report

from .base import UploadHandler, parse_iso_date
from .pdf_form import read_pages

LABELS = [
    "요청처 구분", "출장 시작일", "작성일", "요청처(검색불가시)", "요청처", "출장 종료일", "작성자", "현장담당자 / 연락처",
    "추가 출장", "해피콜 예정일", "동행자", "작업 구분", "출장 목적", "고장 내용", "작업 내용", "작업 결과", "명판 사진",
    "작업 전 사진", "작업 후 사진", "부품 교체 전 사진", "부품 교체 후 사진", "관련 자료 (판넬 도면 등)", "비용청구 유무",
    "견적서 구분", "승인자", "부품 사용 내역", "견적서", "참조자",
]
HEADINGS = ["출장정보", "작업 개요", "제품 목록", "수리 내역", "비고"]
PRODUCT_HEADERS = ["모델명", "사양", "일련번호", "수량"]

TEXT_FIELDS = {
    "requester_type": "요청처 구분",
    "start_date": "출장 시작일",
    "end_date": "출장 종료일",
    "extra_trip": "추가 출장",
    "author": "작성자",
    "work_type": "작업 구분",
    "purpose": "출장 목적",
    "paid_type": "비용청구 유무",
}
LONG_FIELDS = {"fault_description": "고장 내용", "work_description": "작업 내용", "work_result": "작업 결과"}


def split_lines(text):
    return [line.strip() for line in re.split(r"[\n,]", text or "") if line.strip()]


def parse_product_line(line):
    """'모델명 | 사양 | 일련번호 | 수량' → dict (빈 칸 허용)"""
    parts = [p.strip() for p in line.split("|")]
    parts += [""] * (4 - len(parts))
    return {"model_name": parts[0], "spec": parts[1], "serial_no_raw": parts[2], "quantity": re.sub(r"[^\d]", "", parts[3])}


class TripReportPdfHandler(UploadHandler):
    kind = "trip_report_pdf"
    team = "service"
    allowed_extensions = (".pdf",)
    key_field = "start_date"  # 오류 메시지를 붙일 칸 (실제 기준은 시작일+요청처)
    allow_duplicate_override = True
    columns = [
        ("start_date", "출장 시작일"),
        ("end_date", "출장 종료일"),
        ("requester", "요청처"),
        ("region", "시·도", {"choices": REGIONS}),
        # 시·군 목록은 같은 행의 시·도에 따라 바뀐다 (목록이 없는 시·도는 빈 값)
        ("district", "시·군", {"choices_by": "region", "choices_map": DISTRICTS}),
        ("paid_type", "비용청구", {"choices": PAID_TYPES}),
        ("author", "작성자"),
        ("companions", "동행자(줄마다 1명)", {"multiline": True}),
        ("products", "제품(모델명 | 사양 | 일련번호 | 수량)", {"multiline": True}),
        ("parts", "교체 부품(줄마다 1개)", {"multiline": True}),
        ("work_type", "작업 구분"),
        ("requester_type", "요청처 구분"),
        ("extra_trip", "추가 출장"),
        ("purpose", "출장 목적"),
        ("fault_description", "고장 내용", {"multiline": True}),
        ("work_description", "작업 내용", {"multiline": True}),
        ("work_result", "작업 결과", {"multiline": True}),
    ]

    def parse(self, file):
        rows = []
        known = {r: (region, district) for r, region, district
                 in RequesterRegion.objects.values_list("requester", "region", "district")}
        for page_no, page in enumerate(read_pages(file), start=1):
            if page.find("출장 시작일") is None:
                continue
            value = lambda label: page.value(label, LABELS, HEADINGS) or ""
            values = {key: value(label).replace("\n", " ").strip() for key, label in TEXT_FIELDS.items()}
            values.update({key: value(label).strip() for key, label in LONG_FIELDS.items()})
            # 요청처: "검색 불가"이면 직접 적은 칸, 아니면 요청처 칸
            values["requester"] = (value("요청처(검색불가시)") or value("요청처")).replace("\n", " ").strip()
            values["region"], values["district"] = known.get(values["requester"], ("", ""))
            values["companions"] = "\n".join(split_lines(value("동행자")))
            values["parts"] = "\n".join(line.strip() for line in value("부품 사용 내역").split("\n") if line.strip())
            products = page.table(PRODUCT_HEADERS, ["수리 내역"])
            values["products"] = "\n".join(
                " | ".join([p["모델명"], p["사양"], p["일련번호"], re.sub(r"[^\d]", "", p["수량"])]) for p in products
            )
            rows.append({"row_no": page_no, "sheet": f"{page_no}쪽", "values": values})
        if not rows:
            raise ValueError("'출장 시작일' 항목을 찾을 수 없습니다. 출장보고서 PDF인지 확인해 주세요.")
        return rows, 0

    def duplicate_key(self, values):
        parts = [(values.get(k) or "").strip() for k in ("start_date", "requester")]
        return "|".join(parts) if all(parts) else None

    def existing_keys(self, keys):
        found = set()
        for key in keys:
            start, requester = key.split("|", 1)
            try:
                start_date = parse_iso_date(start)
            except ValueError:
                continue
            if TripReport.objects.filter(start_date=start_date, requester=requester).exists():
                found.add(key)
        return found

    def validate(self, values):
        return validate_report(to_report_data(values))

    def save(self, rows, user):
        for row in rows:
            save_report(to_report_data(row["values"]), user, TripReport.InputMethod.PDF)
        return len(rows)


def to_report_data(values):
    """확인 표 한 행(여러 개 값은 줄바꿈으로 나뉜 글자) → 공통 보고서 데이터"""
    data = {key: values.get(key) for key in values if key not in ("companions", "parts", "products")}
    data["companions"] = split_lines(values.get("companions"))
    data["parts"] = split_lines_keep(values.get("parts"))
    data["products"] = [parse_product_line(line) for line in split_lines_keep(values.get("products"))]
    return clean_report(data)


def split_lines_keep(text):
    """줄바꿈으로만 나눈다 (부품명·제품 줄에는 쉼표가 들어갈 수 있음)"""
    return [line.strip() for line in (text or "").split("\n") if line.strip()]
