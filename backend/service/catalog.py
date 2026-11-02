"""부품 단가표와 출장지(업체)별 단가 비교 (specs/06-service.md, specs/09-metrics.md 4절)

- 뉴토크 기준값 = 단가표 기준단가 × (1 − 할인율 ÷ 100) + 추가단가 (원 단위 반올림)
  할인율·추가단가는 부품마다 따로 정할 수 있고, 비어 있으면 전체 기본값(PriceStandard)을 쓴다
- 출장지별 단가 = 그 부품(파트넘버)에 연결된 단가 중 업체(방문한 회사)마다 가장 최근 단가 1개
  (적용 시작일이 오늘 이후인 예정 단가는 뺀다. 한 업체의 견적이 여러 번이면 최근 것만 써서 한 업체가 평균을 끌지 않게)
- 평균·최저·최고·최고−최저 = 위 출장지별 단가로 계산 (평균은 원 단위 반올림)
- 기준값 대비 차이는 **견적 당시 단가표**(적용 시작일 이전 가장 최근 기준일)로 계산한다 (2026-11-02, 단가표 개정 이력)
  단가표보다 먼저 받은 견적은 가장 오래된 단가표와 비교한다. 할인율·추가단가는 이력 없이 지금 설정을 쓴다
- 크게 낮음: 기준값 대비 차이율이 −(PriceStandard.low_alert_rate)% 이하 (할인 과다 점검, 임시 10%)
"""

import csv
import io
import re
from collections import OrderedDict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import PartCatalogItem, PartPrice, PriceStandard

PART_NO_RE = re.compile(r"^[A-Z]{1,4}-\d{2}-[A-Z]-\d{2}$")  # 예: XX-05-A-01
CATEGORY_RE = re.compile(r"^\d{2}\s+\S")  # 예: "05 MOTOR"


# ── 단가표 파일 읽기 (import_part_catalog 명령) ──────────────────────


def _decode(raw):
    """엑셀에서 저장한 CSV는 UTF-8(BOM 포함) 또는 한글 윈도우 인코딩(CP949)이다"""
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949로 저장해 주세요).")


def parse_price(text):
    """' 1,234,000 ' → 1234000, '-'·빈칸 → None"""
    value = (text or "").strip().replace(",", "")
    if value in ("", "-"):
        return None
    if not value.isdigit():
        raise ValueError(f"단가를 숫자로 읽을 수 없습니다: {text!r}")
    return int(value)


def parse_catalog(raw):
    """단가표 CSV 내용(bytes) → (품목 목록, 경고 목록)

    분류 줄("05 MOTOR")은 그 아래 품목의 분류가 되고, 파트넘버 모양이 아닌 줄(제목 등)은 건너뛴다.
    """
    items, warnings, category = [], [], ""
    for line_no, row in enumerate(csv.reader(io.StringIO(_decode(raw))), start=1):
        cells = [c.strip() for c in row] + [""] * 4
        first = cells[0]
        if CATEGORY_RE.match(first) and not any(cells[1:4]):
            category = first
            continue
        if not PART_NO_RE.match(first):
            continue
        try:
            price = parse_price(cells[3])
        except ValueError as e:
            warnings.append(f"{line_no}번째 줄 {first}: {e}")
            price = None
        items.append({"line_no": line_no, "part_no": first, "category": category, "name": cells[1],
                      "applies_to": cells[2], "list_price": price})

    seen = {}
    for item in items:
        if item["part_no"] in seen:
            warnings.append(
                f"파트넘버 {item['part_no']}가 두 품목에 쓰였습니다 "
                f"({seen[item['part_no']]}번째 줄, {item['line_no']}번째 줄) - 품명으로 구분해 둘 다 넣습니다 (원본 확인 필요)"
            )
        seen.setdefault(item["part_no"], item["line_no"])
    return items, warnings


# ── 뉴토크 기준값 ────────────────────────────────────────────


def effective_settings(item, standard):
    discount = item.discount_rate if item.discount_rate is not None else standard.default_discount_rate
    extra = item.extra_price if item.extra_price is not None else standard.default_extra_price
    return Decimal(discount), extra


def standard_price(item, standard, list_price=...):
    """뉴토크 기준값 (list_price를 주지 않으면 지금 단가표 기준단가로)"""
    if list_price is ...:
        list_price = item.list_price
    if list_price is None:
        return None
    discount, extra = effective_settings(item, standard)
    value = Decimal(list_price) * (1 - discount / 100) + extra
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def list_price_on(item, day):
    """그날 적용되던 단가표 → (기준단가, 기준일). 이력이 없으면 지금 값"""
    revisions = sorted(item.list_prices.all(), key=lambda r: r.effective_date)
    if not revisions:
        return item.list_price, item.list_price_date
    before = [r for r in revisions if r.effective_date <= day]
    r = before[-1] if before else revisions[0]  # 단가표보다 먼저 받은 견적은 가장 오래된 단가표와 비교
    return r.list_price, r.effective_date


def compare_to_standard(item, standard, price):
    """업체 단가 1줄을 견적 당시 기준값과 비교 → {base_price, base_date, diff, diff_rate, low}"""
    list_price, base_date = list_price_on(item, price.effective_date)
    base = standard_price(item, standard, list_price)
    if not base:
        return {"base_price": base, "base_date": base_date, "diff": None, "diff_rate": None, "low": False}
    rate = round((price.unit_price - base) / base * 100, 1)
    return {"base_price": base, "base_date": base_date, "diff": price.unit_price - base, "diff_rate": rate,
            "low": rate <= -float(standard.low_alert_rate)}


# ── 출장지(업체)별 단가 ───────────────────────────────────────


def company_prices(item, today=None):
    """업체마다 가장 최근 단가 1개 (오늘 이후 적용 예정 단가 제외, 업체명이 빈 단가는 '(업체 미입력)')"""
    today = today or date.today()
    latest = OrderedDict()
    for p in item.prices.filter(effective_date__lte=today).order_by("effective_date", "id"):
        latest[p.quote_company or "(업체 미입력)"] = p
    return latest


def price_stats(prices):
    values = [p.unit_price for p in prices]
    if not values:
        return {"count": 0, "average": None, "min": None, "max": None, "range": None}
    average = int((Decimal(sum(values)) / len(values)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {"count": len(values), "average": average, "min": min(values), "max": max(values),
            "range": max(values) - min(values)}


def normalize(text):
    """파트넘버 검색용: 대소문자·하이픈·공백 무시 (예: 'xx-05 a' → 'XX05A')"""
    return re.sub(r"[\s-]", "", text or "").upper()


def _item_row(item, standard, today):
    discount, extra = effective_settings(item, standard)
    prices = list(company_prices(item, today).values())
    return {
        "id": item.id,
        "part_no": item.part_no,
        "category": item.category,
        "name": item.name,
        "applies_to": item.applies_to,
        "list_price": item.list_price,
        "list_price_date": item.list_price_date,
        "discount_rate": float(discount),
        "extra_price": extra,
        "custom": item.discount_rate is not None or item.extra_price is not None,  # 부품별로 따로 정했는지
        "standard_price": standard_price(item, standard),
        "stats": price_stats(prices),
    }


def catalog_table(query="", category="", today=None):
    today = today or date.today()
    standard = PriceStandard.get()
    items = PartCatalogItem.objects.prefetch_related("prices", "list_prices")
    if category:
        items = items.filter(category=category)
    q = normalize(query)

    def matches(item):
        if not q:
            return True
        number = normalize(item.part_no)
        # 숫자만 입력하면(예: 0501) 파트넘버의 숫자만 모아 비교 → 'XX-05-A-01'도 찾음
        digits_only = q.isdigit() and q in re.sub(r"\D", "", number)
        return q in number or q in normalize(item.name) or digits_only

    rows = [_item_row(i, standard, today) for i in items if matches(i)]
    return {
        "standard": {
            "default_discount_rate": float(standard.default_discount_rate),
            "default_extra_price": standard.default_extra_price,
            "low_alert_rate": float(standard.low_alert_rate),
        },
        # 단가표 기준일 (여러 날짜가 섞여 있으면 가장 최근 날짜)
        "list_price_date": PartCatalogItem.objects.exclude(list_price_date=None).order_by("-list_price_date")
        .values_list("list_price_date", flat=True).first(),
        # 순서를 지키며 중복 제거 (order_by와 distinct를 함께 쓰면 DB에서 중복이 남는다)
        "categories": list(dict.fromkeys(PartCatalogItem.objects.values_list("category", flat=True))),
        "items": rows,
    }


def catalog_detail(item, today=None):
    today = today or date.today()
    standard = PriceStandard.get()
    row = _item_row(item, standard, today)
    latest_ids = {p.id for p in company_prices(item, today).values()}

    history = []
    for p in item.prices.order_by("-effective_date", "quote_company", "-id"):
        history.append({
            "id": p.id,
            "company": p.quote_company or "(업체 미입력)",
            "unit_price": p.unit_price,
            "effective_date": p.effective_date,
            "upcoming": p.effective_date > today,
            "latest": p.id in latest_ids,  # 평균·최저·최고 계산에 쓰인 단가
            **compare_to_standard(item, standard, p),  # 견적 당시 기준값과 비교
            "source": p.get_source_display(),
            "quote_no": p.quote_no,
            "project": p.quote_project,
            "note": p.quote_note,
        })
    revisions = [
        {"effective_date": r.effective_date, "list_price": r.list_price,
         "standard_price": standard_price(item, standard, r.list_price)}
        for r in item.list_prices.order_by("-effective_date")
    ]
    return {**row, "low_alert_rate": float(standard.low_alert_rate), "revisions": revisions, "prices": history}


def catalog_choices():
    """입력 화면·견적서 확인 화면에서 고르는 목록: '파트넘버 품명 (적용 모델)'"""
    return [
        {"id": i.id, "part_no": i.part_no, "name": i.name, "applies_to": i.applies_to,
         "label": f"{i.part_no} {i.name}" + (f" ({i.applies_to})" if i.applies_to else "")}
        for i in PartCatalogItem.objects.all()
    ]


def find_catalog_item(text):
    """'XX-05-A-01 Motor …' 같은 글자에서 단가표 부품 찾기 → (부품, 오류 메시지)

    맨 앞 단어를 파트넘버로 보고, 같은 파트넘버가 여럿이면 뒤의 품명으로 고른다.
    """
    text = (text or "").strip()
    if not text:
        return None, "파트넘버를 고르거나 입력해 주세요."
    part_no, _, rest = text.partition(" ")
    matches = list(PartCatalogItem.objects.filter(part_no__iexact=part_no))
    if not matches:
        return None, f"단가표에 없는 파트넘버입니다: {part_no}"
    if len(matches) > 1:
        named = [m for m in matches if rest and rest.startswith(m.name)]
        if len(named) != 1:
            return None, f"파트넘버 {part_no}가 여러 품목에 쓰여 있습니다. 목록에서 품명까지 골라 주세요."
        matches = named
    return matches[0], None


def duplicate_price_exists(item, company, effective_date):
    return PartPrice.objects.filter(catalog_item=item, quote_company=company, effective_date=effective_date).exists()


def company_comparison(category="", today=None):
    """출장지(업체)별 비교: 업체가 견적한 부품마다 '뉴토크 기준값 대비 몇 %'를 구해 업체 단위로 모은다

    - 부품마다 그 업체의 가장 최근 단가 1개만 쓴다 (company_prices와 같은 규칙)
    - 견적 당시 단가표의 기준값과 비교하고, 기준값이 없는 부품(단가표 기준단가 '-')은 비교할 수 없어 뺀다
    - 평균 차이율 = 업체가 견적한 부품들의 차이율 단순 평균 (부품 가격 크기와 상관없이 같은 무게, 소수 첫째 자리)
    """
    today = today or date.today()
    standard = PriceStandard.get()
    items = PartCatalogItem.objects.prefetch_related("list_prices")
    if category:
        items = items.filter(category=category)

    companies = {}
    for item in items:
        for company, p in company_prices(item, today).items():
            compared = compare_to_standard(item, standard, p)  # 견적 당시 기준값
            if compared["diff_rate"] is None:
                continue
            companies.setdefault(company, []).append({
                "id": item.id, "part_no": item.part_no, "name": item.name,
                "unit_price": p.unit_price, "effective_date": p.effective_date, **compared,
            })

    rows = []
    for company, parts in companies.items():
        rates = [p["diff_rate"] for p in parts]
        rows.append({
            "company": company,
            "count": len(parts),
            "average_rate": round(sum(rates) / len(rates), 1),
            "min_rate": min(rates),
            "max_rate": max(rates),
            "above": sum(1 for r in rates if r > 0),  # 기준값보다 비싸게 받은 부품 수
            "below": sum(1 for r in rates if r < 0),  # 기준값보다 싸게 받은 부품 수
            "low": sum(1 for p in parts if p["low"]),  # 크게 낮은(할인 과다 점검) 부품 수
            "parts": sorted(parts, key=lambda p: -p["diff_rate"]),
        })
    rows.sort(key=lambda r: (-r["average_rate"], r["company"]))
    return {"low_alert_rate": float(standard.low_alert_rate), "low_count": sum(r["low"] for r in rows),
            "companies": rows}
