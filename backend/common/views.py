from datetime import date

from django.db.models import Min
from rest_framework.response import Response
from rest_framework.views import APIView

from production.models import AnnualProductionTarget, ManufacturingRecord, SalesOrder
from service.models import TripReport


def earliest_data_year():
    """업로드·입력된 데이터 중 가장 이른 연도 (없으면 None) — 기간 선택의 연도 목록을 데이터에 맞추는 데 쓴다"""
    dates = [
        ManufacturingRecord.objects.aggregate(d=Min("manufactured_date"))["d"],
        SalesOrder.objects.aggregate(d=Min("due_date"))["d"],
        TripReport.objects.aggregate(d=Min("start_date"))["d"],
    ]
    years = [d.year for d in dates if d]
    target_year = AnnualProductionTarget.objects.aggregate(y=Min("year"))["y"]
    if target_year:
        years.append(target_year)
    return min(years, default=None)


class PeriodYearsView(APIView):
    """GET /api/periods/years/ — 기간 선택에 보여줄 연도 범위 (로그인한 사람 누구나. 연도만 알려 주고 데이터는 없음)"""

    def get(self, request):
        return Response({"earliest_year": earliest_data_year(), "current_year": date.today().year})
