// 분기 목표 배분 (백엔드 management/targets.py 와 같은 규칙 — 목표 설정 화면 미리보기용)
// 빈 분기 = (연간 − 입력한 분기 합) ÷ 빈 분기 수, 나누어떨어지지 않는 원은 마지막 빈 분기에
export const TARGET_WARNINGS = {
  QUARTER_SUM_MISMATCH: '분기 목표 4개의 합계가 연간 목표와 다릅니다.',
  QUARTER_SUM_EXCEEDS_ANNUAL: '입력한 분기 목표 합계가 연간 목표보다 커서 빈 분기는 0원이 됩니다.',
}

function splitEvenly(total, count) {
  const base = Math.floor(total / count)
  return Array.from({ length: count }, (_, i) => (i === count - 1 ? total - base * (count - 1) : base))
}

// inputs: 1~4분기 입력값 (빈칸 = null) → { quarters, sources, warning }
export function allocateQuarterTargets(annual, inputs) {
  const quarters = inputs.map((q) => q ?? 0)
  const sources = inputs.map((q) => (q === null ? 'allocated' : 'input'))
  const empty = inputs.flatMap((q, i) => (q === null ? [i] : []))
  const filledSum = inputs.reduce((s, q) => s + (q ?? 0), 0)
  if (!empty.length) return { quarters, sources, warning: filledSum === annual ? null : 'QUARTER_SUM_MISMATCH' }
  const remaining = annual - filledSum
  if (remaining < 0) return { quarters, sources, warning: 'QUARTER_SUM_EXCEEDS_ANNUAL' }
  splitEvenly(remaining, empty.length).forEach((part, k) => (quarters[empty[k]] = part))
  return { quarters, sources, warning: null }
}
