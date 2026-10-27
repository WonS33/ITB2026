// 기간 보기 상태 (당월 / 분기 / 연간) — specs/03-common.md 3절
// 화면 전체가 하나의 상태를 같이 쓰므로, 생산팀↔서비스팀 화면을 옮겨도 고른 기간이 유지된다.
import { computed, reactive, ref } from 'vue'
import { apiFetch } from '@/api/client'

const today = new Date()
const thisMonth = today.getMonth() + 1

export const quarterOf = (month) => Math.floor((month - 1) / 3) + 1

export const period = reactive({
  year: today.getFullYear(),
  kind: 'quarter', // month / quarter / year — 처음 화면은 지금 진행 중인 분기 (2026-10-21 결정)
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

// 연도 목록: 업로드된 가장 이른 데이터 연도(없으면 3년 전)부터 내년까지, 최근 연도가 위로
// → 2023년 이전 자료를 올려도 그 연도를 골라 볼 수 있다 (2026-10-27)
const earliestYear = ref(null)
let yearsLoaded = false
export async function loadYearRange() {
  if (yearsLoaded) return
  yearsLoaded = true
  try {
    earliestYear.value = (await apiFetch('/periods/years/')).earliest_year
  } catch {
    yearsLoaded = false // 실패하면 다음에 다시 시도 (그동안은 기본 범위)
  }
}
export function refreshYearRange() {
  yearsLoaded = false
  return loadYearRange()
}
export const yearOptions = computed(() => {
  const thisYear = new Date().getFullYear()
  const from = Math.max(2000, Math.min(earliestYear.value ?? thisYear, thisYear - 3))
  return Array.from({ length: thisYear + 1 - from + 1 }, (_, i) => thisYear + 1 - i)
})
