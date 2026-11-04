"""경영지원팀 메인 대시보드 API (조원 저장소 main-dashboard 를 옮김)

① KPI(매출·매입·지출 합계·간이 이익·미수금) ② 목표 달성률·매출 구성·매입·지출 구성 ③ 월별 추이 + 산업 분야별·제품별 생산량
④ 팀별 현황(생산·서비스). 생산·서비스 숫자는 각 팀의 집계 함수를 그대로 쓴다 (새 계산 없음)
"""

from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response

from common.periods import make_period, period_from_params
from production.metrics import production_breakdown, production_summary
from production.models import ManufacturingRecord
from service.metrics import service_summary

from . import audit, export
from .metrics import management_summary
from .views import ManagementApiView, _check_year_month


def team_data(period):
    production = production_summary(period)
    due = ManufacturingRecord.objects.filter(due_date__range=(period.start, period.end))
    breakdown = production_breakdown(period, product_group_by="model")
    service = service_summary(period)
    paid = {p["name"]: p["quantity"] for p in service["paid"]}
    return {
        "production": {
            "actual": production["actual"],
            "period_target": production["period_target"],
            "achievement_rate": production["achievement_rate"],
            "due_count": due.count(),  # 기간 안에 납기일이 있는 제품 수
            "due_pending": due.filter(shipped_date__isnull=True).count(),
        },
        # 산업 분야·제품 비중: 생산량 집계(제조년월 기준) — specs/09 3절 확정 정의
        "industry": breakdown["by_industry"],
        "product": breakdown["by_product"],
        "production_total": breakdown["total"],
        "unlinked": breakdown["unlinked"],
        "service": {
            "trip_count": service["trip_count"],
            "paid": paid.get("유상", 0),
            "unpaid": paid.get("무상", 0),
            "paid_rate": round(paid.get("유상", 0) / service["trip_count"] * 100, 1) if service["trip_count"] else None,
            "product_quantity": sum(m["quantity"] or 0 for m in service["by_model"]),
        },
    }


class DashboardView(ManagementApiView):
    """GET /api/management/dashboard/?year=&period=month|quarter|year&month=&quarter= — 메인 대시보드 집계"""

    def get(self, request):
        period = period_from_params(request.query_params)
        return Response({**management_summary(period), "teams": team_data(period)})


class TargetsExportView(ManagementApiView):
    """GET /api/management/targets/{year}/export/ — 목표 대비 실적 엑셀 (합계는 확정된 달만, 대시보드 달성률과 같은 기준)"""

    def get(self, request, year):
        _check_year_month(year, 1)
        today = timezone.localdate()
        summary = management_summary(make_period("year", year), today)
        name = export.targets_file_name(year)
        content = export.build_targets_workbook(year, summary, today)
        audit.record_audit(
            actor=request.user,
            screen="targets-export",
            action="EXPORT",
            target_type="AnnualSalesTarget",
            target_id=name,
            target_label=f"{year}년 목표 대비 실적",
            meta={"period": f"{year}년", "sheet_count": 1, "file_name": name},
        )
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename=\"targets.xlsx\"; filename*=UTF-8''{quote(name)}"
        return response
