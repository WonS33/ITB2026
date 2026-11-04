"""미수금 건별 기록 규칙·집계 (조원 저장소 receivables/rules.ts, metrics/receivables.ts 를 옮김)

- 날짜: 발생일 필수·오늘 이후 불가 / 수금 예정일은 발생일 이후 / 수금일은 오늘 이후 불가·발생일 이후
- 경과일은 발생일부터 센다. 구간: 0~30일, 31~60일, 61~90일, 90일 초과
- 기준일 시점의 미수 = 발생일 ≤ 기준일 이고 (아직 미수이거나 수금일 > 기준일). 숨긴 건은 빠진다
"""

from .models import Receivable

TABS = [("open", "미수"), ("collected", "수금 완료"), ("over90", "90일 초과"), ("overdue", "예정일 지남"), ("all", "전체")]
AGING = [("90+", "90일 초과"), ("61-90", "61~90일"), ("31-60", "31~60일"), ("0-30", "0~30일")]


def aging_bucket(days):
    if days > 90:
        return "90+"
    if days > 60:
        return "61-90"
    if days > 30:
        return "31-60"
    return "0-30"


def date_errors(occurred_on, today, due_on=None, collected_on=None, check_collected=False):
    """날짜 규칙 위반 메시지 목록 (비어 있으면 통과)"""
    errors = []
    if occurred_on > today:
        errors.append("발생일은 오늘 이후로 입력할 수 없습니다.")
    if due_on and due_on < occurred_on:
        errors.append("수금 예정일은 발생일보다 이를 수 없습니다.")
    if check_collected:
        if collected_on is None:
            errors.append("수금일을 입력하세요.")
        elif collected_on > today:
            errors.append("미래 날짜로 수금 처리할 수 없습니다.")
        elif collected_on < occurred_on:
            errors.append("수금일은 발생일보다 이를 수 없습니다.")
    return errors


def row_status(r, today):
    """오늘 기준 상태: 미수 건의 경과일·90일 초과·예정일 지남"""
    if r.is_collected:
        return {"age_days": None, "over90": False, "overdue": False}
    age = (today - r.occurred_on).days
    return {"age_days": age, "over90": aging_bucket(age) == "90+", "overdue": bool(r.due_on and r.due_on < today)}


def item_receivables(as_of, horizon_months=6):
    """기준일 시점 미수금 (건별 엑셀·화면 상단 비교용)"""
    rows = [
        r
        for r in Receivable.objects.filter(deleted_at__isnull=True, occurred_on__lte=as_of)
        if not r.is_collected or (r.collected_on and r.collected_on > as_of)
    ]
    items = []
    for r in rows:
        age = (as_of - r.occurred_on).days
        items.append({
            "customer_name": r.customer_name,
            "occurred_on": r.occurred_on,
            "amount": r.amount,
            "due_on": r.due_on,
            "note": r.note,
            "age_days": age,
            "bucket": aging_bucket(age),
            "overdue": bool(r.due_on and r.due_on < as_of),
        })
    items.sort(key=lambda i: -i["amount"])
    customers = {}
    for i in items:
        c = customers.setdefault(i["customer_name"], {"customer_name": i["customer_name"], "amount": 0, "count": 0, "max_age": 0})
        c["amount"] += i["amount"]
        c["count"] += 1
        c["max_age"] = max(c["max_age"], i["age_days"])
    total = lambda lst: {"amount": sum(i["amount"] for i in lst), "count": len(lst)}  # noqa: E731
    return {
        "as_of": as_of,
        "total": sum(i["amount"] for i in items),
        "count": len(items),
        "items": items,
        "by_customer": sorted(customers.values(), key=lambda c: (-c["amount"], c["customer_name"])),
        "aging": [{"bucket": b, "label": label, **total([i for i in items if i["bucket"] == b])} for b, label in AGING],
        "overdue": total([i for i in items if i["overdue"]]),
    }
