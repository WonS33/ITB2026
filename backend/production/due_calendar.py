"""당월 납기 캘린더 (specs/05-production.md 3절)

제조내역의 납기일을 날짜별·수주번호(PO번호)별로 묶는다.
제조내역 1행 = 제품 1대이므로, 같은 날 같은 수주번호의 행 수가 그 수주의 납기 대수다.
"""

from collections import defaultdict

from common.periods import make_period

from .models import ManufacturingRecord


def due_calendar(year, month):
    period = make_period("month", year, month=month)
    records = ManufacturingRecord.objects.filter(due_date__range=(period.start, period.end)).order_by(
        "due_date", "po_no", "serial_full"
    )

    # (납기일, 수주번호) → 묶음
    groups = defaultdict(lambda: {"customers": [], "projects": [], "serials": []})
    for r in records:
        g = groups[(r.due_date, r.po_no)]
        g["serials"].append(r.serial_full)
        if r.customer and r.customer not in g["customers"]:
            g["customers"].append(r.customer)
        if r.project_name and r.project_name not in g["projects"]:
            g["projects"].append(r.project_name)

    days = defaultdict(list)
    for (due_date, po_no), g in groups.items():
        days[due_date].append(
            {
                "po_no": po_no,  # 빈 값이면 화면에서 "수주번호 없음"으로 표시
                "customers": g["customers"],
                "projects": g["projects"],
                "quantity": len(g["serials"]),
                "serials": g["serials"],
            }
        )
    return {
        "year": year,
        "month": month,
        "days": [{"date": d.isoformat(), "orders": orders} for d, orders in sorted(days.items())],
    }
