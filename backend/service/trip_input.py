"""출장보고서 1건 검사·저장 공통 규칙 (specs/06-service.md 3절)

PDF 업로드(uploads/handlers/trip_report_pdf.py)와 웹 직접 입력(POST /api/service/reports/)이 함께 쓴다.
→ 어느 쪽으로 넣어도 같은 규칙으로 검사하고 같은 모양으로 저장된다.

보고서 데이터 모양 (dict):
- 한 칸 값: start_date·end_date(YYYY-MM-DD 문자열), requester, region, district, paid_type, author 등 (문자열)
- 여러 개 값: companions(이름 목록), parts(부품명 목록),
  products([{model_name, spec, serial_no_raw, quantity}] 목록, quantity는 숫자 문자열 또는 정수)
"""

from datetime import date

from .models import RequesterRegion, TripReport, TripReportCompanion, TripReportPart, TripReportProduct
from .regions import region_errors

PAID_TYPES = ["유상", "무상"]
TRUNCATED = "…"  # PDF에서 긴 값이 잘리면 붙는 글자
SCALAR_FIELDS = [
    "start_date", "end_date", "extra_trip", "paid_type", "requester_type", "requester", "region", "district",
    "work_type", "purpose", "fault_description", "work_description", "work_result", "author",
]
DATE_FIELDS = ("start_date", "end_date")
# 글자 수 제한 (DB 칸 크기와 같음)
LIMITS = {"requester": 100, "author": 50, "purpose": 200, "work_type": 30, "requester_type": 30, "extra_trip": 50}
LIST_LIMITS = {"companions": 50, "parts": 100}
PRODUCT_LIMITS = {"model_name": 50, "spec": 100, "serial_no_raw": 50}
PRODUCT_ERROR = "제품마다 모델명과 수량(1 이상의 숫자)이 필요합니다."


def parse_date(text):
    """'YYYY-MM-DD' → date. 빈 값이면 None, 형식이 틀리면 ValueError."""
    text = (text or "").strip()
    return date.fromisoformat(text) if text else None


def clean_report(data):
    """앞뒤 공백을 지우고 빈 줄을 뺀 보고서 데이터로 정리한다."""
    clean = {key: str(data.get(key) or "").strip() for key in SCALAR_FIELDS}
    clean["companions"] = [str(n).strip() for n in data.get("companions") or [] if str(n).strip()]
    clean["parts"] = [str(n).strip() for n in data.get("parts") or [] if str(n).strip()]
    clean["products"] = []
    for p in data.get("products") or []:
        product = {key: str(p.get(key) or "").strip() for key in ("model_name", "spec", "serial_no_raw", "quantity")}
        if any(product.values()):  # 완전히 빈 줄은 무시
            clean["products"].append(product)
    return clean


def validate_report(data):
    """정리된 보고서 데이터 검사 → {칸: 메시지} (오류가 없으면 빈 dict)"""
    errors = {}
    try:
        start = parse_date(data["start_date"])
        if start is None:
            errors["start_date"] = "출장 시작일이 없습니다 (월 집계 기준)."
    except ValueError:
        start, errors["start_date"] = None, "날짜 형식: YYYY-MM-DD"
    try:
        end = parse_date(data["end_date"])
        if start and end and end < start:
            errors["end_date"] = "종료일이 시작일보다 빠릅니다."
    except ValueError:
        errors["end_date"] = "날짜 형식: YYYY-MM-DD"

    for key, message in (("requester", "요청처가 없습니다."), ("author", "작성자가 없습니다.")):
        if not data[key]:
            errors[key] = message
    errors.update(region_errors(data["region"], data["district"]))
    if data["paid_type"] not in PAID_TYPES:
        errors["paid_type"] = "유상 또는 무상을 골라 주세요."

    for p in data["products"]:
        if not p["model_name"] or not p["quantity"].isdigit() or int(p["quantity"]) == 0:
            errors["products"] = PRODUCT_ERROR
            break
        too_long = [key for key, limit in PRODUCT_LIMITS.items() if len(p[key]) > limit]
        if too_long:
            errors["products"] = "모델명 50자, 사양 100자, 일련번호 50자 이하로 입력해 주세요."
            break

    texts = {key: data[key] for key in SCALAR_FIELDS}
    texts["companions"] = "\n".join(data["companions"])
    texts["parts"] = "\n".join(data["parts"])
    texts["products"] = "\n".join(" ".join(p.values()) for p in data["products"])
    for key, text in texts.items():
        if TRUNCATED in text and key not in errors:
            errors[key] = "잘린 값(…)입니다. 전체 값으로 고쳐 주세요."
    for key, limit in LIMITS.items():
        if len(data[key]) > limit and key not in errors:
            errors[key] = f"{limit}자 이하로 입력해 주세요."
    for key, limit in LIST_LIMITS.items():
        if any(len(name) > limit for name in data[key]) and key not in errors:
            errors[key] = f"한 개당 {limit}자 이하로 입력해 주세요."
    return errors


def find_duplicates(data):
    """중복 확인 기준: 출장 시작일 + 요청처 (보고서 고유 번호가 없어서 — 기업 확인 필요)"""
    try:
        start = parse_date(data["start_date"])
    except ValueError:
        return TripReport.objects.none()
    if not start or not data["requester"]:
        return TripReport.objects.none()
    return TripReport.objects.filter(start_date=start, requester=data["requester"])


def save_report(data, user, input_method):
    """검사를 통과한 보고서 1건을 저장하고, 요청처 → 시·도·시·군을 대응표에 기억한다."""
    report = TripReport.objects.create(
        **{key: data[key] for key in SCALAR_FIELDS if key not in DATE_FIELDS},
        start_date=parse_date(data["start_date"]),
        end_date=parse_date(data["end_date"]),
        input_method=input_method,
        created_by=user,
    )
    TripReportCompanion.objects.bulk_create(TripReportCompanion(report=report, name=n) for n in data["companions"])
    TripReportProduct.objects.bulk_create(
        TripReportProduct(report=report, model_name=p["model_name"], spec=p["spec"],
                          serial_no_raw=p["serial_no_raw"], quantity=int(p["quantity"]))
        for p in data["products"]
    )
    TripReportPart.objects.bulk_create(TripReportPart(report=report, part_name=n) for n in data["parts"])
    # 다음 업로드·입력부터 시·도·시·군을 자동으로 채운다
    RequesterRegion.objects.update_or_create(
        requester=data["requester"], defaults={"region": data["region"], "district": data["district"]}
    )
    return report
