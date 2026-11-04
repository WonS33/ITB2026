"""경영지원 상세 API (조원 저장소 components/detail/management-detail 을 옮김) — 표·수치 위주, 금액은 원 단위 전체"""

from django.utils import timezone
from rest_framework.response import Response

from common.periods import period_from_params

from .detail_metrics import break_even, cash_forecast, productivity, receivables_detail
from .metrics import _index, load_finance, management_summary, period_months, select_confirmed
from .models import AnnualSalesTarget
from .views import ManagementApiView


class DetailView(ManagementApiView):
    """GET /api/management/detail/?(기간) — 메인 대시보드 집계 + 손익분기점·인당 생산성·미수금 상세·자금 수지 예측(오늘 기준)"""

    def get(self, request):
        period = period_from_params(request.query_params)
        today = timezone.localdate()
        summary = management_summary(period, today)
        finance = load_finance({_index(period.year, m) for m in period.months})
        rows, _ = select_confirmed(period_months(period), finance, today)
        target = AnnualSalesTarget.objects.filter(year=period.year).first()
        return Response({
            **summary,
            "break_even": break_even(rows, summary["revenue"]["total"]),
            "productivity": productivity(
                target.headcount if target else None,
                summary["confirmation"]["has_data"],
                summary["revenue"]["total"],
                summary["profit"]["amount"],
            ),
            "receivables": receivables_detail(period, today),
            "cash_forecast": cash_forecast(today),
        })
