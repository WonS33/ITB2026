from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import TeamPermission
from common.periods import period_from_params

from . import lists
from .due_calendar import due_calendar, due_soon, search_due
from .metrics import (
    COMPARES,
    CUSTOMER_BASES,
    DATE_BASES,
    PRODUCT_GROUPS,
    delivery_performance,
    model_names,
    monthly_production,
    production_by_model,
    production_compare,
    production_summary,
    sales_summary,
    unshipped_status,
    year_progress,
)
from .industry_map import INDUSTRIES
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


def _period_info(period):
    return {"kind": period.kind, "label": period.label, "start": period.start, "end": period.end, "months": period.months}


class ProductionDashboardView(ProductionApiView):
    """GET /api/production/dashboard/?year=&period=&month=&quarter=&compare=none|previous|last_year — 생산팀 화면 집계"""

    def get(self, request):
        period = period_from_params(request.query_params)
        compare = _choice(request.query_params, "compare", COMPARES, "none")
        return Response(
            {
                "period": _period_info(period),
                "production": production_summary(period),
                "compare": production_compare(period, compare),
                "monthly": monthly_production(period.year, with_last_year=compare != "none"),
                "delivery": delivery_performance(period),
                "unshipped": unshipped_status(),
                "year_progress": year_progress(period.year),
                "by_model": production_by_model(period),
                # 모델 색을 기간이 바뀌어도 같게 하려고 전체 모델명 목록(가나다순)을 함께 보낸다
                "model_names": model_names(),
            }
        )


def _choice(params, name, choices, default):
    value = params.get(name) or default
    if value not in choices:
        raise ValidationError({name: f"{name}는 {', '.join(choices)} 중 하나여야 합니다."})
    return value


class SalesView(ProductionApiView):
    """GET /api/production/sales/?(기간)&date_basis=&customer_basis=&product_group=&compare=&industry=&customer=&product=
    판매 실적 — 직원이 기준 날짜·거래처 기준·제품 묶음·비교 기간·교차 필터를 바꿔 본다"""

    def get(self, request):
        params = request.query_params
        period = period_from_params(params)
        return Response(
            {
                "period": _period_info(period),
                "sales": sales_summary(
                    period,
                    date_basis=_choice(params, "date_basis", DATE_BASES, "due"),
                    customer_basis=_choice(params, "customer_basis", CUSTOMER_BASES, "customer"),
                    product_group_by=_choice(params, "product_group", PRODUCT_GROUPS, "name"),
                    compare=_choice(params, "compare", COMPARES, "none"),
                    industry=params.get("industry") or "",
                    customer=params.get("customer") or "",
                    product=params.get("product") or "",
                ),
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


class DueCalendarView(ProductionApiView):
    """GET /api/production/due-calendar/?year=2026&month=10 — 납기 캘린더 (날짜별·수주번호별)"""

    def get(self, request):
        period = period_from_params({**request.query_params.dict(), "period": "month"})
        return Response(due_calendar(period.year, period.months[0]))


class DueSearchView(ProductionApiView):
    """GET /api/production/due-calendar/search/?q=검색어 — 모든 달에서 수주번호·판매처·사업명·일련번호로 납기 찾기"""

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q.lstrip("#"):
            raise ValidationError({"q": "검색어를 입력해 주세요."})
        return Response(search_due(q))


class DueSoonView(ProductionApiView):
    """GET /api/production/due-soon/ — 납기 임박(오늘부터 14일 안) + 납기 지남(최근 30일) 중 출고가 끝나지 않은 수주"""

    def get(self, request):
        return Response(due_soon())


class RecordListView(ProductionApiView):
    """GET /api/production/records/?(기간)&q=&model=&shipped=yes|no&page= — 제조내역 목록 (제조년월 기준, 100건씩)"""

    def get(self, request):
        params = request.query_params
        period = period_from_params(params)
        page = lists.page_number(params)
        before_shipped, records = lists.filter_records(period, params)
        rows, page_info = lists.paginate(records, page)
        return Response(
            {
                "period": _period_info(period),
                # 출고 상태 버튼에 붙일 건수는 출고 상태로 거르기 전 기준
                "counts": lists.record_counts(before_shipped),
                "results": [lists.record_row(r) for r in rows],
                **page_info,
                "model_names": model_names(),
            }
        )


class RecordExportView(ProductionApiView):
    """GET /api/production/records/export/?(목록과 같은 조건) — 걸러 낸 제조내역 전체를 엑셀로"""

    def get(self, request):
        period = period_from_params(request.query_params)
        _, records = lists.filter_records(period, request.query_params)
        return lists.excel_response(f"제조내역_{period.label}.xlsx", "제조내역", lists.RECORD_COLUMNS, records)


class OrderListView(ProductionApiView):
    """GET /api/production/orders/?(기간)&q=&industry=&page= — 수주 내역 목록 (납기일 기준, 100건씩)"""

    def get(self, request):
        params = request.query_params
        period = period_from_params(params)
        page = lists.page_number(params)
        orders = lists.filter_orders(period, params)
        rows, page_info = lists.paginate(orders.prefetch_related("items"), page)
        return Response(
            {
                "period": _period_info(period),
                "counts": lists.order_counts(orders),
                "results": [lists.order_row(o) for o in rows],
                **page_info,
                "industries": INDUSTRIES,
            }
        )


class OrderExportView(ProductionApiView):
    """GET /api/production/orders/export/?(목록과 같은 조건) — 걸러 낸 수주 내역 전체를 엑셀로 (제품 1개 = 1행)"""

    def get(self, request):
        period = period_from_params(request.query_params)
        orders = lists.filter_orders(period, request.query_params)
        return lists.excel_response(
            f"수주내역_{period.label}.xlsx", "수주내역", lists.ORDER_COLUMNS, lists.order_excel_rows(orders)
        )
