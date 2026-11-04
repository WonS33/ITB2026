"""경영지원 상세 지표 (조원 저장소 metrics/break-even.ts, productivity.ts, ar-receivables.ts, cash-forecast.ts 를 옮김)

- 손익분기점(BEP): 확정된 달의 금액을 합친 뒤 한 번 계산 (월별 달성률 평균 아님)
  공헌이익 = 매출 − 변동비, 달성률 = 공헌이익 ÷ 고정비 (= 매출 ÷ BEP 매출), BEP 매출 = 고정비 × 매출 ÷ 공헌이익 (원 단위 올림)
  분류: 상품·원재료 매입 = 변동비, 경비 = 고정비, 그 외 지출 = 항목 설정(고정/변동), 미분류는 고정비
- 인당 생산성: 확정된 달 합계 ÷ 직원 수 (원 단위 반올림)
- 미수금 상세: 기준월 외상매출금의 장기 미수금 + 당월 수금예정 (거래처별·수금 예정 6개월)
- 자금 수지 예측: 다음 달부터 최대 6개월, 실제 주고받는 금액(부가세 포함). 예정 = 장부, 추정 = 최근 확정 3개월 평균
"""

import calendar
from datetime import date

from .metrics import pct
from .models import LedgerEntry, MonthlyFinance

K, S = LedgerEntry.Kind, LedgerEntry.ArStatus

BEP_BASIS = [
    "매출·매입·경비(월간 입력)는 공급가액(부가세 제외) 기준입니다",
    "상품·원재료 매입액을 그달의 원가로 보고 변동비로 계산합니다",
    "경비 지출과 그 외 지출은 고정비로 계산합니다 (항목별 구분은 목표·항목 설정에서 바꿀 수 있음)",
]
CASH_BASIS = [
    "금액은 실제 주고받는 금액(부가세 포함)입니다. 월간 입력 평균은 매출·매입·그 외 지출에 ×1.1, 경비는 그대로 씁니다",
    "들어올 돈(예정) = 경영지원 관리 외상매출금 '당월 수금예정'을 예정일 달에 넣습니다. 예정일이 없거나 지났으면 첫 달로 봅니다. 장기 미수금은 넣지 않습니다",
    "나갈 돈(예정) = 외상매입금·미지급비용(직원·업체, 자동이체 포함)을 예정일 달에 넣습니다. 예정일이 비어 있으면 기준월 다음 달에 지급합니다",
    "추정 = 경영지원 관리 기준월 2달 뒤부터 최근 확정 3개월 평균입니다. 급여·세금 같은 정기 지출을 따로 넣지 않아 달마다 고르게 퍼집니다",
    "예상 잔액 = 월간 입력의 가장 최근 '월말 통장 잔액' + 누적 순수지입니다. 잔액을 넣지 않으면 수입 − 지출만 보여 드립니다",
]
FORECAST_MONTHS = 6
AVERAGE_MONTHS = 3


def _index(year, month):
    return year * 12 + month - 1


def _ym(index):
    return {"year": index // 12, "month": index % 12 + 1}


# ---------- 손익분기점 ----------


def break_even(rows, revenue):
    """rows: 확정된 MonthlyFinance 목록 (그 외 지출·항목까지 prefetch), revenue: 그 달들의 총매출"""
    items = [
        {"key": "merchandise_purchase", "label": "상품 매입", "amount": sum(r.merchandise_purchase for r in rows), "cost_class": "variable", "basis": "settings"},
        {"key": "material_purchase", "label": "원재료 매입", "amount": sum(r.material_purchase for r in rows), "cost_class": "variable", "basis": "settings"},
        {"key": "expense", "label": "경비 지출", "amount": sum(r.expense for r in rows), "cost_class": "fixed", "basis": "settings"},
    ]
    other = {}
    for r in rows:
        for e in r.other_expenses.all():
            c = e.category
            item = other.setdefault(c.id, {
                "key": str(c.id), "label": c.name, "amount": 0, "order": c.sort_order,
                "cost_class": c.cost_type or "fixed", "basis": "category" if c.cost_type else "unclassified",
            })
            item["amount"] += e.amount
    items += [{k: v for k, v in o.items() if k != "order"} for o in sorted(other.values(), key=lambda o: o["order"])]
    variable = sum(i["amount"] for i in items if i["cost_class"] == "variable")
    fixed = sum(i["amount"] for i in items if i["cost_class"] == "fixed")
    contribution = revenue - variable
    result = {
        "items": items, "revenue": revenue, "variable_cost": variable, "fixed_cost": fixed,
        "contribution": contribution, "contribution_ratio": pct(contribution, revenue),
        "unclassified_count": sum(1 for i in items if i["basis"] == "unclassified" and i["amount"]),
        "applied_basis": BEP_BASIS, "bep_revenue": None, "rate": None, "gap": None, "reason": None,
    }
    if not rows:
        return {**result, "reason": "no-data"}
    if revenue == 0:
        return {**result, "reason": "no-revenue"}
    if fixed == 0:
        return {**result, "reason": "no-fixed-cost"}
    if contribution <= 0:
        return {**result, "reason": "not-reachable"}
    bep = -(-fixed * revenue // contribution)  # 원 단위 올림
    return {**result, "bep_revenue": bep, "rate": pct(contribution, fixed), "gap": revenue - bep}


# ---------- 인당 생산성 ----------


def _round_div(a, b):
    """a ÷ b 원 단위 반올림 (적자여도 대칭)"""
    q = (abs(a) * 2 + b) // (b * 2)
    return -q if a < 0 else q


def productivity(headcount, has_data, revenue, profit):
    if not headcount:
        return {"headcount": None, "revenue_per_head": None, "profit_per_head": None, "reason": "no-headcount"}
    if not has_data:
        return {"headcount": headcount, "revenue_per_head": None, "profit_per_head": None, "reason": "no-data"}
    return {
        "headcount": headcount,
        "revenue_per_head": _round_div(revenue, headcount),
        "profit_per_head": _round_div(profit, headcount),
        "reason": None,
    }


# ---------- 미수금 상세 ----------


def receivables_detail(period, today, horizon=FORECAST_MONTHS):
    """기준월 = 기간 안(오늘이 속한 달까지) 외상매출금이 있는 마지막 달. 미수 = 장기 미수금 + 당월 수금예정"""
    limit = _index(today.year, today.month)
    entries = list(LedgerEntry.objects.filter(kind=K.AR, deleted_at__isnull=True, year=period.year, month__in=period.months))
    has = {e.month for e in entries}
    month = next((m for m in reversed(period.months) if _index(period.year, m) <= limit and m in has), None)
    if month is None:
        return {"month": None}
    end = date(period.year, month, calendar.monthrange(period.year, month)[1])
    as_of = min(end, today)
    rows = [e for e in entries if e.month == month]
    total = lambda lst: {"amount": sum(e.amount for e in lst), "count": len(lst)}  # noqa: E731
    long_overdue = [e for e in rows if e.ar_status == S.LONG_OVERDUE]
    scheduled = [e for e in rows if e.ar_status == S.SCHEDULED]
    open_rows = sorted(long_overdue + scheduled, key=lambda e: -e.amount)
    customers = {}
    for e in open_rows:
        c = customers.setdefault(e.partner_name, {"customer_name": e.partner_name, "amount": 0, "count": 0, "long_overdue": 0})
        c["amount"] += e.amount
        c["count"] += 1
        if e.ar_status == S.LONG_OVERDUE:
            c["long_overdue"] += e.amount
    # 수금 예정 (당월 수금예정 행의 예정일)
    start = _index(period.year, month)
    upcoming = [e for e in scheduled if e.due_on and e.due_on >= as_of]
    due_index = lambda e: _index(e.due_on.year, e.due_on.month)  # noqa: E731
    months = [{**_ym(start + i), **total([e for e in upcoming if due_index(e) == start + i])} for i in range(horizon)]
    return {
        "month": {"year": period.year, "month": month},
        "as_of": as_of,
        "total": sum(e.amount for e in open_rows),
        "count": len(open_rows),
        "long_overdue": total(long_overdue),
        "scheduled": total(scheduled),
        "collected": total([e for e in rows if e.ar_status == S.COLLECTED]),
        "items": [
            {"customer_name": e.partner_name, "amount": e.amount, "status": e.ar_status, "due_on": e.due_on,
             "note": e.note, "overdue": bool(e.ar_status == S.SCHEDULED and e.due_on and e.due_on < as_of)}
            for e in open_rows
        ],
        "by_customer": sorted(customers.values(), key=lambda c: (-c["amount"], c["customer_name"])),
        "expected": {
            "overdue": total([e for e in scheduled if e.due_on and e.due_on < as_of]),
            "months": months,
            "later": total([e for e in upcoming if due_index(e) > start + horizon - 1]),
            "no_due_date": total([e for e in scheduled if e.due_on is None]),
        },
    }


# ---------- 자금 수지 예측 ----------


def with_vat(amount):
    """부가세 포함 환산 ×1.1 (원 단위 반올림)"""
    return (amount * 11 + 5) // 10


def cash_forecast(today):
    """오늘 기준 (선택한 기간과 무관). 다음 달부터 FORECAST_MONTHS 개월"""
    this = _index(today.year, today.month)
    start = this + 1
    window = list(range(start, start + FORECAST_MONTHS))
    slot = lambda i: i - start  # noqa: E731
    inflow = [0] * FORECAST_MONTHS
    outflow = [0] * FORECAST_MONTHS
    zero = lambda: {"amount": 0, "count": 0}  # noqa: E731
    notes = {k: zero() for k in ("carried_inflow", "long_overdue", "past_outflow", "beyond_inflow", "beyond_outflow")}

    def add(note, amount):
        notes[note]["amount"] += amount
        notes[note]["count"] += 1

    # 경영지원 관리 기준월 B = 이번 달까지 행(숨긴 행 제외)이 있는 마지막 달
    latest = (
        LedgerEntry.objects.filter(deleted_at__isnull=True)
        .filter(year__lte=today.year)
        .exclude(year=today.year, month__gt=today.month)
        .order_by("-year", "-month")
        .first()
    )
    ledger_month = None
    if latest:
        ledger_month = {"year": latest.year, "month": latest.month}
        default_pay = _index(latest.year, latest.month) + 1
        for r in LedgerEntry.objects.filter(year=latest.year, month=latest.month, deleted_at__isnull=True):
            if r.kind == K.AR:
                if r.ar_status == S.LONG_OVERDUE:
                    add("long_overdue", r.amount)
                if r.ar_status != S.SCHEDULED:
                    continue  # 당월 수금 = 이미 들어온 돈
                due = slot(_index(r.due_on.year, r.due_on.month)) if r.due_on else None
                if due is None or due < 0:
                    add("carried_inflow", r.amount)  # 예정일이 없거나 지났으면 첫 달로
                i = max(0, due or 0)
                if i >= FORECAST_MONTHS:
                    add("beyond_inflow", r.amount)
                else:
                    inflow[i] += r.amount
                continue
            if r.settled_on:
                continue  # 이미 나간 돈
            if r.due_on:
                i = max(0, slot(_index(r.due_on.year, r.due_on.month)))  # 예정일이 지났는데 완료일이 없으면 첫 달
                if i >= FORECAST_MONTHS:
                    add("beyond_outflow", r.amount)
                else:
                    outflow[i] += r.amount
                continue
            i = slot(default_pay)
            if i < 0:
                add("past_outflow", r.amount)
            elif i >= FORECAST_MONTHS:
                add("beyond_outflow", r.amount)
            else:
                outflow[i] += r.amount

    # 추정: 최근 확정 3개월 평균 (1년 안, 이번 달까지)
    confirmed = sorted(
        (
            f for f in MonthlyFinance.objects.filter(status=MonthlyFinance.Status.CONFIRMED).prefetch_related("other_expenses")
            if this - 11 <= _index(f.year, f.month) <= this
        ),
        key=lambda f: -_index(f.year, f.month),
    )[:AVERAGE_MONTHS]
    average = None
    if confirmed:
        n = len(confirmed)
        avg = lambda values: (sum(values) * 2 + n) // (2 * n)  # noqa: E731 원 단위 반올림
        average = {
            "months": [{"year": f.year, "month": f.month} for f in reversed(confirmed)],
            "inflow": avg([with_vat(f.product_sales + f.merchandise_sales + f.service_sales) for f in confirmed]),
            "outflow": avg([
                with_vat(f.merchandise_purchase + f.material_purchase + sum(e.amount for e in f.other_expenses.all())) + f.expense
                for f in confirmed
            ]),
        }
    # 장부가 있으면 B+2 달부터 추정 (B+1 은 장부 총액으로 예정이 잡혀 있어 이중 계산 방지)
    estimate_from = _index(latest.year, latest.month) + 2 if latest else -1

    cash = (
        MonthlyFinance.objects.filter(cash_balance__isnull=False)
        .filter(year__lte=today.year)
        .exclude(year=today.year, month__gt=today.month)
        .order_by("-year", "-month")
        .first()
    )
    opening = (
        {"year": cash.year, "month": cash.month, "amount": cash.cash_balance, "gap_months": this - _index(cash.year, cash.month)}
        if cash else None
    )

    cumulative, months = 0, []
    for k, idx in enumerate(window):
        estimate = average is not None and idx >= estimate_from
        in_est = average["inflow"] if estimate else None
        out_est = average["outflow"] if estimate else None
        net = inflow[k] + (in_est or 0) - outflow[k] - (out_est or 0)
        cumulative += net
        months.append({
            **_ym(idx), "inflow_planned": inflow[k], "inflow_estimated": in_est,
            "outflow_planned": outflow[k], "outflow_estimated": out_est,
            "net": net, "cumulative": cumulative,
            "balance": opening["amount"] + cumulative if opening else None,
        })
    return {
        "as_of": today, "months": months, "ledger_month": ledger_month, "average": average,
        "opening": opening, "notes": notes, "basis": CASH_BASIS,
    }
