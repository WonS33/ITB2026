from .manufacturing_excel import ManufacturingExcelHandler
from .quote_pdf import QuotePdfHandler
from .sales_order_pdf import SalesOrderPdfHandler
from .trip_report_pdf import TripReportPdfHandler

# 파일 종류(kind) → 업로드 규칙. 새 종류는 여기에 추가한다.
HANDLERS = {
    handler.kind: handler
    for handler in [
        ManufacturingExcelHandler(),
        SalesOrderPdfHandler(),
        TripReportPdfHandler(),
        QuotePdfHandler(),
    ]
}
