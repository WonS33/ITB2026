"""기간 계산 (specs/03-common.md 3절, specs/09-metrics.md 1절)

화면이 보내는 기간 파라미터
    ?year=2026&period=month|quarter|year&month=10&quarter=4
를 시작일·종료일·개월 수로 바꾼다. 모든 대시보드 API가 이 함수를 같이 쓴다.

- 당월: 선택한 연·월
- 분기: 일반 달력 기준 (1분기 1~3월, 2분기 4~6월, 3분기 7~9월, 4분기 10~12월) — 기업 확인 필요
- 연간: 1~12월
"""

import calendar
from dataclasses import dataclass
from datetime import date

from rest_framework.exceptions import ValidationError

PERIOD_KINDS = ("month", "quarter", "year")


@dataclass(frozen=True)
class Period:
    kind: str  # month / quarter / year
    year: int
    start: date  # 기간 첫날
    end: date  # 기간 마지막 날 (이 날 포함)
    months: list  # 기간에 속한 월 번호 목록 (예: 4분기 → [10, 11, 12])
    label: str  # 화면 표시용 (예: "2026년 4분기")

    @property
    def month_count(self):
        return len(self.months)


def quarter_of(month):
    return (month - 1) // 3 + 1


def make_period(kind, year, month=None, quarter=None):
    if kind == "month":
        months = [month]
        label = f"{year}년 {month}월"
    elif kind == "quarter":
        first = (quarter - 1) * 3 + 1
        months = [first, first + 1, first + 2]
        label = f"{year}년 {quarter}분기"
    else:
        months = list(range(1, 13))
        label = f"{year}년"
    last_day = calendar.monthrange(year, months[-1])[1]
    return Period(
        kind=kind,
        year=year,
        start=date(year, months[0], 1),
        end=date(year, months[-1], last_day),
        months=months,
        label=label,
    )


def _int_param(params, name, default, low, high):
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: f"{name}는 숫자여야 합니다."})
    if not low <= value <= high:
        raise ValidationError({name: f"{name}는 {low}~{high} 사이여야 합니다."})
    return value


def period_from_params(params, today=None):
    """요청 파라미터(request.query_params)로 Period를 만든다.

    값이 없으면 오늘 기준(이번 연도, 이번 달, 이번 분기, 당월 보기)으로 채운다.
    잘못된 값이면 400 오류(ValidationError)를 낸다.
    """
    today = today or date.today()
    kind = params.get("period") or "month"
    if kind not in PERIOD_KINDS:
        raise ValidationError({"period": "period는 month, quarter, year 중 하나여야 합니다."})
    year = _int_param(params, "year", today.year, 2000, 2100)
    month = _int_param(params, "month", today.month, 1, 12)
    quarter = _int_param(params, "quarter", quarter_of(month), 1, 4)
    return make_period(kind, year, month=month, quarter=quarter)
