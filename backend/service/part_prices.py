"""교체 부품 단가 표 (specs/06-service.md, specs/09-metrics.md 4절)

- 현재 단가 = 적용 시작일이 오늘 이전(오늘 포함)인 것 중 가장 최근 단가
- 직전 단가 = 현재 단가 바로 앞의 단가
- 증감 = 현재 단가 - 직전 단가, 증감률(%) = 증감 ÷ 직전 단가 × 100 (소수 첫째 자리)
- 단가 미등록 부품 = 출장보고서에 나왔지만 단가가 하나도 없는 부품
- 출처: 직접 입력 또는 견적서(견적 번호)
- 부품 비용 합계(사용 횟수 × 단가)는 보고서에 수량이 없어 계산하지 않는다 (기업 확인 전)
"""

from collections import defaultdict
from datetime import date

from django.db.models import Count

from .models import PartPrice, TripReportPart


def source_label(price):
    """단가 출처 표시: '견적서 NTK-…' 또는 '직접 입력'"""
    if price.source == PartPrice.Source.QUOTE:
        return f"견적서 {price.quote_no}".strip()
    return price.get_source_display()


def part_price_table(today=None):
    today = today or date.today()
    usage = dict(TripReportPart.objects.values_list("part_name").annotate(n=Count("id")))

    history = defaultdict(list)
    for price in PartPrice.objects.order_by("part_name", "effective_date"):
        history[price.part_name].append(price)

    parts = []
    for name, prices in history.items():
        applied = [p for p in prices if p.effective_date <= today]
        current = applied[-1] if applied else None
        previous = applied[-2] if len(applied) >= 2 else None
        change = current.unit_price - previous.unit_price if current and previous else None
        parts.append({
            "part_name": name,
            "usage_count": usage.get(name, 0),
            "current_price": current.unit_price if current else None,
            "current_since": current.effective_date if current else None,
            "previous_price": previous.unit_price if previous else None,
            "change": change,
            "change_rate": round(change / previous.unit_price * 100, 1) if change is not None and previous.unit_price else None,
            "current_source": source_label(current) if current else None,
            "history": [
                {"id": p.id, "unit_price": p.unit_price, "effective_date": p.effective_date, "upcoming": p.effective_date > today,
                 "source": source_label(p),
                 # 견적 단가가 달라진 이유를 참고하는 정보 (견적서로 넣은 단가만)
                 "company": p.quote_company, "project": p.quote_project, "note": p.quote_note}
                for p in prices
            ],
        })
    parts.sort(key=lambda p: (-p["usage_count"], p["part_name"]))

    unregistered = [
        {"part_name": name, "usage_count": n}
        for name, n in sorted(usage.items(), key=lambda x: (-x[1], x[0]))
        if name not in history
    ]
    return {"parts": parts, "unregistered": unregistered, "part_names": sorted(set(usage) | set(history))}
