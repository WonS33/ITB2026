"""납기 캘린더 + 납기 임박 목록 (specs/05-production.md 3절)

제조내역의 납기일을 날짜별·수주번호(PO번호)별로 묶는다.
제조내역 1행 = 제품 1대이므로, 같은 날 같은 수주번호의 행 수가 그 수주의 납기 대수다.

처리 상태 (제안, 2026-10-27): 제조내역의 **출고일**로 판단한다
- done(출고 완료): 묶음의 모든 대수에 출고일이 있음
- partial(일부 출고): 일부만 출고일이 있음
- pending(출고 전): 출고일이 하나도 없음
- overdue(납기 지남): 출고가 끝나지 않았는데 납기일이 오늘보다 앞섬 (pending·partial 중)
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from common.periods import make_period

from .models import ManufacturingRecord

DUE_SOON_DAYS = 14  # 납기 임박: 오늘부터 14일 안 (제안)
SEARCH_LIMIT = 50  # 캘린더 검색 결과 최대 수주 묶음 수
OVERDUE_LOOKBACK_DAYS = 30  # 납기 지남·미출고는 최근 30일 것만 (오래된 행에 출고일이 비어 있어도 목록이 넘치지 않게)


def group_orders(records, today):
    """제조내역 → [(납기일, 수주 묶음)] — 묶음마다 대수·출고 대수·처리 상태를 붙인다"""
    groups = defaultdict(lambda: {"customers": [], "projects": [], "serials": [], "shipped": 0})
    for r in records:
        g = groups[(r.due_date, r.po_no)]
        g["serials"].append(r.serial_full)
        g["shipped"] += 1 if r.shipped_date else 0
        if r.customer and r.customer not in g["customers"]:
            g["customers"].append(r.customer)
        if r.project_name and r.project_name not in g["projects"]:
            g["projects"].append(r.project_name)

    result = []
    for (due_date, po_no), g in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        quantity = len(g["serials"])
        status = "done" if g["shipped"] == quantity else "partial" if g["shipped"] else "pending"
        result.append((due_date, {
            "po_no": po_no,  # 빈 값이면 화면에서 "수주번호 없음"으로 표시
            "customers": g["customers"],
            "projects": g["projects"],
            "quantity": quantity,
            "shipped": g["shipped"],
            "status": status,
            "overdue": status != "done" and due_date < today,
            "serials": g["serials"],
        }))
    return result


def due_calendar(year, month, today=None):
    today = today or date.today()
    period = make_period("month", year, month=month)
    records = ManufacturingRecord.objects.filter(due_date__range=(period.start, period.end)).order_by(
        "due_date", "po_no", "serial_full"
    )
    days = defaultdict(list)
    for due_date, order in group_orders(records, today):
        days[due_date].append(order)
    return {
        "year": year,
        "month": month,
        "days": [{"date": d.isoformat(), "orders": orders} for d, orders in sorted(days.items())],
    }


def due_soon(today=None):
    """메인 대시보드 '납기 임박': 출고가 끝나지 않은 수주 중
    납기 지남(최근 30일) + 오늘부터 14일 안. 납기일 순서, D-day 포함"""
    today = today or date.today()
    records = ManufacturingRecord.objects.filter(
        due_date__range=(today - timedelta(days=OVERDUE_LOOKBACK_DAYS), today + timedelta(days=DUE_SOON_DAYS))
    ).order_by("due_date", "po_no", "serial_full")
    items = [
        {**{k: v for k, v in order.items() if k != "serials"}, "due_date": due_date, "d_day": (due_date - today).days}
        for due_date, order in group_orders(records, today)
        if order["status"] != "done"
    ]
    return {"days": DUE_SOON_DAYS, "items": items}


def search_due(query, today=None):
    """캘린더 검색: 수주번호(# 없이도)·판매처·사업명·일련번호·거래처 주문번호에 검색어가 들어 있는 납기 묶음.
    모든 달에서 찾고, 최근 납기일부터 최대 50건. 일련번호로 찾아도 그 수주 묶음 전체(대수·출고)를 보여준다."""
    today = today or date.today()
    q = (query or "").strip()
    po = q.lstrip("#")
    matched = ManufacturingRecord.objects.exclude(due_date=None).filter(
        Q(po_no__icontains=po) | Q(customer__icontains=q) | Q(project_name__icontains=q)
        | Q(serial_full__icontains=q) | Q(customer_order_no__icontains=q)
    )
    keys = set(matched.values_list("due_date", "po_no"))
    total = len(keys)
    keys = set(sorted(keys, key=lambda k: (k[0], k[1]), reverse=True)[:SEARCH_LIMIT])
    records = ManufacturingRecord.objects.filter(due_date__in={d for d, _ in keys}).order_by("due_date", "po_no", "serial_full")
    records = [r for r in records if (r.due_date, r.po_no) in keys]
    results = [
        {**order, "due_date": due_date, "d_day": (due_date - today).days}
        for due_date, order in reversed(group_orders(records, today))
    ]
    return {"query": q, "total": total, "limit": SEARCH_LIMIT, "results": results}
