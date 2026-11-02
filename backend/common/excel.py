"""엑셀(.xlsx) 내려받기 응답 — 생산팀 목록·서비스팀 단가표가 함께 쓴다"""

from io import BytesIO
from urllib.parse import quote

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font


def _fill_sheet(ws, columns, rows):
    ws.append([title for title, _ in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        values = [row.get(key) if isinstance(row, dict) else getattr(row, key) for _, key in columns]
        # 날짜는 YYYY-MM-DD 글자로 (CLAUDE.md 6절 형식 통일), 빈 값은 빈칸
        ws.append([v.isoformat() if hasattr(v, "isoformat") else ("" if v is None else v) for v in values])
    for i, (title, _) in enumerate(columns, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(10, len(title) * 2 + 2)
    ws.freeze_panes = "A2"


def excel_sheets_response(file_name, sheets):
    """sheets: [(시트 이름, [(제목, 키)], 행 목록)] → 시트 여러 개짜리 .xlsx 내려받기 응답"""
    wb = Workbook()
    for i, (title, columns, rows) in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet()
        ws.title = title
        _fill_sheet(ws, columns, rows)

    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    # 한글 파일 이름은 filename* (UTF-8) 로 보낸다
    response["Content-Disposition"] = f"attachment; filename=\"export.xlsx\"; filename*=UTF-8''{quote(file_name)}"
    return response


def excel_response(file_name, sheet_title, columns, rows):
    """columns: [(제목, 키)], rows: 딕셔너리 또는 모델 객체 목록 → .xlsx 내려받기 응답 (시트 1개)"""
    return excel_sheets_response(file_name, [(sheet_title, columns, rows)])
