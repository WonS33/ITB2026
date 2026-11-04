"""생산팀 지표 계산 (specs/09-metrics.md 3절)

- 기간 생산량 = 제조년월이 기간에 속하는 제조내역(일련번호) 수
- 기간 목표 생산량 = 연간 목표 ÷ 12 × 기간 개월 수 (2026-11-04 확정)
- 생산량 달성률(%) = 기간 생산량 ÷ 기간 목표 생산량 × 100
- 부족치(대) = 기간 목표 생산량 − 기간 생산량 (0보다 작으면 0)
- 월별 생산량 = 선택한 연도 1~12월 각 달의 제조내역 수, 월 목표 = 연간 목표 ÷ 12
- 연간 목표까지 남은 양 = 연간 목표 − 올해 누적 생산량, 월 평균 필요량 = 남은 양 ÷ 남은 개월 수(이번 달 포함)
- 연말 예상 생산량(예측) = 올해 누적 ÷ 1월 1일부터 오늘까지 일수 × 그 해 일수 (지금 속도가 이어진다고 가정)
- 모델별 생산량 = 기간 생산량을 제조내역 모델명별로 센 값
- 산업 분야별·거래처별·제품별 생산량(대) = 제조년월이 기간에 속하는 제조내역 수 (2026-11-04 기업 확인: 판매량 → 생산량)
  (산업 분야: PO번호와 같은 번호의 수주서에서, 못 찾으면 "수주서 미연결")
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


def _monthly_counts(year):
    return dict(
        _year_records(year)
        .annotate(m=ExtractMonth("manufactured_date"))
        .values_list("m")
        .annotate(n=Count("id"))
    )


def _monthly_orders(year):
    """월별 수주 수량 (수주서 납기일 기준 — 판매 실적 기본 기준과 같음)"""
    return dict(
        SalesOrderItem.objects.filter(order__due_date__year=year)
        .annotate(m=ExtractMonth("order__due_date"))
        .values_list("m")
        .annotate(n=Sum("quantity"))
    )


def monthly_production(year, with_last_year=False):
    """선택한 연도 1~12월 생산량 + 월 목표(연간 목표 ÷ 12, 목표가 없으면 None)

    - orders: 같은 달 수주 수량(납기일 기준). 일련번호로 잇지 않고 월 합계만 비교한다
    - last_year: 전년 같은 달 생산량 (with_last_year=True일 때만)
    """
    counts = _monthly_counts(year)
    orders = _monthly_orders(year)
    last = _monthly_counts(year - 1) if with_last_year else None
    target = AnnualProductionTarget.objects.filter(year=year).first()
    months = []
    for m in range(1, 13):
        row = {"month": m, "actual": counts.get(m, 0), "orders": orders.get(m, 0)}
        if last is not None:
            row["last_year"] = last.get(m, 0)
        months.append(row)
    return {
        "months": months,
        "monthly_target": round(target.target_quantity / 12, 1) if target else None,
    }


def production_compare(period, compare):
    """비교 기간 생산량 (판매 실적과 같은 비교 기간 규칙: previous_period)"""
    if compare == "none":
        return None
    p = previous_period(period, compare)
    previous = ManufacturingRecord.objects.filter(manufactured_date__range=(p.start, p.end)).count()
    current = ManufacturingRecord.objects.filter(manufactured_date__range=(period.start, period.end)).count()
    change = current - previous
    return {
        "label": p.label,
        "actual": previous,
        "change": change,
        "change_rate": round(change / previous * 100, 1) if previous else None,
    }


def _rate(part, whole):
    return round(part / whole * 100, 1) if whole else None


def delivery_performance(period, today=None):
    """납기 준수율 (제조내역 1행 = 1대 기준)

    - 대상: 납기일이 기간에 속하고 오늘까지 납기가 이미 온 제품 (납기 전인 제품은 빼고 건수만 안내)
    - 기한 내 출고: 출고일 ≤ 납기일 / 늦게 출고: 출고일 > 납기일 / 미출고(납기 지남): 출고일 없음
    - 준수율 = 기한 내 출고 ÷ 대상 × 100
    - 평균 지연일 = 늦은 제품의 (출고일 또는 오늘) − 납기일 평균
    """
    today = today or date.today()
    in_period = ManufacturingRecord.objects.filter(due_date__range=(period.start, period.end))
    not_due_yet = in_period.filter(due_date__gt=today).count()
    rows = list(in_period.filter(due_date__lte=today).values("model_name", "customer", "due_date", "shipped_date"))

    def classify(r):
        if r["shipped_date"] is None:
            return "open", (today - r["due_date"]).days
        if r["shipped_date"] <= r["due_date"]:
            return "on_time", 0
        return "late", (r["shipped_date"] - r["due_date"]).days

    def summarize(items):
        kinds = [classify(r) for r in items]
        on_time = sum(1 for k, _ in kinds if k == "on_time")
        delays = [d for k, d in kinds if k != "on_time"]
        return {
            "total": len(items),
            "on_time": on_time,
            "late": sum(1 for k, _ in kinds if k == "late"),
            "open": sum(1 for k, _ in kinds if k == "open"),
            "rate": _rate(on_time, len(items)),
            "avg_delay_days": round(sum(delays) / len(delays), 1) if delays else None,
        }

    def by(field):
        groups = {}
        for r in rows:
            groups.setdefault(r[field] or NO_NAME, []).append(r)
        result = [{"name": name, **summarize(items)} for name, items in groups.items()]
        # 준수율이 낮은 순 (같으면 대수가 많은 순) → 먼저 챙길 곳이 위로
        return sorted(result, key=lambda g: (g["rate"], -g["total"], g["name"]))

    return {**summarize(rows), "not_due_yet": not_due_yet, "by_model": by("model_name"), "by_customer": by("customer")}


UNSHIPPED_BUCKETS = [(0, 29, "30일 미만"), (30, 59, "30~59일"), (60, None, "60일 이상")]


def unshipped_status(today=None, oldest_limit=5):
    """미출고 현황 (오늘 기준, 기간 선택과 관계없음)

    - 대상: 오늘까지 제조됐고 출고일이 없는 제품
    - 경과일 = 오늘 − 제조년월(날짜)
    """
    today = today or date.today()
    records = ManufacturingRecord.objects.filter(manufactured_date__lte=today, shipped_date__isnull=True)
    rows = list(records.order_by("manufactured_date", "serial_full").values(
        "serial_full", "model_name", "manufactured_date", "due_date", "customer"))
    for r in rows:
        r["days"] = (today - r["manufactured_date"]).days
    buckets = []
    for low, high, label in UNSHIPPED_BUCKETS:
        n = sum(1 for r in rows if r["days"] >= low and (high is None or r["days"] <= high))
        buckets.append({"label": label, "count": n})
    by_model = {}
    for r in rows:
        name = r["model_name"] or NO_NAME
        by_model[name] = by_model.get(name, 0) + 1
    return {
        "as_of": today,
        "total": len(rows),
        "buckets": buckets,
        "by_model": [{"name": k, "quantity": v} for k, v in sorted(by_model.items(), key=lambda kv: (-kv[1], kv[0]))],
        "oldest": rows[:oldest_limit],
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


# ── 생산량 집계: 직원이 기준을 바꿔 보는 설정 (specs/09-metrics.md 3절) ──────────
# 2026-11-04 기업 확인: "판매량 집계"를 "생산량 집계"로 바꾸고 제조년월 기준으로 센다 (제조내역 1행 = 1대)
# 산업 분야는 제조내역에 없어, PO번호와 같은 번호의 수주서(수주서류 번호, 예: #26001 ↔ NTK-SO-26001)에서 가져온다

CUSTOMER_BASES = {"customer": "customer", "final_orderer": "final_orderer"}
PRODUCT_GROUPS = ("model", "series")  # 모델별(NTI-04) · 시리즈별(NTI)
COMPARES = ("none", "previous", "last_year")
NO_NAME = "(미입력)"
NO_ORDER = "수주서 미연결"  # 같은 번호의 수주서를 못 찾은 제조내역의 산업 분야


def order_key(text):
    """PO번호·수주서류 번호를 잇는 번호: 숫자만 남긴다 (#26001 → 26001, NTK-SO-26001 → 26001)"""
    return re.sub(r"\D", "", text or "")


def industry_by_po():
    """{번호: 산업 분야} — 수주서류 번호를 먼저 보고, 없으면 판매번호 끝 숫자로 잇는다"""
    mapping = {}
    for doc_no, sales_no, industry in SalesOrder.objects.order_by("-id").values_list("order_doc_no", "sales_no", "industry"):
        for key in (order_key(doc_no), order_key(sales_no.rsplit("-", 1)[-1])):
            if key:
                mapping.setdefault(key, industry)
    return mapping


def product_group(model_name, group):
    name = model_name or NO_NAME
    return name.split("-", 1)[0] if group == "series" and model_name else name


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


def production_breakdown(period, customer_basis="customer", product_group_by="model",
                         compare="none", industry="", customer="", product=""):
    """생산량 집계 (제조년월 기준, 제조내역 1행 = 1대)

    - customer_basis: 거래처를 제조내역의 거래처로 볼지 최종발주처로 볼지
    - product_group_by: 제품을 모델별·시리즈별로 묶기
    - compare: 비교 기간 (없음·직전 기간·전년 동기) → 순위마다 previous·change
    - industry·customer·product: 교차 필터. 각 순위는 "자기 자신을 뺀 나머지 필터"만 적용한다
      (예: 산업 분야를 골라도 산업 분야 순위는 전체를 보여 주고, 거래처·제품 순위가 좁혀진다)
    """
    customer_field = CUSTOMER_BASES[customer_basis]
    industries = industry_by_po()

    def rows_in(p):
        return [
            {
                "industry": industries.get(order_key(r["po_no"]), NO_ORDER),
                "customer": r[customer_field] or NO_NAME,
                "product": product_group(r["model_name"], product_group_by),
            }
            for r in ManufacturingRecord.objects.filter(manufactured_date__range=(p.start, p.end))
            .values("po_no", "model_name", customer_field)
        ]

    chosen = {"industry": industry, "customer": customer, "product": product}

    def count(rows, field):
        totals = {}
        for r in rows:
            # 자기 자신을 뺀 나머지 필터만 적용
            if all(not v or r[k] == v for k, v in chosen.items() if k != field):
                totals[r[field]] = totals.get(r[field], 0) + 1
        return totals

    periods = [period] + ([previous_period(period, compare)] if compare != "none" else [])
    results = []
    for p in periods:
        rows = rows_in(p)
        results.append({
            "total": sum(1 for r in rows if all(not v or r[k] == v for k, v in chosen.items())),
            "by_industry": count(rows, "industry"),
            "by_customer": count(rows, "customer"),
            "by_product": count(rows, "product"),
            "unlinked": sum(1 for r in rows if r["industry"] == NO_ORDER),
        })
    current = results[0]
    prev = results[1] if len(results) > 1 else None

    summary = {
        "total": current["total"],
        "by_industry": _ranking_rows(current["by_industry"], prev and prev["by_industry"]),
        "by_customer": _ranking_rows(current["by_customer"], prev and prev["by_customer"]),
        "by_product": _ranking_rows(current["by_product"], prev and prev["by_product"]),
        "unlinked": current["unlinked"],  # 수주서와 못 이은 제조내역 수 (산업 분야 "수주서 미연결")
        # 제조년월이 비어 있어 어느 기간에도 들어가지 않는 제조내역 수 (화면에 안내)
        "missing_date_records": ManufacturingRecord.objects.filter(manufactured_date__isnull=True).count(),
    }
    if prev is not None:
        p = periods[1]
        summary["compare"] = {"label": p.label, "total": prev["total"], "change": current["total"] - prev["total"]}
    return summary
