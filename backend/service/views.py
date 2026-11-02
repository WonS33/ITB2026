from datetime import date

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import TeamPermission
from common.excel import excel_response, excel_sheets_response
from common.periods import period_from_params

from .catalog import catalog_choices, catalog_detail, catalog_table, company_comparison
from .metrics import reports_in, service_summary
from .models import PartCatalogItem, PartPrice, PriceStandard, RequesterRegion, TripReport
from .part_prices import part_price_table
from .regions import DISTRICTS, REGIONS, region_errors
from .serializers import CatalogSettingSerializer, PartPriceSerializer, StandardSettingSerializer
from .trip_input import clean_report, find_duplicates, save_report, validate_report


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
    """GET  /api/service/reports/?year=&period=... — 기간 안의 출장보고서 목록
    POST /api/service/reports/ — 출장보고서 1건 직접 입력 (서비스 수정 권한)"""

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
                        "input_method": r.input_method,
                        "models": [p.model_name for p in r.products.all()],
                    }
                    for r in reports
                ],
            }
        )


    def post(self, request):
        """직접 입력: PDF 업로드와 같은 규칙(service/trip_input.py)으로 검사하고 저장한다.
        같은 시작일·요청처 보고서가 있으면 409로 알리고, allow_duplicate=true로 다시 보내면 저장한다."""
        if not isinstance(request.data, dict):
            return Response({"detail": "보고서 데이터 형식이 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        lists_ok = all(isinstance(request.data.get(key, []), list) for key in ("companions", "parts", "products"))
        if not lists_ok or not all(isinstance(p, dict) for p in request.data.get("products", [])):
            return Response({"detail": "동행자·제품·부품은 목록 형식으로 보내 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        data = clean_report(request.data)
        errors = validate_report(data)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        duplicates = find_duplicates(data)
        if duplicates.exists() and request.data.get("allow_duplicate") is not True:
            return Response(
                {
                    "duplicate": True,
                    "detail": "같은 출장 시작일·요청처의 보고서가 이미 있습니다. 같은 곳에 실제로 두 번 간 경우에만 '중복 아님'을 체크해 저장하세요.",
                    "existing": [{"id": r.id, "start_date": r.start_date, "requester": r.requester, "author": r.author}
                                 for r in duplicates],
                },
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            report = save_report(data, request.user, TripReport.InputMethod.MANUAL)
        report = TripReport.objects.prefetch_related("companions", "products", "parts").get(pk=report.pk)
        return Response(report_detail(report), status=status.HTTP_201_CREATED)


class TripReportDetailView(ServiceApiView):
    """GET /api/service/reports/{id}/ — 출장보고서 상세 (고장·작업 내용 포함)"""

    def get(self, request, pk):
        r = get_object_or_404(TripReport.objects.prefetch_related("companions", "products", "parts"), pk=pk)
        return Response(report_detail(r))


def report_detail(r):
    return {
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
        "input_method": r.input_method,
        "input_method_display": r.get_input_method_display(),
    }


class PartPriceListView(ServiceApiView):
    """GET  /api/service/part-prices/ — 부품별 현재·직전 단가, 증감, 이력, 단가 미등록 부품
    POST /api/service/part-prices/ — 단가 한 줄 추가 (서비스 수정 권한)"""

    def get(self, request):
        return Response(part_price_table())

    def post(self, request):
        serializer = PartPriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PartPriceDetailView(ServiceApiView):
    """DELETE /api/service/part-prices/{id}/ — 잘못 입력한 단가 한 줄 삭제 (서비스 수정 권한)"""

    def delete(self, request, pk):
        get_object_or_404(PartPrice, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PartCatalogListView(ServiceApiView):
    """GET /api/service/part-catalog/?q=파트넘버·품명&category= — 부품별 뉴토크 기준값 + 출장지별 평균·최저·최고·최고−최저"""

    def get(self, request):
        return Response(catalog_table(request.query_params.get("q", ""), request.query_params.get("category", "")))


CATALOG_EXCEL_COLUMNS = [
    ("분류", "category"), ("파트넘버", "part_no"), ("품명", "name"), ("적용 모델", "applies_to"),
    ("단가표 기준단가", "list_price"), ("단가표 기준일", "list_price_date"), ("할인율(%)", "discount_rate"),
    ("추가단가", "extra_price"), ("뉴토크 기준값", "standard_price"), ("출장지 평균", "average"), ("출장지 최저", "min"),
    ("출장지 최고", "max"), ("최고-최저", "range"), ("출장지 수", "count"),
]
COMPANY_EXCEL_COLUMNS = [
    ("출장지(업체)", "company"), ("비교 부품 수", "count"), ("평균 차이율(%)", "average_rate"), ("최저 차이율(%)", "min_rate"),
    ("최고 차이율(%)", "max_rate"), ("비쌈", "above"), ("쌈", "below"), ("크게 낮음", "low"),
]
COMPANY_PART_EXCEL_COLUMNS = [
    ("출장지(업체)", "company"), ("파트넘버", "part_no"), ("품명", "name"), ("당시 뉴토크 기준값", "base_price"),
    ("단가표 기준일", "base_date"), ("업체 단가", "unit_price"), ("차이(원)", "diff"), ("차이율(%)", "diff_rate"),
    ("적용 시작일", "effective_date"), ("크게 낮음", "low_text"),
]


class PartCatalogExportView(ServiceApiView):
    """GET /api/service/part-catalog/export/?q=&category= — 화면과 같은 조건의 부품 단가표(5개 기준)를 엑셀로"""

    def get(self, request):
        data = catalog_table(request.query_params.get("q", ""), request.query_params.get("category", ""))
        rows = [{**i, **i["stats"]} for i in data["items"]]
        return excel_response(f"부품단가_{date.today().isoformat()}.xlsx", "부품 단가", CATALOG_EXCEL_COLUMNS, rows)


class PartCompanyExportView(ServiceApiView):
    """GET /api/service/part-catalog/companies/export/?category= — 출장지별 비교 (시트1 업체 요약, 시트2 부품별 차이)"""

    def get(self, request):
        data = company_comparison(request.query_params.get("category", ""))
        parts = [{**p, "company": c["company"], "low_text": "크게 낮음" if p["low"] else ""}
                 for c in data["companies"] for p in c["parts"]]
        return excel_sheets_response(f"출장지별단가비교_{date.today().isoformat()}.xlsx", [
            ("업체 요약", COMPANY_EXCEL_COLUMNS, data["companies"]),
            ("부품별 차이", COMPANY_PART_EXCEL_COLUMNS, parts),
        ])


class PartCompanyCompareView(ServiceApiView):
    """GET /api/service/part-catalog/companies/?category= — 출장지(업체)별 뉴토크 기준값 대비 평균 차이율 + 부품별 차이"""

    def get(self, request):
        return Response(company_comparison(request.query_params.get("category", "")))


class PartCatalogChoicesView(ServiceApiView):
    """GET /api/service/part-catalog/choices/ — 단가 입력 화면에서 고를 부품 목록 + 이미 입력된 업체(출장지) 이름"""

    def get(self, request):
        companies = (PartPrice.objects.exclude(quote_company="").order_by("quote_company")
                     .values_list("quote_company", flat=True).distinct())
        return Response({"items": catalog_choices(), "companies": list(companies)})


class PartCatalogDetailView(ServiceApiView):
    """GET   /api/service/part-catalog/{id}/ — 부품 하나의 출장지별 단가 목록 (기준값 대비 차이)
    PATCH /api/service/part-catalog/{id}/ — 부품별 할인율·추가단가 (null이면 전체 기본값 사용, 서비스 수정 권한)"""

    def get(self, request, pk):
        return Response(catalog_detail(get_object_or_404(PartCatalogItem, pk=pk)))

    def patch(self, request, pk):
        item = get_object_or_404(PartCatalogItem, pk=pk)
        serializer = CatalogSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.discount_rate = serializer.validated_data["discount_rate"]
        item.extra_price = serializer.validated_data["extra_price"]
        item.save(update_fields=["discount_rate", "extra_price", "updated_at"])
        return Response(catalog_detail(item))


class PriceStandardView(ServiceApiView):
    """GET/PUT /api/service/price-standard/ — 뉴토크 기준값 전체 기본 할인율·추가단가·크게 낮음 표시 기준 (PUT은 서비스 수정 권한)"""

    def get(self, request):
        standard = PriceStandard.get()
        return Response({"discount_rate": float(standard.default_discount_rate), "extra_price": standard.default_extra_price,
                         "low_alert_rate": float(standard.low_alert_rate)})

    def put(self, request):
        serializer = StandardSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        standard = PriceStandard.get()
        standard.default_discount_rate = serializer.validated_data["discount_rate"] or 0
        standard.default_extra_price = serializer.validated_data["extra_price"] or 0
        if "low_alert_rate" in serializer.validated_data:
            standard.low_alert_rate = serializer.validated_data["low_alert_rate"]
        standard.save()
        return self.get(request)


class RequesterRegionListView(ServiceApiView):
    """GET /api/service/requester-regions/ — 요청처 → 시·도·시·군 대응표 (보고서 수 포함)"""

    def get(self, request):
        counts = dict(TripReport.objects.values_list("requester").annotate(n=Count("id")))
        return Response({
            "regions": REGIONS,
            "districts": DISTRICTS,
            "results": [
                {"id": r.id, "requester": r.requester, "region": r.region, "district": r.district,
                 "report_count": counts.get(r.requester, 0)}
                for r in RequesterRegion.objects.order_by("requester")
            ],
        })


class RequesterRegionDetailView(ServiceApiView):
    """PATCH /api/service/requester-regions/{id}/ — 시·도·시·군 변경 (서비스 수정 권한)
    같은 요청처로 이미 저장된 출장보고서의 지역도 함께 바꾼다 (요청처의 위치는 하나이므로)."""

    def patch(self, request, pk):
        mapping = get_object_or_404(RequesterRegion, pk=pk)
        region = request.data.get("region", mapping.region)
        district = request.data.get("district", mapping.district) or ""
        errors = region_errors(region, district)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            mapping.region, mapping.district = region, district
            mapping.save(update_fields=["region", "district"])
            updated = TripReport.objects.filter(requester=mapping.requester).update(region=region, district=district)
        return Response({"id": mapping.id, "requester": mapping.requester, "region": region, "district": district,
                         "report_count": updated})
