"""경영지원 관리 엑셀 이관 — 고객사 「경영지원_관리」 엑셀 → 장부 (조원 저장소 ledger/import/*.ts 를 옮김)

원본 구조 (행 번호는 고정이 아니라고 보고 제목 글자로 찾는다)
- 시트 하나에 블록 4개가 세로로: C열 제목(외상매출금·외상매입금·미지급비용-직원·미지급비용-업체) → 다음 행이 머리글
- 머리글: 코드(A, 외상매출금만) | 거래처명(C) | 잔액(D) | 적요(E) | 총액(F)
- F열 총액은 그룹마다 세로 병합 + =SUM(...). 데이터로 저장하지 않고 검산에만 쓴다
- 외상매출금 그룹 = F열 병합 범위, H열 메모("← 장기 미수금 업체" 등)로 상태 판별, 빨간 글씨 = 장기 미수금
- 미지급비용-업체: 적요 "자동이체" 또는 연두 배경 = 자동이체
- 외상매출금 당월 수금 완료일: 적요 날짜(기준월 안·오늘 이전) → 없으면 min(기준월 말일, 오늘)
"""

import calendar
import re
from datetime import date, datetime

from openpyxl.utils import get_column_letter

from .models import LedgerEntry

K, S = LedgerEntry.Kind, LedgerEntry.ArStatus
KINDS = [k for k, _ in K.choices]
KIND_LABEL = dict(K.choices)
AR_LABEL = dict(S.choices)
COL = {"code": 1, "name": 3, "amount": 4, "note": 5, "total": 6, "memo": 8}
MAX_BYTES = 5 * 1024 * 1024


def squash(s):
    return re.sub(r"\s+", "", s or "")


def _text(cell):
    v = cell.value if cell is not None else None
    if v is None or isinstance(v, (datetime, date)):
        return ""
    return str(v).strip()


def _blank(cell):
    return cell is None or cell.value is None or (isinstance(cell.value, str) and not cell.value.strip())


def _is_formula(cell):
    return isinstance(cell.value, str) and cell.value.startswith("=")


def is_red(cell):
    """빨간 글씨: FF0000 (테마 색은 판별하지 않음)"""
    color = cell.font.color if cell is not None and cell.font else None
    return bool(color is not None and color.type == "rgb" and isinstance(color.rgb, str) and color.rgb[-6:].upper() == "FF0000")


def is_green_fill(cell):
    """연두 배경: 원본은 테마 색 9번(강조 6 = 초록). 직접 지정 색이면 초록 성분이 빨강·파랑보다 큰 색"""
    fill = cell.fill if cell is not None else None
    if not fill or not fill.fill_type:
        return False
    color = fill.fgColor
    if color.type == "theme":
        return color.theme == 9
    hex6 = color.rgb[-6:] if color.type == "rgb" and isinstance(color.rgb, str) else ""
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", hex6):
        return False
    r, g, b = (int(hex6[i : i + 2], 16) for i in (0, 2, 4))
    return g > r and g > b


def format_note_date(d, number_format):
    """날짜 칸 → 엑셀 표시 형식대로 글자 ("m/d" → "10/5", "mm월 dd일" → "10월 05일")"""
    fmt = number_format or ""
    if "월" in fmt:
        return f"{d.month:02d}월 {d.day:02d}일" if "mm" in fmt else f"{d.month}월 {d.day}일"
    return f"{d.month}/{d.day}"


def read_amount(cell, value_cell):
    """잔액 칸 → ("ok", 금액) / ("empty", None) / ("error", 메시지)"""
    if _is_formula(cell) and value_cell.value is None:
        return "error", "잔액이 수식인데 계산값이 저장돼 있지 않습니다. 엑셀에서 열어 저장한 뒤 올려 주세요."
    v = value_cell.value
    if v is None:
        return "empty", None
    if isinstance(v, bool) or isinstance(v, (datetime, date)):
        return "error", "잔액이 숫자가 아닙니다."
    if isinstance(v, str):
        cleaned = re.sub(r"[,\s원₩]", "", v)
        if not cleaned:
            return "empty", None
        if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
            return "error", f'잔액이 숫자가 아닙니다 ("{v.strip()}").'
        v = float(cleaned)
    if v < 0:
        return "error", "음수 잔액입니다 (선수금·과입금인지 확인하세요). 음수는 가져올 수 없습니다."
    if v != int(v):
        return "error", "잔액에 소수점이 있습니다. 원 단위 정수만 가져옵니다."
    if len(str(int(v))) > 15:
        return "error", "잔액이 15자리를 넘습니다."
    return "ok", int(v)


def read_partner_code(cell):
    """거래처코드: 문자열은 그대로, 숫자로 저장돼 있으면 10자리로 0 채움"""
    v = cell.value if cell is not None else None
    if v is None or v == "":
        return None, None
    raw = str(int(v)).zfill(10) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 and v == int(v) else str(v).strip()
    if not raw:
        return None, None
    if len(raw) == 10 and raw.isdigit():
        return raw, None
    return None, f'거래처코드는 숫자 10자리여야 합니다 ("{raw}").'


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def default_settled_on(year, month, today):
    """완료일 기본값: min(기준월 말일, 오늘)"""
    return min(month_end(year, month), today)


def status_from_memo(memo):
    s = squash(memo)
    if "장기미수금" in s:
        return S.LONG_OVERDUE
    if "수금된" in s:
        return S.COLLECTED
    if "수금예정" in s:
        return S.SCHEDULED
    return None


# ---------- 시트 ----------


def find_titles(ws):
    title_of = {squash(label): k for k, label in KIND_LABEL.items()}
    found = []
    for r in range(1, ws.max_row + 1):
        kind = title_of.get(squash(_text(ws.cell(r, COL["name"]))))
        if kind:
            found.append((kind, r))
    return found


def ledger_sheet_names(wb):
    """양식 시트(C열에 "외상매출금" 제목이 있는 시트)만"""
    return [ws.title for ws in wb.worksheets if any(k == K.AR for k, _ in find_titles(ws))]


def select_sheet(wb, month_text, requested):
    """1) 고른 시트 2) 양식 시트가 1장이면 그 시트 3) 기준년월과 같은 이름("2026-10") 시트 4) 없으면 고르게 한다"""
    names = ledger_sheet_names(wb)
    if not names:
        return None, {"reason": "none"}

    def month_of(name):
        m = re.search(r"(?:^|\s)(\d{4}-\d{2})$", name)
        return m.group(1) if m else None

    def pick(name):
        named = month_of(name)
        note = f"시트 이름({name})과 기준년월({month_text})이 다릅니다. 맞는지 확인하세요." if named and named != month_text else None
        return name, {"candidates": names, "note": note}

    if requested:
        return pick(requested) if requested in names else (None, {"reason": "choose", "candidates": names})
    if len(names) == 1:
        return pick(names[0])
    same = next((n for n in names if month_of(n) == month_text), None)
    return pick(same) if same else (None, {"reason": "choose", "candidates": names})


def _total_ranges(ws, first, last):
    """그룹(총액) 범위: F열 세로 병합 + 병합되지 않은 F열 SUM 칸 (행이 1개뿐인 그룹)"""
    merged = [
        (m.min_row, m.max_row)
        for m in ws.merged_cells.ranges
        if m.min_col == m.max_col == COL["total"] and m.min_row >= first and m.max_row <= last
    ]
    in_merge = lambda r: any(top <= r <= bottom for top, bottom in merged)  # noqa: E731
    single = [
        (r, r)
        for r in range(first, last + 1)
        if _is_formula(ws.cell(r, COL["total"])) and ws.cell(r, COL["total"]).value.upper().startswith("=SUM(") and not in_merge(r)
    ]
    return sorted(merged + single)


def _parse_block(ws, wv, kind, title_row, last_row, year, month, today, fatal):
    header = title_row + 1
    label = KIND_LABEL[kind]
    wrong = [(c, h) for c, h in ((COL["name"], "거래처명"), (COL["amount"], "잔액"), (COL["note"], "적요")) if squash(_text(ws.cell(header, c))) != h]
    if kind == K.AR and squash(_text(ws.cell(header, COL["code"]))) != "코드":
        wrong.insert(0, (COL["code"], "코드"))
    if wrong:
        need = ", ".join(f'{get_column_letter(c)}열 "{h}"' for c, h in wrong)
        fatal.append(f"{label}: {header}행 머리글이 양식과 다릅니다 ({need} 필요).")
        return None

    first = header + 1
    groups = _total_ranges(ws, first, last_row)
    group_of = lambda r: next((g for g in groups if g[0] <= r <= g[1]), None)  # noqa: E731
    group_status = {
        g: status_from_memo(" ".join(_text(ws.cell(r, COL["memo"])) for r in range(g[0], g[1] + 1))) for g in groups
    }

    rows, skipped = [], {"code_only": [], "zero": []}
    for r in range(first, last_row + 1):
        name_cell, amount_cell = ws.cell(r, COL["name"]), ws.cell(r, COL["amount"])
        code_cell = ws.cell(r, COL["code"]) if kind == K.AR else None
        if _blank(name_cell) and _blank(amount_cell) and not _is_formula(amount_cell):
            if code_cell is not None and not _blank(code_cell):
                skipped["code_only"].append(r)
            continue
        errors, warnings = [], []
        partner_name = " ".join(_text(name_cell).split())
        if not partner_name:
            errors.append("거래처명이 없습니다.")
        elif len(partner_name) > 50:
            errors.append("거래처명이 50자를 넘습니다.")

        state, amount = read_amount(amount_cell, wv.cell(r, COL["amount"]))
        if state == "ok" and amount == 0:
            skipped["zero"].append(r)
            continue
        if state == "empty":
            errors.append("잔액이 없습니다.")
        elif state == "error":
            errors.append(amount)
            amount = None

        code, code_error = read_partner_code(code_cell) if kind == K.AR else (None, None)
        if code_error:
            errors.append(code_error)

        # 적요: 날짜 칸은 엑셀 표시 그대로 글자로 (원문 보존)
        note_cell = ws.cell(r, COL["note"])
        note_date = note_cell.value if isinstance(note_cell.value, (datetime, date)) else None
        note = format_note_date(note_date, note_cell.number_format) if note_date else (_text(note_cell) or None)
        if note and len(note) > 200:
            errors.append("적요가 200자를 넘습니다.")

        ar_status = ar_source = settled = settled_source = ignored = None
        if kind == K.AR:
            g = group_of(r)
            from_memo = group_status.get(g) if g else None
            # 빨간 글씨 판별은 외상매출금에서만
            if is_red(name_cell) or is_red(amount_cell):
                ar_status, ar_source = S.LONG_OVERDUE, "red"
                if from_memo and from_memo != S.LONG_OVERDUE:
                    warnings.append(f"빨간 글씨라 장기 미수금으로 분류했습니다 (원래 그룹: {AR_LABEL[from_memo]}).")
            elif from_memo:
                ar_status, ar_source = from_memo, "memo"
            if ar_status == S.COLLECTED:
                # 적요 날짜: 연도는 기준년도로, 기준월 밖·오늘 이후 날짜는 쓰지 않는다
                candidate, reason = None, None
                if note_date:
                    if note_date.month != month:
                        reason = "기준월 밖이라"
                    elif date(year, month, note_date.day) > today:
                        reason = "오늘 이후라"
                    else:
                        candidate = date(year, month, note_date.day)
                if candidate:
                    settled, settled_source = candidate, "note"
                else:
                    settled, settled_source = default_settled_on(year, month, today), "month_end"
                    if reason:
                        ignored = f"적요 날짜({note})가 {reason} 사용하지 않음"

        auto = kind == K.ACCRUED_VENDOR and (
            "자동이체" in squash(note or "") or any(is_green_fill(ws.cell(r, c)) for c in (COL["name"], COL["amount"], COL["note"]))
        )
        rows.append({
            "row": r, "kind": kind, "partner_code": code, "partner_name": partner_name, "amount": amount, "note": note,
            "ar_status": ar_status, "ar_status_source": ar_source, "settled_on": settled, "settled_source": settled_source,
            "note_date_ignored": ignored, "auto_transfer": auto, "errors": errors, "warnings": warnings,
        })

    totals = []
    for top, bottom in groups:
        rows_sum = sum(x["amount"] or 0 for x in rows if top <= x["row"] <= bottom)
        master, master_v = ws.cell(top, COL["total"]), wv.cell(top, COL["total"]).value
        file_total = round(master_v) if isinstance(master_v, (int, float)) and not isinstance(master_v, bool) else None
        state = ("match" if file_total == rows_sum else "mismatch") if file_total is not None else ("no_result" if _is_formula(master) else "no_total")
        totals.append({
            "range": f"F{top}:F{bottom}", "rows_sum": rows_sum, "file_total": file_total,
            "formula": master.value if _is_formula(master) else None, "state": state,
        })
    return {"kind": kind, "title_row": title_row, "first_row": first, "last_row": last_row, "rows": rows, "skipped": skipped, "totals": totals}


def parse_ledger_sheet(ws, wv, year, month, today):
    """ws: 수식 그대로 읽은 시트, wv: 계산값으로 읽은 같은 시트"""
    fatal = []
    titles = find_titles(ws)
    for kind in KINDS:
        n = sum(1 for k, _ in titles if k == kind)
        if n == 0:
            fatal.append(f'"{KIND_LABEL[kind]}" 블록 제목(C열)을 찾지 못했습니다.')
        elif n > 1:
            fatal.append(f'"{KIND_LABEL[kind]}" 블록 제목이 {n}번 있습니다.')
    if fatal:
        return {"sheet_name": ws.title, "fatal": fatal, "blocks": []}
    titles.sort(key=lambda t: t[1])
    blocks = []
    for i, (kind, row) in enumerate(titles):
        last = (titles[i + 1][1] if i + 1 < len(titles) else ws.max_row + 1) - 1
        block = _parse_block(ws, wv, kind, row, last, year, month, today, fatal)
        if block:
            blocks.append(block)
    blocks.sort(key=lambda b: KINDS.index(b["kind"]))  # 화면 순서는 구분 순서대로
    return {"sheet_name": ws.title, "fatal": fatal, "blocks": blocks}


# ---------- 미리보기에서 고른 값 → 저장 계획 ----------


def build_plan(parsed, choices, year, month, today, mode, existing_total):
    """choices: {"ar_status": {행: 값}, "purchase_type": {...}, "expense_type": {...}, "settled_on": {행: "YYYY-MM-DD"}}
    → blockers(저장을 막는 것), entries(저장할 행), summary(구분별 건수·합계)"""
    from .ledger_views import _date_error
    from .serializers import LedgerFieldsSerializer

    blockers = [{"type": "error", "message": m} for m in parsed["fatal"]]
    entries = []
    summary = {k: {"count": 0, "sum": 0} for k in KINDS}
    pick = lambda name, row: choices.get(name, {}).get(str(row))  # noqa: E731
    for block in parsed["blocks"]:
        label = KIND_LABEL[block["kind"]]
        for row in block["rows"]:
            at = {"kind": block["kind"], "row": row["row"]}
            if row["errors"] or row["amount"] is None:
                blockers += [{"type": "error", **at, "message": f"{label} {row['row']}행: {m}"} for m in row["errors"]]
                continue
            fields = {"kind": block["kind"], "partner_name": row["partner_name"], "amount": row["amount"], "note": row["note"] or ""}
            if block["kind"] == K.AR:
                status = row["ar_status"] or pick("ar_status", row["row"])
                if not status:
                    blockers.append({"type": "choice", **at, "message": f"{label} {row['row']}행 {row['partner_name']}: 상태(미분류)를 고르세요."})
                    continue
                settled = None
                if status == S.COLLECTED:
                    settled = pick("settled_on", row["row"]) or (row["settled_on"].isoformat() if row["settled_on"] else default_settled_on(year, month, today).isoformat())
                fields.update(ar_status=status, partner_code=row["partner_code"] or "", settled_on=settled)
            elif block["kind"] == K.AP:
                purchase = pick("purchase_type", row["row"])
                if not purchase:
                    blockers.append({"type": "choice", **at, "message": f"{label} {row['row']}행 {row['partner_name']}: 매입유형을 고르세요."})
                    continue
                fields["purchase_type"] = purchase
            elif block["kind"] == K.ACCRUED_VENDOR:
                fields.update(expense_type=pick("expense_type", row["row"]) or "other", auto_transfer=row["auto_transfer"])
            # 화면에서 직접 입력할 때와 같은 검사
            serializer = LedgerFieldsSerializer(data=fields)
            if not serializer.is_valid():
                first = next(iter(serializer.errors.values()))
                message = first[0] if isinstance(first, list) else str(first)
                blockers.append({"type": "error", **at, "message": f"{label} {row['row']}행: {message}"})
                continue
            data = serializer.validated_data
            error = _date_error(data, today)
            if error:
                blockers.append({"type": "choice", **at, "message": f"{label} {row['row']}행 {row['partner_name']}: {error}"})
                continue
            entries.append({"row": row["row"], "fields": data})
            summary[block["kind"]]["count"] += 1
            summary[block["kind"]]["sum"] += data["amount"]

    if not parsed["fatal"] and not any(b["rows"] for b in parsed["blocks"]):
        blockers.append({"type": "empty", "message": "가져올 데이터가 없습니다. 빈 양식이거나 거래처명·잔액이 비어 있습니다."})
    if existing_total and mode is None:
        blockers.append({"type": "choice", "message": f"{year}년 {month}월에 이미 {existing_total}행이 있습니다. 덮어쓰기·추가 중에 고르세요."})
    return {"blockers": blockers, "entries": entries, "summary": summary}
