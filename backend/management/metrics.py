"""경영지원 지표 (조원 저장소 metrics/*.ts 를 옮김) — 대시보드·목표 대비 실적 엑셀이 같이 쓴다

- 확정(confirmed)된 달만 집계한다. 마감됐는데 확정 안 된 달은 "미확정", 이번 달·미래는 "마감 전"으로 따로 알려 준다
- 총매출 = 제품 + 상품 + 용역 / 매입·지출 합계 = 상품 매입 + 원재료 매입 + 경비 + 그 외 지출
- 간이 이익 = 총매출 − 매입·지출 합계 (= specs/09 총매출 − 총매입 − 총지출), 간이 이익률 = 간이 이익 ÷ 총매출
- 비교: 직전 기간(전월·전분기·전년) + 전년 동기. 현재 기간에 확정 안 된 달이 있으면 같은 순서의 달끼리만 비교
- 비율은 % (소수 첫째 자리), 계산할 수 없으면 None
"""

from django.utils import timezone

from common.periods import make_period, quarter_of

from .models import AnnualSalesTarget, LedgerEntry, MonthlyFinance
from .targets import allocate_month_targets, allocate_quarter_targets

TREND_MONTHS = 12
COLLECTION_MONTHS = 6  # 수금 예정을 보여 줄 개월 수

REVENUE_ITEMS = [("product_sales", "제품"), ("merchandise_sales", "상품"), ("service_sales", "용역")]
COST_ITEMS = [("merchandise_purchase", "상품 매입"), ("material_purchase", "원재료 매입"), ("expense", "경비")]
OTHER_KEY, OTHER_LABEL = "other_expense", "그 외 지출"


def pct(part, whole):
    return None if not whole else round(part / whole * 100, 1)


def _index(year, month):
    return year * 12 + month - 1


def _ym(index):
    return {"year": index // 12, "month": index % 12 + 1}


def period_months(period):
    return [{"year": period.year, "month": m} for m in period.months]


def previous_period(period):
    if period.kind == "year":
        return make_period("year", period.year - 1)
    if period.kind == "month":
        ym = _ym(_index(period.year, period.months[0]) - 1)
        return make_period("month", ym["year"], month=ym["month"])
    quarter = quarter_of(period.months[0])
    year, quarter = (period.year - 1, 4) if quarter == 1 else (period.year, quarter - 1)
    return make_period("quarter", year, quarter=quarter)


def same_period_last_year(period):
    return make_period(period.kind, period.year - 1, month=period.months[0], quarter=quarter_of(period.months[0]))


def load_finance(indexes):
    """월 번호 목록 → {월 번호: MonthlyFinance} (그 외 지출 항목까지 함께)"""
    years = {i // 12 for i in indexes}
    rows = (
        MonthlyFinance.objects.filter(year__in=years)
        .prefetch_related("other_expenses__category")
    )
    wanted = set(indexes)
    return {_index(f.year, f.month): f for f in rows if _index(f.year, f.month) in wanted}


# ---------- 기간 하나 ----------


def select_confirmed(months, finance, today):
    """확정된 달만 고르고, 미확정·마감 전 달을 함께 돌려준다"""
    current = _index(today.year, today.month)
    confirmed, unconfirmed, pending = [], [], []
    for ym in months:
        i = _index(ym["year"], ym["month"])
        row = finance.get(i)
        if row and row.status == MonthlyFinance.Status.CONFIRMED:
            confirmed.append(row)
        elif i >= current:
            pending.append(ym)
        else:
            unconfirmed.append({**ym, "reason": "draft" if row else "missing"})
    return confirmed, {
        "confirmed_months": [{"year": r.year, "month": r.month} for r in confirmed],
        "unconfirmed_months": unconfirmed,
        "pending_months": pending,
        "is_partial": bool(unconfirmed),
        "has_data": bool(confirmed),
    }


def _revenue(rows):
    items = [{"key": k, "label": label, "amount": sum(getattr(r, k) for r in rows)} for k, label in REVENUE_ITEMS]
    total = sum(i["amount"] for i in items)
    return {"total": total, "items": [{**i, "ratio": pct(i["amount"], total)} for i in items]}


def _costs(rows):
    other = {}
    for r in rows:
        for e in r.other_expenses.all():
            item = other.setdefault(e.category_id, {"key": str(e.category_id), "label": e.category.name, "order": e.category.sort_order, "amount": 0})
            item["amount"] += e.amount
    other_total = sum(o["amount"] for o in other.values())
    items = [{"key": k, "label": label, "amount": sum(getattr(r, k) for r in rows)} for k, label in COST_ITEMS]
    items.append({"key": OTHER_KEY, "label": OTHER_LABEL, "amount": other_total})
    total = sum(i["amount"] for i in items)
    return {
        "total": total,
        "items": [{**i, "ratio": pct(i["amount"], total)} for i in items],
        "other_items": [
            {"key": o["key"], "label": o["label"], "amount": o["amount"], "ratio": pct(o["amount"], total)}
            for o in sorted(other.values(), key=lambda o: o["order"])
        ],
    }


def period_core(period, finance, today, only_months=None):
    rows, confirmation = select_confirmed(only_months or period_months(period), finance, today)
    revenue = _revenue(rows)
    costs = _costs(rows)
    profit = revenue["total"] - costs["total"]
    return {
        "period": {"kind": period.kind, "year": period.year, "months": period.months, "label": period.label},
        "confirmation": confirmation,
        "revenue": revenue,
        "costs": costs,
        "profit": {"amount": profit, "margin": pct(profit, revenue["total"])},
    }


# ---------- 비교 ----------


def _base_core(current, base_period, finance, today):
    """현재 기간에 확정 안 된 달이 있으면 현재의 확정 월과 "같은 순서"의 달만 비교 기간에서 집계
    예) 2026 3분기(7·8월 확정) vs 2분기 → 4·5월 / 2026 연간(1~8월) vs 2025 → 1~8월"""
    months = current["period"]["months"]
    confirmed = {m["month"] for m in current["confirmation"]["confirmed_months"]}
    if confirmed == set(months) or not confirmed:
        return period_core(base_period, finance, today), None
    positions = [i for i, m in enumerate(months) if m in confirmed]
    base_months = period_months(base_period)
    aligned_base = [base_months[i] for i in positions]
    aligned = {"current": [{"year": current["period"]["year"], "month": months[i]} for i in positions], "base": aligned_base}
    return period_core(base_period, finance, today, aligned_base), aligned


def _change(now, before, current_has, base_has):
    if not current_has:
        return {"rate": None, "reason": "no-current-data"}  # −100%로 보이지 않게
    if not base_has:
        return {"rate": None, "reason": "no-data"}
    if before == 0:
        return {"rate": None, "reason": "zero-base"}
    return {"rate": round((now - before) / abs(before) * 100, 1)}


def compare(current, base, aligned):
    ch, bh = current["confirmation"]["has_data"], base["confirmation"]["has_data"]
    margin_diff = None
    if ch and bh and current["profit"]["margin"] is not None and base["profit"]["margin"] is not None:
        margin_diff = round(current["profit"]["margin"] - base["profit"]["margin"], 1)
    return {
        "label": base["period"]["label"],
        # 같은 월끼리 맞춰 비교하면 현재 쪽 미확정은 영향 없음 → 비교 기간 쪽 미확정만 남는다
        "is_partial": base["confirmation"]["is_partial"] if aligned else current["confirmation"]["is_partial"] or base["confirmation"]["is_partial"],
        "aligned": aligned,
        "revenue": _change(current["revenue"]["total"], base["revenue"]["total"], ch, bh),
        "costs": _change(current["costs"]["total"], base["costs"]["total"], ch, bh),
        # 이익은 적자·소액이면 증감률이 크게 튀어 금액 차이로 비교
        "profit_diff": current["profit"]["amount"] - base["profit"]["amount"] if ch and bh else None,
        "margin_diff": margin_diff,  # %p
    }


# ---------- 목표 ----------


def _progress(target, actual):
    return {"target": target, "actual": actual, "rate": pct(actual, target)}


def targets_summary(period, finance, today):
    """기간 목표 달성률 + 분기별 목표·실적 + 연간 진도 (목표가 없으면 None)"""
    target = AnnualSalesTarget.objects.filter(year=period.year).first()
    if target is None:
        return None
    year = period.year
    confirmed = {f.month: f for f in finance.values() if f.year == year and f.status == MonthlyFinance.Status.CONFIRMED}

    def revenue_between(first, last):
        return _revenue([f for m, f in confirmed.items() if first <= m <= last])["total"]

    allocation = allocate_quarter_targets(target.target_amount, target.quarter_targets)
    quarters_target = allocation["quarters"]
    month_targets = allocate_month_targets(quarters_target)
    last_month = period.months[-1]
    current_index = _index(today.year, today.month)

    if period.kind == "quarter":
        q = quarter_of(period.months[0])
        first = (q - 1) * 3 + 1
        period_target = {"kind": "quarter", **_progress(quarters_target[q - 1], revenue_between(first, first + 2))}
    elif period.kind == "month":
        q = quarter_of(last_month)
        first = (q - 1) * 3 + 1
        # 월 보기: 분기 첫 달 ~ 그 달 누적을 분기 목표와 비교 (분기 진행률)
        period_target = {"kind": "quarter-progress", **_progress(quarters_target[q - 1], revenue_between(first, last_month))}
    else:
        period_target = {"kind": "annual", **_progress(target.target_amount, revenue_between(1, 12))}

    quarters = []
    for i, qt in enumerate(quarters_target):
        q = i + 1
        months = [(q - 1) * 3 + k for k in (1, 2, 3)]
        first_index = _index(year, months[0])
        state = "future" if current_index < first_index else "current" if current_index <= first_index + 2 else "ended"
        unconfirmed = [m for m in months if m not in confirmed] if state == "ended" else []
        confirmed_count = sum(1 for m in months if m in confirmed)
        actual = revenue_between(months[0], months[-1])
        rate = pct(actual, qt)
        if confirmed_count:
            no_confirmed_text = None
        elif state == "current":
            no_confirmed_text = f"진행 중 (경과 {current_index - first_index + 1}/3개월, 확정된 달 없음)"
        elif state == "ended":
            no_confirmed_text = f"({'·'.join(map(str, unconfirmed))}월 미확정, 확정된 달 없음)"
        else:
            no_confirmed_text = None
        quarters.append({
            "quarter": q,
            "target": qt,
            "actual": actual,
            "rate": rate,
            "source": allocation["sources"][i],
            "state": state,
            "unconfirmed_months": unconfirmed,
            "no_confirmed_text": no_confirmed_text,
            # 끝났고 3개월 모두 확정인데 목표 미달일 때만 경고 (확정 안 된 달이 있으면 "미확정" 안내)
            "warn": state == "ended" and not unconfirmed and rate is not None and rate < 100,
        })

    # 연간 진도: 확정된 마지막 달 ÷ 12 를 경과율로 (실적과 같은 기준)
    confirmed_months = sorted(confirmed)
    basis_month = confirmed_months[-1] if confirmed_months else 0
    annual_actual = revenue_between(1, 12)
    closed_through = 12 if year < today.year else 0 if year > today.year else today.month - 1
    unconfirmed_closed = [m for m in range(1, closed_through + 1) if m not in confirmed]
    annual_rate = pct(annual_actual, target.target_amount)
    elapsed = round(basis_month / 12 * 100, 1)

    month_target = None
    if period.kind == "month":
        m = period.months[0]
        month_target = {"month": m, **_progress(month_targets[m - 1], revenue_between(m, m))}

    return {
        "annual": {
            **_progress(target.target_amount, annual_actual),
            "remaining": max(target.target_amount - annual_actual, 0),
            "basis_month": basis_month,
            "elapsed": elapsed,
            "gap": round((annual_rate or 0) - elapsed, 1),  # %p, 양수 = 진도보다 앞섬
            "confirmed_months": confirmed_months,
            "excluded_months": [m for m in unconfirmed_closed if m > basis_month],
            "gap_months": [m for m in unconfirmed_closed if m < basis_month],
        },
        "period": period_target,
        "month": month_target,
        "quarters": quarters,
        "allocation_warning": allocation["warning"],
        "month_targets": month_targets,
        "headcount": target.headcount,
    }


# ---------- 추이 ----------


def trend(period, finance, today):
    """기간 마지막 달에서 거꾸로 12개월. 임시저장 달도 값을 보여 주되 status 로 구분, 없는 달·마감 전 달은 None"""
    last = _index(period.year, period.months[-1])
    current = _index(today.year, today.month)
    points = []
    for i in range(last - TREND_MONTHS + 1, last + 1):
        row = finance.get(i)
        if row is None:
            points.append({**_ym(i), "status": "pending" if i >= current else "missing", "revenue": None, "costs": None, "profit": None, "margin": None})
            continue
        revenue = _revenue([row])["total"]
        costs = _costs([row])["total"]
        points.append({**_ym(i), "status": row.status, "revenue": revenue, "costs": costs, "profit": revenue - costs, "margin": pct(revenue - costs, revenue)})
    return points


# ---------- 미수금 (경영지원 관리 외상매출금 기준) ----------


def receivables(period, today):
    """기준월 = 기간 안에서 오늘이 속한 달까지, 외상매출금 행이 있는 마지막 달 (없으면 None — 다른 달 값을 끌어오지 않음)
    미수 = 장기 미수금 + 당월 수금예정. 당월 수금은 그 달에 받은 돈이라 따로"""
    limit = _index(today.year, today.month)
    entries = LedgerEntry.objects.filter(
        kind=LedgerEntry.Kind.AR, deleted_at__isnull=True, year=period.year, month__in=period.months
    )
    has = {e.month for e in entries}
    month = next((m for m in reversed(period.months) if _index(period.year, m) <= limit and m in has), None)
    if month is None:
        return {"month": None}
    rows = [e for e in entries if e.month == month]
    S = LedgerEntry.ArStatus
    group = lambda status: [e for e in rows if e.ar_status == status]  # noqa: E731
    total = lambda lst: {"amount": sum(e.amount for e in lst), "count": len(lst)}  # noqa: E731
    long_overdue, scheduled, collected = group(S.LONG_OVERDUE), group(S.SCHEDULED), group(S.COLLECTED)
    open_rows = long_overdue + scheduled
    return {
        "month": {"year": period.year, "month": month},
        "is_current_month": _index(period.year, month) == limit,
        "total": sum(e.amount for e in open_rows),
        "count": len(open_rows),
        "customer_count": len({e.partner_name for e in open_rows}),
        "long_overdue": total(long_overdue),
        "scheduled": total(scheduled),
        "collected": total(collected),
    }


# ---------- 종합 ----------


def management_summary(period, today=None):
    today = today or timezone.localdate()
    prev, last_year = previous_period(period), same_period_last_year(period)
    indexes = set()
    for p in (period, prev, last_year):
        indexes |= {_index(p.year, m) for m in p.months}
    end = _index(period.year, period.months[-1])
    indexes |= set(range(end - TREND_MONTHS + 1, end + 1))
    indexes |= {_index(period.year, m) for m in range(1, 13)}  # 목표 달성률은 그 해 전체
    finance = load_finance(indexes)

    core = period_core(period, finance, today)
    prev_core, prev_aligned = _base_core(core, prev, finance, today)
    changes = {"previous": compare(core, prev_core, prev_aligned)}
    if period.kind in ("month", "quarter"):  # 연간은 직전 기간 = 전년이라 하나만
        ly_core, ly_aligned = _base_core(core, last_year, finance, today)
        changes["last_year"] = compare(core, ly_core, ly_aligned)
    return {
        **core,
        "changes": changes,
        "targets": targets_summary(period, finance, today),
        "trend": trend(period, finance, today),
        "receivables": receivables(period, today),
    }
