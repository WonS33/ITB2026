import { apiFetch, downloadFile } from './client'

// 월간 입력 (월별 실적) — intent: draft(임시저장) / confirm(확정) / update_confirmed(확정된 달 수정)
// body.expected_updated_at: 화면을 불러올 때 받은 updated_at (다른 사람이 먼저 저장했으면 409)
export const getMonthly = (year, month) => apiFetch(`/management/monthly/${year}/${month}/`)
export const saveMonthly = (year, month, body) => apiFetch(`/management/monthly/${year}/${month}/`, { method: 'PUT', body })
export const unconfirmMonthly = (year, month, expectedUpdatedAt) =>
  apiFetch(`/management/monthly/${year}/${month}/unconfirm/`, { method: 'POST', body: { expected_updated_at: expectedUpdatedAt } })
// [경영지원 관리에서 불러오기] 그 달 장부 행 (읽기만)
export const getMonthlyLedger = (year, month) => apiFetch(`/management/monthly/${year}/${month}/ledger/`)
// 엑셀 내려받기 — kind: month / quarter / year (저장된 값 기준, 합계는 확정된 달만)
export function exportMonthly(year, kind, month) {
  const params = new URLSearchParams({ year, period: kind })
  if (kind === 'month') params.set('month', month)
  if (kind === 'quarter') params.set('quarter', Math.floor((month - 1) / 3) + 1)
  return downloadFile(`/management/monthly/export/?${params}`, '월간입력.xlsx')
}
// 변경 이력 — filters: { from, to, actor, screen, action, q, page }
export function getHistory(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => v && params.set(k, v))
  return apiFetch(`/management/history/?${params}`)
}
