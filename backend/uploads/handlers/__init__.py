from .manufacturing_excel import ManufacturingExcelHandler

# 파일 종류(kind) → 업로드 규칙. 새 종류는 여기에 추가한다.
HANDLERS = {
    handler.kind: handler
    for handler in [
        ManufacturingExcelHandler(),
    ]
}
