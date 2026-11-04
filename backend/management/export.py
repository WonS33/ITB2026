"""월간 입력 엑셀 내려받기 (조원 저장소 entry/export/plan.ts·layout.ts 를 옮김)

- 당월: 그 달 시트 1장 (입력이 없어도 빈 모양 + "상태: 입력 없음")
- 분기·연간: 맨 앞 합계 시트(2026-Q3 / 2026) + 데이터가 있는 달(임시저장 포함)의 월 시트
- 합계는 확정된 달만 (대시보드와 같은 숫자). 임시저장·입력 없는 달은 합계 시트 H2에 빨간 글씨로 "제외: …"
- 배치는 고객사 「경영지원_관리」 엑셀처럼 매입 → 경비 → 그 외 지출액 → 매출 블록, 블록마다 F열 총액(=SUM) + H열 메모
- 기간은 이번 달까지만 (미래 달은 넣지 않음)
"""

from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from .models import ExpenseCategory, MonthlyFinance
from .serializers import VALUE_FIELDS

ITEM_LABELS = {
    "merchandise_purchase": "상품 매입액",
    "material_purchase": "원재료 매입액",
    "expense": "경비 지출액",
    "product_sales": "제품 매출액",
    "merchandise_sales": "상품 매출액",
    "service_sales": "용역 매출액",
}
OTHER_EXPENSE_TITLE = "그 외 지출액(광고선전비, 접대비 등)"
BLOCKS = [
    # 제목, H열 메모 글자, 칸 (None = 그 외 지출 항목들)
    ("매입", "매입", ["merchandise_purchase", "material_purchase"]),
    ("경비", "경비 지출", ["expense"]),
    (OTHER_EXPENSE_TITLE, "그 외 지출", None),
    ("매출", "매출", ["product_sales", "merchandise_sales", "service_sales"]),
]

C, D, E, F, H = 3, 4, 5, 6, 8
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="F2F2F2")
RED = "C00000"
MONEY = "#,##0"


def _month_name(year, month):
    return f"{year}-{month:02d}"


def _total_sheet_name(period):
    return f"{period.year}-Q{(period.months[0] - 1) // 3 + 1}" if period.kind == "quarter" else str(period.year)


def _memo_label(period):
    if period.kind == "month":
        return "당월"
    if period.kind == "quarter":
        return f"{(period.months[0] - 1) // 3 + 1}분기"
    return "연간"


def file_name(period):
    name = _month_name(period.year, period.months[0]) if period.kind == "month" else _total_sheet_name(period)
    return f"월간입력_{name}.xlsx"


def export_months(period, today=None):
    """기간 안 이번 달까지의 월 번호"""
    today = today or timezone.localdate()
    return [m for m in period.months if period.year * 12 + m <= today.year * 12 + today.month]


def _visible_others(categories, amount_of):
    """사용 중인 항목 + 비활성이지만 금액이 있는 항목 (월간 입력 화면과 같은 규칙)"""
    return [
        {"name": c.name, "amount": amount_of(c.id), "inactive": not c.is_active}
        for c in categories
        if c.is_active or amount_of(c.id)
    ]


def _month_sheet(year, month, finance, categories):
    others = {e.category_id: e.amount for e in finance.other_expenses.all()} if finance else {}
    if finance is None:
        status = ("상태: 입력 없음", True)
    elif finance.status == MonthlyFinance.Status.DRAFT:
        status = ("상태: 임시저장 (확정 전 — 대시보드 합계 제외)", True)
    else:
        when = f" ({timezone.localtime(finance.confirmed_at):%Y-%m-%d})" if finance.confirmed_at else ""
        status = (f"상태: 확정{when}", False)
    return {
        "name": _month_name(year, month),
        "kind": "month",
        "title_suffix": None,
        "memo": "당월",
        "values": {f: getattr(finance, f) if finance else None for f in VALUE_FIELDS},
        "others": _visible_others(categories, lambda cid: others.get(cid) if finance else None),
        "status": status,
        "status2": None,
    }


def _total_sheet(period, months, by_month, categories):
    confirmed = [by_month[m] for m in months if m in by_month and by_month[m].status == MonthlyFinance.Status.CONFIRMED]
    has = bool(confirmed)
    other_sum = {}
    for f in confirmed:
        for e in f.other_expenses.all():
            other_sum[e.category_id] = other_sum.get(e.category_id, 0) + e.amount
    excluded = [
        f"{m}월 {'임시저장' if m in by_month else '입력 없음'}"
        for m in months
        if m not in by_month or by_month[m].status != MonthlyFinance.Status.CONFIRMED
    ]
    month_list = "·".join(str(f.month) for f in confirmed)
    return {
        "name": _total_sheet_name(period),
        "kind": "total",
        "title_suffix": f"({period.label} 합계)",
        "memo": _memo_label(period),
        "values": {f: sum(getattr(x, f) for x in confirmed) if has else None for f in VALUE_FIELDS},
        "others": _visible_others(categories, lambda cid: other_sum.get(cid, 0) if has else None),
        "status": (f"집계: 확정된 달만 ({month_list}월)", False) if has else ("집계: 확정된 달 없음", True),
        "status2": (f"제외: {' · '.join(excluded)}", True) if excluded else None,
    }


def plan_sheets(period, today=None):
    months = export_months(period, today)
    if not months:
        return []  # 아직 시작하지 않은 기간
    rows =MonthlyFinance.objects.filter(year=period.year, month__in=months).prefetch_related("other_expenses")
    by_month = {f.month: f for f in rows}
    categories = list(ExpenseCategory.objects.all())
    if period.kind == "month":
        return [_month_sheet(period.year, m, by_month.get(m), categories) for m in months]
    return [_total_sheet(period, months, by_month, categories)] + [
        _month_sheet(period.year, m, by_month[m], categories) for m in months if m in by_month
    ]


def _draw(ws, sheet):
    for col, width in ((C, 34), (D, 18), (E, 14), (F, 18), (H, 46)):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    row = 1
    for i, (title, memo, fields) in enumerate(BLOCKS):
        if i > 0:
            row += 1  # 블록 사이 빈 행
        title_row = row
        ws.cell(row=row, column=C, value=f"{title} {sheet['title_suffix']}" if sheet["title_suffix"] else title).font = Font(bold=True)
        row += 1
        for col, text in ((C, "항목"), (D, "금액"), (E, "적요"), (F, "총액")):
            cell = ws.cell(row=row, column=col, value=text)
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
            cell.border = BOX
            cell.alignment = Alignment(horizontal="center")
        row += 1
        if fields:
            prefix = "월간 " if sheet["kind"] == "month" else ""
            items = [(prefix + ITEM_LABELS[f], sheet["values"][f], None) for f in fields]
        else:
            items = [(o["name"], o["amount"], "비활성 항목" if o["inactive"] else None) for o in sheet["others"]]
            items = items or [("(항목 없음)", None, None)]
        first = row
        for name, amount, note in items:
            ws.cell(row=row, column=C, value=name).border = BOX
            cell = ws.cell(row=row, column=D, value=amount)
            cell.number_format = MONEY
            cell.border = BOX
            ws.cell(row=row, column=E, value=note).border = BOX
            ws.cell(row=row, column=F).border = BOX
            row += 1
        last = row - 1
        total = ws.cell(row=first, column=F, value=f"=SUM(D{first}:D{last})")
        total.number_format = MONEY
        total.font = Font(bold=True)
        total.alignment = Alignment(horizontal="center", vertical="center")
        if last > first:
            ws.merge_cells(start_row=first, start_column=F, end_row=last, end_column=F)
        ws.cell(row=first, column=H, value=f"← {sheet['memo']} {memo} (월간 입력)")
        if i == 0:
            for offset, note in enumerate((sheet["status"], sheet["status2"])):
                if note:
                    text, warn = note
                    ws.cell(row=title_row + offset, column=H, value=text).font = Font(color=RED if warn else None, bold=warn)


def build_workbook(sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in sheets:
        ws = wb.create_sheet(sheet["name"])
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        _draw(ws, sheet)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
