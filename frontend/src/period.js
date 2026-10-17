// 기간 보기 상태 (당월 / 분기 / 연간) — specs/03-common.md 3절
// 화면 전체가 하나의 상태를 같이 쓰므로, 생산팀↔서비스팀 화면을 옮겨도 고른 기간이 유지된다.
import { reactive } from 'vue'

const today = new Date()
const thisMonth = today.getMonth() + 1

export const quarterOf = (month) => Math.floor((month - 1) / 3) + 1

export const period = reactive({
  year: today.getFullYear(),
  kind: 'month', // month / quarter / year
  month: thisMonth,
  quarter: quarterOf(thisMonth),
})

export const PERIOD_KINDS = [
  { value: 'month', label: '당월' },
  { value: 'quarter', label: '분기' },
  { value: 'year', label: '연간' },
]

// 백엔드 API에 붙일 기간 파라미터 (specs/08-api.md 공통 규칙)
export function periodParams(p = period) {
  const params = new URLSearchParams({ year: p.year, period: p.kind })
  if (p.kind === 'month') params.set('month', p.month)
  if (p.kind === 'quarter') params.set('quarter', p.quarter)
  return params.toString()
}

export function periodLabel(p = period) {
  if (p.kind === 'month') return `${p.year}년 ${p.month}월`
  if (p.kind === 'quarter') return `${p.year}년 ${p.quarter}분기`
  return `${p.year}년`
}
