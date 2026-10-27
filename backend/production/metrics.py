"""생산팀 지표 계산 (specs/09-metrics.md 3절)

- 기간 생산량 = 제조년월이 기간에 속하는 제조내역(일련번호) 수
- 기간 목표 생산량 = 연간 목표 ÷ 12 × 기간 개월 수   ← 기업 확인 전 임시 기준
- 생산량 달성률(%) = 기간 생산량 ÷ 기간 목표 생산량 × 100
- 부족치(대) = 기간 목표 생산량 − 기간 생산량 (0보다 작으면 0)
- 월별 생산량 = 선택한 연도 1~12월 각 달의 제조내역 수, 월 목표 = 연간 목표 ÷ 12 (임시 기준)
- 연간 목표까지 남은 양 = 연간 목표 − 올해 누적 생산량, 월 평균 필요량 = 남은 양 ÷ 남은 개월 수(이번 달 포함)
- 연말 예상 생산량(예측) = 올해 누적 ÷ 1월 1일부터 오늘까지 일수 × 그 해 일수 (지금 속도가 이어진다고 가정)
- 모델별 생산량 = 기간 생산량을 제조내역 모델명별로 센 값
- 산업 분야별·거래처별·제품별 판매량(대) = 수주서 제품 수량 합계
  (기간 기준 날짜: 수주서 납기일 ← 기업 확인 전 임시 기준, 거래처: 수주서 판매처)
"""

import calendar
import re
from datetime import date
from fractions import Fraction

from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth

from common.periods import make_period, quarter_of

from .models import AnnualProductionTarget, ManufacturingRecord, SalesOrder, SalesOrderItem


def production_summary(period):
    actual = ManufacturingRecord.objects.filter(
        manufactured_date__range=(period.start, period.end)
    ).count()

    target = AnnualProductionTarget.objects.filter(year=period.year).first()
    if target is None:
        # 연간 목표가 없으면 달성률·부족치를 계산하지 않는다
        return {
            "actual": actual,
            "annual_target": None,
            "period_target": None,
            "achievement_rate": None,
            "shortfall": None,
        }

    # 분수(Fraction)로 정확히 계산한 뒤 화면 표시용으로 소수 첫째 자리에서 반올림한다
    period_target = Fraction(target.target_quantity * period.month_count, 12)
    rate = round(float(actual / period_target * 100), 1) if period_target else None
    shortfall = max(period_target - actual, 0)
    return {
        "actual": actual,
        "annual_target": target.target_quantity,
        "period_target": round(float(period_target), 1),
        "achievement_rate": rate,
        "shortfall": round(float(shortfall), 1),
    }


def _year_records(year):
    return ManufacturingRecord.objects.filter(manufactured_date__year=year)


def monthly_production(year):
    """선택한 연도 1~12월 생산량 + 월 목표(연간 목표 ÷ 12, 목표가 없으면 None)"""
    counts = dict(
        _year_records(year)
        .annotate(m=ExtractMonth("manufactured_date"))
        .values_list("m")
        .annotate(n=Count("id"))
    )
    target = AnnualProductionTarget.objects.filter(year=year).first()
    return {
        "months": [{"month": m, "actual": counts.get(m, 0)} for m in range(1, 13)],
        "monthly_target": round(target.target_quantity / 12, 1) if target else None,
    }


def year_progress(year, today=None):
    """연간 목표까지 남은 양과 연말 예상 생산량.

    - 지난 해: 1년이 끝났으므로 남은 개월·필요량·예측 없이 최종 결과만
    - 올해: 오늘까지 누적, 남은 개월 수는 이번 달 포함 (10월이면 10·11·12월 → 3개월)
    - 앞으로 올 해: 누적 0, 남은 12개월, 예측 없음
    """
    today = today or date.today()
    target = AnnualProductionTarget.objects.filter(year=year).first()
    annual = target.target_quantity if target else None
    if year < today.year:
        cumulative, remaining_months = _year_records(year).count(), 0
    elif year == today.year:
        cumulative = _year_records(year).filter(manufactured_date__lte=today).count()
        remaining_months = 12 - today.month + 1
    else:
        cumulative, remaining_months = 0, 12

    remaining = max(annual - cumulative, 0) if annual is not None else None
    required = round(remaining / remaining_months, 1) if remaining is not None and remaining_months else None

    forecast = None
    if year == today.year:
        days_passed = (today - date(year, 1, 1)).days + 1
        days_in_year = 366 if calendar.isleap(year) else 365
        forecast = round(cumulative / days_passed * days_in_year)

    return {
        "year": year,
        "is_current_year": year == today.year,
        "annual_target": annual,
        "cumulative": cumulative,
        "as_of": min(today, date(year, 12, 31)) if year <= today.year else None,
        "remaining": remaining,
        "remaining_months": remaining_months,
        "required_per_month": required,
        "forecast": forecast,
    }


def production_by_model(period):
    rows = (
        ManufacturingRecord.objects.filter(manufactured_date__range=(period.start, period.end))
        .values("model_name")
        .annotate(quantity=Count("id"))
        .order_by("-quantity", "model_name")
    )
    return [{"name": r["model_name"] or "(미입력)", "quantity": r["quantity"]} for r in rows]


def model_names():
    names = ManufacturingRecord.objects.exclude(model_name="").order_by().values_list("model_name", flat=True).distinct()
    return sorted(names)


# ── 판매 실적: 직원이 기준을 바꿔 보는 설정 (specs/09-metrics.md 3절) ──────────

# 기간을 셀 기준 날짜 (수주서의 어느 날짜로 기간에 넣을지)
DATE_BASES = {"due": "order__due_date", "order": "order__order_date", "delivery": "order__delivery_date"}
# 거래처 기준
CUSTOMER_BASES = {"customer": "order__customer", "final_orderer": "order__final_orderer"}
PRODUCT_GROUPS = ("name", "model", "size", "type")
COMPARES = ("none", "previous", "last_year")
OTHER_FORMAT = "기타(형식 다름)"
NO_NAME = "(미입력)"

# 품명 형식 "제수 150A: NTI-03" = 종류 구경: 모델 (확인 필요 — 형식이 다르면 "기타(형식 다름)")
PRODUCT_NAME_RE = re.compile(r"^\s*(?P<type>\S+)\s+(?P<size>\d+A)\s*:\s*(?P<model>\S+)\s*$")


def product_group(name, group):
    if group == "name":
        return name or NO_NAME
    m = PRODUCT_NAME_RE.match(name or "")
    return m.group(group) if m else OTHER_FORMAT



def previous_period(period, compare):
    """비교 기간: previous = 바로 앞 기간(전월·전 분기·전년), last_year = 전년 같은 기간"""
    if compare == "last_year" or period.kind == "year":
        return make_period(period.kind, period.year - 1, month=period.months[0], quarter=quarter_of(period.months[0]))
    if period.kind == "month":
        year, month = (period.year - 1, 12) if period.months[0] == 1 else (period.year, period.months[0] - 1)
        return make_period("month", year, month=month)
    quarter = quarter_of(period.months[0])
    year, quarter = (period.year - 1, 4) if quarter == 1 else (period.year, quarter - 1)
    return make_period("quarter", year, quarter=quarter)


def _grouped(items, field, group=None):
    """품목 → {이름: 수량} (제품은 묶음 단위로 다시 합친다)"""
    totals = {}
    for row in items.values(field).annotate(quantity=Sum("quantity")):
        name = product_group(row[field], group) if group else (row[field] or NO_NAME)
        totals[name] = totals.get(name, 0) + row["quantity"]
    return totals


def _ranking_rows(current, previous):
    rows = [
        {
            "name": name,
            "quantity": quantity,
            "previous": None if previous is None else previous.get(name, 0),
            "change": None if previous is None else quantity - previous.get(name, 0),
        }
        for name, quantity in current.items()
    ]
    return sorted(rows, key=lambda r: (-r["quantity"], r["name"]))


def sales_summary(period, date_basis="due", customer_basis="customer", product_group_by="name",
                  compare="none", industry="", customer="", product=""):
    """판매 실적 (수주서 제품 수량)

    - date_basis: 기간에 넣을 날짜 (납기일·수주일·납품일)
    - customer_basis: 거래처를 판매처로 볼지 최종발주처로 볼지
    - product_group_by: 제품을 품명 그대로·모델·구경·종류로 묶기
    - compare: 비교 기간 (없음·직전 기간·전년 동기) → 순위마다 previous·change
    - industry·customer·product: 교차 필터. 각 순위는 "자기 자신을 뺀 나머지 필터"만 적용한다
      (예: 산업 분야를 골라도 산업 분야 순위는 전체를 보여 주고, 거래처·제품 순위가 좁혀진다)
    """
    date_field = DATE_BASES[date_basis]
    customer_field = CUSTOMER_BASES[customer_basis]

    def items_in(p):
        return SalesOrderItem.objects.filter(**{f"{date_field}__range": (p.start, p.end)})

    def apply(items, skip=None):
        if industry and skip != "industry":
            items = items.filter(order__industry=industry)
        if customer and skip != "customer":
            items = items.filter(**{customer_field: "" if customer == NO_NAME else customer})
        if product and skip != "product":
            names = {n for n in items.values_list("product_name", flat=True).distinct()
                     if product_group(n, product_group_by) == product}
            items = items.filter(product_name__in=names)
        return items

    periods = [period] + ([previous_period(period, compare)] if compare != "none" else [])
    results = []
    for p in periods:
        base = items_in(p)
        results.append({
            "total": apply(base).aggregate(total=Sum("quantity"))["total"] or 0,
            "by_industry": _grouped(apply(base, "industry"), "order__industry"),
            "by_customer": _grouped(apply(base, "customer"), customer_field),
            "by_product": _grouped(apply(base, "product"), "product_name", product_group_by),
        })
    current = results[0]
    prev = results[1] if len(results) > 1 else None

    # 고른 날짜가 비어 있어 이 기준으로는 셀 수 없는 수주서 수 (화면에 안내)
    missing = SalesOrder.objects.filter(**{f"{date_field[len('order__'):]}__isnull": True}).count()

    summary = {
        "total": current["total"],
        "by_industry": _ranking_rows(current["by_industry"], prev and prev["by_industry"]),
        "by_customer": _ranking_rows(current["by_customer"], prev and prev["by_customer"]),
        "by_product": _ranking_rows(current["by_product"], prev and prev["by_product"]),
        "missing_date_orders": missing,
    }
    if prev is not None:
        p = periods[1]
        summary["compare"] = {"label": p.label, "total": prev["total"], "change": current["total"] - prev["total"]}
    return summary
