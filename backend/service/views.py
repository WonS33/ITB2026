from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import TeamPermission
from common.periods import period_from_params

from .metrics import reports_in, service_summary
from .models import TripReport


class ServiceApiView(APIView):
    """서비스팀 API 공통: 조회는 서비스 열람 권한이 필요하다"""

    team = "service"
    permission_classes = [TeamPermission]


def _period_info(period):
    return {"kind": period.kind, "label": period.label, "start": period.start, "end": period.end, "months": period.months}


class ServiceDashboardView(ServiceApiView):
    """GET /api/service/dashboard/?year=&period=&month=&quarter= — 서비스팀 화면 집계"""

    def get(self, request):
        period = period_from_params(request.query_params)
        return Response({"period": _period_info(period), "service": service_summary(period)})


class TripReportListView(ServiceApiView):
    """GET /api/service/reports/?year=&period=... — 기간 안의 출장보고서 목록"""

    def get(self, request):
        period = period_from_params(request.query_params)
        reports = reports_in(period).prefetch_related("products")
        return Response(
            {
                "period": _period_info(period),
                "results": [
                    {
                        "id": r.id,
                        "start_date": r.start_date,
                        "end_date": r.end_date,
                        "requester": r.requester,
                        "region": r.region,
                        "district": r.district,
                        "paid_type": r.paid_type,
                        "work_type": r.work_type,
                        "author": r.author,
                        "models": [p.model_name for p in r.products.all()],
                    }
                    for r in reports
                ],
            }
        )


class TripReportDetailView(ServiceApiView):
    """GET /api/service/reports/{id}/ — 출장보고서 상세 (고장·작업 내용 포함)"""

    def get(self, request, pk):
        r = get_object_or_404(TripReport.objects.prefetch_related("companions", "products", "parts"), pk=pk)
        return Response(
            {
                "id": r.id,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "extra_trip": r.extra_trip,
                "requester_type": r.requester_type,
                "requester": r.requester,
                "region": r.region,
                "district": r.district,
                "paid_type": r.paid_type,
                "work_type": r.work_type,
                "purpose": r.purpose,
                "author": r.author,
                "companions": [c.name for c in r.companions.all()],
                "products": [
                    {"model_name": p.model_name, "spec": p.spec, "serial_no_raw": p.serial_no_raw, "quantity": p.quantity}
                    for p in r.products.all()
                ],
                "parts": [p.part_name for p in r.parts.all()],
                "fault_description": r.fault_description,
                "work_description": r.work_description,
                "work_result": r.work_result,
            }
        )
