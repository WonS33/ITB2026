"""목표 배분 규칙 (조원 저장소 metrics/targets.ts 를 옮김) — 목표 설정 화면 미리보기와 대시보드 달성률이 같이 쓴다

- 분기 목표: 비어 있는 분기 = (연간 − 입력한 분기 합) ÷ 빈 분기 수, 나누어떨어지지 않는 원은 마지막 빈 분기에
  · 입력한 분기 합이 연간보다 크면 빈 분기는 0원 + 경고(QUARTER_SUM_EXCEEDS_ANNUAL)
  · 4개 모두 입력했는데 합계 ≠ 연간이면 경고(QUARTER_SUM_MISMATCH), 입력값 그대로 사용
- 월 목표: 분기 목표 ÷ 3, 나머지 원은 그 분기 마지막 달에
"""

WARNINGS = {
    "QUARTER_SUM_MISMATCH": "분기 목표 4개의 합계가 연간 목표와 다릅니다.",
    "QUARTER_SUM_EXCEEDS_ANNUAL": "입력한 분기 목표 합계가 연간 목표보다 커서 빈 분기는 0원이 됩니다.",
}


def split_evenly(total, count):
    """total 을 count 개로 똑같이 나누고 나머지 원은 마지막 몫에 더한다"""
    base, rest = divmod(total, count)
    return [base] * (count - 1) + [base + rest]


def allocate_quarter_targets(annual, quarter_inputs):
    """quarter_inputs: 1~4분기 입력값 (빈칸 = None) → {quarters, sources, warning}"""
    quarters = [q or 0 for q in quarter_inputs]
    sources = ["allocated" if q is None else "input" for q in quarter_inputs]
    empty = [i for i, q in enumerate(quarter_inputs) if q is None]
    filled_sum = sum(q for q in quarter_inputs if q is not None)

    if not empty:
        warning = None if filled_sum == annual else "QUARTER_SUM_MISMATCH"
        return {"quarters": quarters, "sources": sources, "warning": warning}
    remaining = annual - filled_sum
    if remaining < 0:
        return {"quarters": quarters, "sources": sources, "warning": "QUARTER_SUM_EXCEEDS_ANNUAL"}
    for i, part in zip(empty, split_evenly(remaining, len(empty))):
        quarters[i] = part
    return {"quarters": quarters, "sources": sources, "warning": None}


def allocate_month_targets(quarters):
    """분기 목표 4개 → 1~12월 목표 (index 0 = 1월)"""
    return [m for q in quarters for m in split_evenly(q, 3)]
