"""서비스팀 지표 계산 (specs/09-metrics.md 4절)

- 출장 횟수 = 출장 시작일이 기간에 속하는 보고서 수 (여러 날 출장도 1회)
- 유상·무상 비율(%) = 비용청구 유무별 보고서 수 ÷ 전체 보고서 수 × 100
- 지역별 출장 = 시·도별 보고서 수
- 교체 부품 순위 = 부품명별 사용 횟수 (보고서에 부품 수량이 없어 횟수로 센다)
- A/S 제품 모델명 순위 = 모델명별 수량 합계
- 출장 담당자 순위 = 작성자+동행자를 합쳐 보고서 1건당 1인 1회로 센 횟수
"""

from collections import Counter

from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth

from .models import TripReport, TripReportPart, TripReportProduct


def _ranking(counter):
    return [{"name": name, "quantity": count} for name, count in sorted(counter.items(), key=lambda x: (-x[1], x[0]))]


def reports_in(period):
    return TripReport.objects.filter(start_date__range=(period.start, period.end))


def service_summary(period):
    reports = reports_in(period)
    total = reports.count()

    paid = Counter(dict(reports.values_list("paid_type").annotate(n=Count("id"))))
    regions = Counter(dict(reports.values_list("region").annotate(n=Count("id"))))
    parts = Counter(dict(
        TripReportPart.objects.filter(report__in=reports).values_list("part_name").annotate(n=Count("id"))
    ))
    models = Counter(dict(
        TripReportProduct.objects.filter(report__in=reports).values_list("model_name").annotate(n=Sum("quantity"))
    ))

    # 담당자: 보고서마다 작성자+동행자를 집합(set)으로 모아 같은 사람은 1번만 센다
    people = Counter()
    for report in reports.prefetch_related("companions"):
        names = {report.author} | {c.name for c in report.companions.all()}
        people.update(name for name in names if name)

    # 월별 추이: 선택한 연도의 1~12월 (기간 보기와 관계없이 연간 흐름을 보여줌)
    by_month = dict(
        TripReport.objects.filter(start_date__year=period.year)
        .annotate(m=ExtractMonth("start_date")).values_list("m").annotate(n=Count("id"))
    )

    return {
        "trip_count": total,
        "monthly": [{"month": m, "count": by_month.get(m, 0)} for m in range(1, 13)],
        "paid": [{"name": name, "quantity": paid.get(name, 0)} for name in ("유상", "무상")],
        "by_region": _ranking(regions),
        "by_part": _ranking(parts),
        "by_model": _ranking(models),
        "by_person": _ranking(people),
    }
