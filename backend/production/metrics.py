"""생산팀 지표 계산 (specs/09-metrics.md 3절)

- 기간 생산량 = 제조년월이 기간에 속하는 제조내역(일련번호) 수
- 기간 목표 생산량 = 연간 목표 ÷ 12 × 기간 개월 수   ← 기업 확인 전 임시 기준
- 생산량 달성률(%) = 기간 생산량 ÷ 기간 목표 생산량 × 100
- 부족치(대) = 기간 목표 생산량 − 기간 생산량 (0보다 작으면 0)
- 산업 분야별·거래처별·제품별 판매량(대) = 수주서 제품 수량 합계
  (기간 기준 날짜: 수주서 납기일 ← 기업 확인 전 임시 기준, 거래처: 수주서 판매처)
"""

from fractions import Fraction

from django.db.models import Sum

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
