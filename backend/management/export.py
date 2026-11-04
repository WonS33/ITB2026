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


# ---------- 목표 대비 실적 엑셀 (조원 저장소 settings/export/targets-layout.ts 를 옮김) ----------
# 시트 한 장("2026"): "연간 목표매출액" 블록(1~4분기 목표, F = SUM) → "목표매출 달성률" 블록(월 행 + 분기마다 F = SUM)
# - 월 행: 확정 = 그 달 매출 + 적요 "월 목표 N (분기 ÷ 3)", 임시저장·입력 없음(마감된 달) = 금액 빈칸 + 빨간 "… — 합계 제외"
# - 분기 메모(H): 달성률 / 진행 중 / 미확정 / 확정된 달 없음 — 확정된 달이 없으면 0.0% 대신 사실만
# - 빨간색: 분기가 끝났고 3개월 모두 확정됐는데 미달일 때만 (대시보드와 같은 규칙)
# - 맨 아래 H 라벨 + I 값: 연간 실적 합계, 목표매출 달성률, 부족분 (엑셀 수식)

PERCENT = "0.0%"


def targets_file_name(year):
    return f"목표실적_{year}.xlsx"


def build_targets_workbook(year, summary, today=None):
    """summary: metrics.management_summary(연간 기간) — 대시보드와 같은 계산 결과"""
    today = today or timezone.localdate()
    targets = summary["targets"]
    wb = Workbook()
    ws = wb.active
    ws.title = str(year)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToHeight = 0
    for col, width in ((C, 16), (D, 18), (E, 34), (F, 18), (H, 46), (9, 18)):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    def header(row):
        for col, text in ((C, "구분"), (D, "금액"), (E, "적요"), (F, "총액")):
            cell = ws.cell(row=row, column=col, value=text)
            cell.font, cell.fill, cell.border = Font(bold=True), HEADER_FILL, BOX
            cell.alignment = Alignment(horizontal="center")

    def group(row, items, memo, warn=False):
        """items: [(이름, 금액|None, 적요|None, 적요 빨강)] → F열 합계(병합) + H열 메모. 다음 행 번호를 돌려줌"""
        first = row
        for name, amount, note, note_warn in items:
            ws.cell(row=row, column=C, value=name).border = BOX
            cell = ws.cell(row=row, column=D, value=amount)
            cell.number_format, cell.border = MONEY, BOX
            n = ws.cell(row=row, column=E, value=note)
            n.border = BOX
            if note_warn:
                n.font = Font(color=RED)
            ws.cell(row=row, column=F).border = BOX
            row += 1
        total = ws.cell(row=first, column=F, value=f"=SUM(D{first}:D{row - 1})")
        total.number_format = MONEY
        total.font = Font(bold=True, color=RED if warn else None)
        total.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(start_row=first, start_column=F, end_row=row - 1, end_column=F)
        ws.cell(row=first, column=H, value=f"← {memo}").font = Font(color=RED if warn else None, bold=warn)
        return row, first

    # ── 연간 목표매출액 ──
    ws.cell(row=1, column=C, value="연간 목표매출액").font = Font(bold=True)
    header(2)
    if targets is None:
        ws.cell(row=1, column=H, value="목표가 설정되지 않았습니다 — 목표·항목 설정에서 입력하세요").font = Font(color=RED, bold=True)
        items = [(f"{q}분기 목표", None, None, False) for q in (1, 2, 3, 4)]
    else:
        items = [
            (f"{q['quarter']}분기 목표", q["target"], "직접 입력" if q["source"] == "input" else "자동 배분", False)
            for q in targets["quarters"]
        ]
    row, _ = group(3, items, f"{year}년 연간 목표매출액")
    if targets and targets["allocation_warning"]:
        # 분기 목표 합계 ≠ 입력한 연간 목표 — 입력값을 보조 칸으로
        ws.cell(row=4, column=H, value="입력한 연간 목표 (분기 합계와 다름)").font = Font(color=RED)
        ws.cell(row=4, column=9, value=targets["annual"]["target"]).number_format = MONEY

    # ── 목표매출 달성률 (월 행 + 분기 그룹) ──
    row += 1
    ws.cell(row=row, column=C, value="목표매출 달성률").font = Font(bold=True)
    header(row + 1)
    row += 2
    finance = {f.month: f for f in MonthlyFinance.objects.filter(year=year).prefetch_related("other_expenses")}
    this_month = today.year * 12 + today.month
    month_targets = targets["month_targets"] if targets else [None] * 12
    group_firsts = []
    last_row = row
    for q in range(1, 5):
        items = []
        for k in (1, 2, 3):
            m = (q - 1) * 3 + k
            f = finance.get(m)
            mt = month_targets[m - 1]
            target_note = None if mt is None else f"월 목표 {mt:,} (분기 ÷ 3)"
            if f and f.status == MonthlyFinance.Status.CONFIRMED:
                items.append((f"{m}월", f.product_sales + f.merchandise_sales + f.service_sales, target_note, False))
            elif f:
                items.append((f"{m}월", None, "임시저장 — 합계 제외", True))
            elif year * 12 + m < this_month:
                items.append((f"{m}월", None, "입력 없음 — 합계 제외", True))
            else:
                items.append((f"{m}월", None, target_note, False))
        info = targets["quarters"][q - 1] if targets else None
        confirmed_count = sum(1 for k in (1, 2, 3) if finance.get((q - 1) * 3 + k) and finance[(q - 1) * 3 + k].status == MonthlyFinance.Status.CONFIRMED)
        rate = lambda r: "-" if r is None else f"{r:.1f}%"  # noqa: E731
        if info is None:
            memo = f"{q}분기"
        elif info["state"] == "future":
            memo = f"{q}분기 시작 전"
        elif info["state"] == "current":
            elapsed = f"경과 {this_month - (year * 12 + (q - 1) * 3 + 1) + 1}/3개월"
            memo = f"{q}분기 진행 중 ({elapsed}, 확정된 달 없음)" if not confirmed_count else f"{q}분기 달성률 {rate(info['rate'])} · 진행 중 ({elapsed})"
        elif not confirmed_count:
            memo = f"{q}분기 ({'·'.join(map(str, info['unconfirmed_months']))}월 미확정, 확정된 달 없음)"
        elif info["unconfirmed_months"]:
            memo = f"{q}분기 달성률 {rate(info['rate'])} ({'·'.join(map(str, info['unconfirmed_months']))}월 미확정)"
        else:
            gap = info["target"] - info["actual"]
            memo = f"{q}분기 달성률 {rate(info['rate'])}" + (f" ({gap:,}원 부족)" if gap > 0 else " (달성)")
        row, first = group(row, items, memo, warn=bool(info and info["warn"]))
        group_firsts.append(first)
        last_row = first

    # ── 연간 합계·달성률·부족분 (H 라벨 + I 수식) ──
    r = last_row + 3
    ws.cell(row=r, column=H, value="연간 실적 합계")
    cell = ws.cell(row=r, column=9, value="=" + "+".join(f"F{x}" for x in group_firsts))
    cell.number_format = MONEY
    if targets:
        annual = targets["annual"]
        ws.cell(row=r + 1, column=H, value="목표매출 달성률")
        cell = ws.cell(row=r + 1, column=9, value=f"=IF({annual['target']}=0,0,I{r}/{annual['target']})")
        cell.number_format = PERCENT
        year_ended = year * 12 + 12 < this_month
        all_confirmed = len(annual["confirmed_months"]) == 12
        warn = year_ended and all_confirmed and annual["actual"] < annual["target"]
        ws.cell(row=r + 2, column=H, value="부족분").font = Font(color=RED if warn else None)
        cell = ws.cell(row=r + 2, column=9, value=f"=MAX({annual['target']}-I{r},0)")
        cell.number_format = MONEY
        cell.font = Font(color=RED if warn else None)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------- 미수금 건별 기록 엑셀 (조원 저장소 receivables/export/receivables-layout.ts 를 옮김) ----------
# 시트1 "미수금 통계": 경과일 그룹(90일 초과 → 61~90일 → 31~60일 → 0~30일, 90일 초과 그룹은 빨간 글씨) + 거래처별 미수금
#   (빈 그룹도 빈 행 1개 + 총액 0), H·I에 90일 초과 합계·수금 예정일 지남
# 시트2 "미수금 상세": 건별 목록 (경과일 큰 순, 첫 행 고정·자동 필터)


def _md(d):
    return f"{d.month:02d}/{d.day:02d}"


def build_receivables_workbook(r):
    wb = Workbook()
    ws = wb.active
    ws.title = "미수금 통계"
    for col, width in ((C, 26), (D, 16), (E, 34), (F, 16), (H, 22), (9, 16)):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width

    def header(row):
        for col, text in ((C, "거래처명"), (D, "미수 금액"), (E, "적요"), (F, "총액")):
            cell = ws.cell(row=row, column=col, value=text)
            cell.font, cell.fill, cell.border = Font(bold=True), HEADER_FILL, BOX
            cell.alignment = Alignment(horizontal="center")

    def group(row, items, memo, warn=False):
        items = items or [(None, None, None)]  # 빈 그룹도 빈 행 1개
        first = row
        red = Font(color=RED) if warn else Font()
        for name, amount, note in items:
            for col, value in ((C, name), (D, amount), (E, note)):
                cell = ws.cell(row=row, column=col, value=value)
                cell.border, cell.font = BOX, red
                if col == D:
                    cell.number_format = MONEY
            ws.cell(row=row, column=F).border = BOX
            row += 1
        total = ws.cell(row=first, column=F, value=f"=SUM(D{first}:D{row - 1})")
        total.number_format, total.font = MONEY, Font(bold=True, color=RED if warn else None)
        total.alignment = Alignment(horizontal="center", vertical="center")
        if row - 1 > first:
            ws.merge_cells(start_row=first, start_column=F, end_row=row - 1, end_column=F)
        ws.cell(row=first, column=H, value=f"← {memo}").font = Font(color=RED if warn and memo else None)
        return row, first

    as_of = r["as_of"]
    ws.cell(row=1, column=C, value=f"미수금 통계 ({as_of.month}/{as_of.day} 기준)").font = Font(bold=True)
    header(2)
    row, over90_row = 3, 3
    for bucket in r["aging"]:
        lst = [i for i in r["items"] if i["bucket"] == bucket["bucket"]]
        items = [
            (
                i["customer_name"],
                i["amount"],
                f"{_md(i['occurred_on'])} 발생·{i['age_days']}일"
                + (f"·예정 {_md(i['due_on'])}{' 지남' if i['overdue'] else ''}" if i["due_on"] else ""),
            )
            for i in lst
        ]
        row, first = group(row, items, f"{bucket['label']} {len(lst)}건", warn=bucket["bucket"] == "90+" and bool(lst))
        if bucket["bucket"] == "90+":
            over90_row = first

    row += 1
    ws.cell(row=row, column=C, value="거래처별 미수금").font = Font(bold=True)
    header(row + 1)
    items = [(c["customer_name"], c["amount"], f"{c['count']}건 · 최장 {c['max_age']}일") for c in r["by_customer"]]
    end, first = group(row + 2, items, f"미수금 총액 {r['count']}건")
    over90 = next(a for a in r["aging"] if a["bucket"] == "90+")
    for k, (label, value, warn) in enumerate((
        ("90일 초과", f"=F{over90_row}", over90["amount"] > 0),
        ("수금 예정일 지남", r["overdue"]["amount"], False),  # 건별 예정일이라 시트 안 다른 칸으로 다시 계산할 수 없어 값만
    )):
        ws.cell(row=first + 1 + k, column=H, value=label).font = Font(color=RED if warn else None)
        cell = ws.cell(row=first + 1 + k, column=9, value=value)
        cell.number_format, cell.font = MONEY, Font(color=RED if warn else None)

    # ── 미수금 상세 (목록형) ──
    detail = wb.create_sheet("미수금 상세")
    columns = [("거래처명", 26), ("발생일", 12), ("예정일", 12), ("경과일", 8), ("구간", 10), ("금액", 15), ("비고", 30)]
    labels = {b["bucket"]: b["label"] for b in r["aging"]}
    detail.append([c for c, _ in columns])
    for k, (_, width) in enumerate(columns, start=1):
        detail.cell(row=1, column=k).font = Font(bold=True)
        detail.column_dimensions[detail.cell(row=1, column=k).column_letter].width = width
    for i in sorted(r["items"], key=lambda i: (-i["age_days"], -i["amount"])):
        detail.append([
            i["customer_name"], i["occurred_on"].isoformat(), i["due_on"].isoformat() if i["due_on"] else None,
            i["age_days"], labels[i["bucket"]], i["amount"], i["note"] or None,
        ])
        detail.cell(row=detail.max_row, column=6).number_format = MONEY
    detail.freeze_panes = "A2"
    detail.auto_filter.ref = f"A1:G{max(detail.max_row, 1)}"

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------- 경영지원 관리 장부 엑셀 (조원 저장소 ledger/export/*.ts 를 옮김) ----------
# 고객사 원본 양식과 같은 순서·열 위치로, 행 수만 실제 데이터 수만큼 → 내려받은 파일을 [엑셀 가져오기]로 다시 올려도 같은 값으로 읽힌다
# - 블록: 제목(C:F 병합) → 머리글 → 데이터 → 빈 행. 외상매출금 → 외상매입금 → 미지급비용-직원 → 미지급비용-업체
# - 그룹(외상매출금 상태별·다른 블록 전체)마다 행 수 = max(데이터 수, 1). 빈 그룹도 빈 행 1개 + 총액 0 + H열 메모
# - 총액: F열 그룹 병합 + =SUM. 장기 미수금 행은 빨간 글씨
# - 업체: 자동이체 행을 위에(연두, E:F 병합), 총액은 자동이체 제외 SUM (원본과 같음), H·I열에 자동이체 합계 / 전체 합계
# - 당월: 그 달 시트 1장 / 분기·연간: 데이터가 있는 달만 월별 시트, 하나도 없으면 빈 양식 1장

GREEN = PatternFill("solid", fgColor="E2EFDA")  # 연두 (가져오기에서 자동이체로 읽는 색)
LEDGER_RED = "FF0000"  # 원본 양식의 장기 미수금 빨강 (가져오기가 이 색을 빨간 글씨로 읽는다)
AR_ORDER = [
    ("long_overdue", "장기 미수금 업체"),
    ("collected", "당월 수금된 업체"),
    ("scheduled", "당월 수금예정인 업체"),
]
KIND_ORDER = [("ap", "외상매입금", "당월 매입 지출"), ("accrued_staff", "미지급비용-직원", "당월 경비 지출")]


def ledger_period_name(period):
    if period.kind == "month":
        return _month_name(period.year, period.months[0])
    return _total_sheet_name(period)


def ledger_file_name(period):
    return f"경영지원_관리_{ledger_period_name(period)}.xlsx"


def plan_ledger_sheets(period, today=None):
    """[(시트 이름, 행 목록)] — 숨긴 행 제외, 입력 순서대로"""
    from .models import LedgerEntry

    months = export_months(period, today)
    if not months:
        return []
    rows = list(LedgerEntry.objects.filter(year=period.year, month__in=months, deleted_at__isnull=True).order_by("created_at", "id"))
    sheets = [(_month_name(period.year, m), [r for r in rows if r.month == m]) for m in months]
    if period.kind == "month":
        return sheets
    with_data = [s for s in sheets if s[1]]
    return with_data or [(ledger_period_name(period), [])]


def _draw_ledger(ws, rows):
    for col, width in ((1, 13), (C, 26), (D, 15), (E, 26), (F, 15), (H, 24), (9, 15)):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.column_dimensions["B"].width = 2
    state = {"row": 1}

    def title(text):
        r = state["row"]
        ws.cell(row=r, column=C, value=text).font = Font(bold=True)
        ws.merge_cells(start_row=r, start_column=C, end_row=r, end_column=F)
        state["row"] += 1

    def header(code):
        r = state["row"]
        cols = ([(1, "코드")] if code else []) + [(C, "거래처명"), (D, "잔액"), (E, "적요"), (F, "총액")]
        for col, text in cols:
            cell = ws.cell(row=r, column=col, value=text)
            cell.font, cell.fill, cell.border = Font(bold=True), HEADER_FILL, BOX
            cell.alignment = Alignment(horizontal="center")
        state["row"] += 1

    def group(items, memo, code=False, red=False):
        """items: 장부 행 목록 → F열 합계(병합) + H열 메모. (첫 행, 마지막 행)을 돌려줌"""
        first = state["row"]
        font = Font(color=LEDGER_RED) if red else Font()
        for e in items or [None]:  # 빈 그룹도 빈 행 1개
            r = state["row"]
            if code:
                c = ws.cell(row=r, column=1, value=(e.partner_code or None) if e else None)
                c.number_format = "@"  # 앞자리 0 유지
            for col, value in ((C, e.partner_name if e else None), (D, e.amount if e else None), (E, (e.note or None) if e else None)):
                cell = ws.cell(row=r, column=col, value=value)
                cell.border, cell.font = BOX, font
                if col == D:
                    cell.number_format = MONEY
                if col == E:
                    cell.number_format = "@"  # 적요가 날짜로 바뀌지 않게 글자로
            ws.cell(row=r, column=F).border = BOX
            state["row"] += 1
        last = state["row"] - 1
        total = ws.cell(row=first, column=F, value=f"=SUM(D{first}:D{last})")
        total.number_format, total.font = MONEY, Font(bold=True, color=LEDGER_RED if red else None)
        total.alignment = Alignment(horizontal="center", vertical="center")
        if last > first:
            ws.merge_cells(start_row=first, start_column=F, end_row=last, end_column=F)
        ws.cell(row=first, column=H, value=f"← {memo}")
        return first, last

    def of(kind):
        return [e for e in rows if e.kind == kind]

    # 외상매출금: 상태별 그룹
    title("외상매출금")
    header(code=True)
    for status, memo in AR_ORDER:
        group([e for e in of("ar") if e.ar_status == status], memo, code=True, red=status == "long_overdue")
    state["row"] += 1
    for kind, label, memo in KIND_ORDER:
        title(label)
        header(code=False)
        group(of(kind), memo)
        state["row"] += 1

    # 미지급비용-업체: 자동이체 행(연두, E:F 병합) → 일반 행(총액 = 자동이체 제외)
    title("미지급비용-업체")
    header(code=False)
    vendor = of("accrued_vendor")
    auto = [e for e in vendor if e.auto_transfer]
    auto_first = state["row"]
    for e in auto or [None]:
        r = state["row"]
        for col, value in ((C, e.partner_name if e else None), (D, e.amount if e else None), (E, (e.note or "자동이체") if e else "자동이체")):
            cell = ws.cell(row=r, column=col, value=value)
            cell.fill, cell.border = GREEN, BOX
            if col == D:
                cell.number_format = MONEY
            if col == E:
                cell.number_format = "@"
        ws.merge_cells(start_row=r, start_column=E, end_row=r, end_column=F)
        state["row"] += 1
    auto_last = state["row"] - 1
    first, last = group([e for e in vendor if not e.auto_transfer], "당월 그 외 지출")
    extras = (("자동이체 합계", f"=SUM(D{auto_first}:D{auto_last})"), ("전체 합계", f"=SUM(D{auto_first}:D{last})"))
    for k, (label, expr) in enumerate(extras):
        ws.cell(row=first + 1 + k, column=H, value=label)
        ws.cell(row=first + 1 + k, column=9, value=expr).number_format = MONEY


def build_ledger_workbook(sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(name)
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 0
        _draw_ledger(ws, rows)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
