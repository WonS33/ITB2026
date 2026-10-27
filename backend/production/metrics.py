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
from datetime import date
from fractions import Fraction

from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth

from .models import AnnualProductionTarget, ManufacturingRecord, SalesOrderItem


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


def _ranking(items, field):
    rows = items.values(field).annotate(quantity=Sum("quantity")).order_by("-quantity", field)
    return [{"name": r[field] or "(미입력)", "quantity": r["quantity"]} for r in rows]


def sales_summary(period):
    items = SalesOrderItem.objects.filter(order__due_date__range=(period.start, period.end))
    return {
        "total": items.aggregate(total=Sum("quantity"))["total"] or 0,
        "by_industry": _ranking(items, "order__industry"),
        "by_customer": _ranking(items, "order__customer"),
        "by_product": _ranking(items, "product_name"),
    }
