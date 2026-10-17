from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import TeamPermission
from common.periods import period_from_params

from .metrics import production_summary
from .models import AnnualProductionTarget, ManufacturingRecord
from .serializers import ProductionTargetInputSerializer
from .serials import SEARCH_LIMIT, search_serials, serial_detail


class ProductionApiView(APIView):
    """생산팀 API 공통: 조회는 생산 열람 권한, 입력은 생산 수정 권한이 필요하다"""

    team = "production"
    permission_classes = [TeamPermission]


def _check_year(year):
    if not 2000 <= year <= 2100:
        raise ValidationError({"year": "year는 2000~2100 사이여야 합니다."})


class ProductionTargetView(ProductionApiView):
    """GET/PUT /api/production/targets/{year}/ — 연간 목표 생산량 조회·입력"""

    def get(self, request, year):
        _check_year(year)
        target = AnnualProductionTarget.objects.filter(year=year).first()
        return Response({"year": year, "target_quantity": target.target_quantity if target else None})

    def put(self, request, year):
        _check_year(year)
        serializer = ProductionTargetInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target, created = AnnualProductionTarget.objects.get_or_create(
            year=year,
            defaults={**serializer.validated_data, "created_by": request.user},
        )
        if not created:
            target.target_quantity = serializer.validated_data["target_quantity"]
            target.save()
        return Response({"year": year, "target_quantity": target.target_quantity})


class ProductionDashboardView(ProductionApiView):
    """GET /api/production/dashboard/?year=&period=&month=&quarter= — 생산팀 화면 집계"""

    def get(self, request):
        period = period_from_params(request.query_params)
        return Response(
            {
                "period": {"kind": period.kind, "label": period.label, "start": period.start, "end": period.end},
                "production": production_summary(period),
            }
        )


class SerialSearchView(ProductionApiView):
    """GET /api/production/serials/?q=0001 — 4자리 또는 전체 일련번호로 검색"""

    def get(self, request):
        records = search_serials(request.query_params.get("q"))
        results = [
            {
                "serial_full": r.serial_full,
                "model_name": r.model_name,
                "manufactured_date": r.manufactured_date,
                "customer": r.customer,
                "project_name": r.project_name,
            }
            for r in records
        ]
        return Response({"results": results, "limit": SEARCH_LIMIT})


class SerialDetailView(ProductionApiView):
    """GET /api/production/serials/{serial_full}/ — 조회 항목 11개"""

    def get(self, request, serial_full):
        record = get_object_or_404(ManufacturingRecord, serial_full=serial_full.upper())
        return Response(serial_detail(record))
