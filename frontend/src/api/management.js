import { apiFetch, downloadFile } from './client'
import { periodParams } from '@/period'

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
// 목표·항목 설정 — 연간 목표(분기 목표·직원 수는 선택), 그 외 지출 항목(목록 전체를 한 번에 저장)
export const getTarget = (year) => apiFetch(`/management/targets/${year}/`)
export const saveTarget = (year, body) => apiFetch(`/management/targets/${year}/`, { method: 'PUT', body })
export const getCategories = () => apiFetch('/management/expense-categories/')
export const saveCategories = (body) => apiFetch('/management/expense-categories/', { method: 'PUT', body })
// 메인 대시보드 (기간 보기: 당월·분기·연간) + 목표 대비 실적 엑셀
export const getDashboard = (period) => apiFetch(`/management/dashboard/?${periodParams(period)}`)
export const exportTargets = (year) => downloadFile(`/management/targets/${year}/export/`, `목표실적_${year}.xlsx`)
// 미수금 건별 기록 — action: collect / uncollect / hide / restore (모두 expected_updated_at 필요)
export const getReceivables = () => apiFetch('/management/receivables/')
export const createReceivable = (body) => apiFetch('/management/receivables/', { method: 'POST', body })
export const updateReceivable = (id, body) => apiFetch(`/management/receivables/${id}/`, { method: 'PUT', body })
export const receivableAction = (id, action, body) => apiFetch(`/management/receivables/${id}/${action}/`, { method: 'POST', body })
export const exportReceivables = (period) => downloadFile(`/management/receivables/export/?${periodParams(period)}`, '미수금.xlsx')
// 한 건의 변경 기록 (type: Receivable)
export const getRowHistory = (type, id) => apiFetch(`/management/history/row/?type=${type}&id=${id}`)
// 경영지원 관리 장부 — 기준년월별 거래처 잔액 (행 추가·수정·숨김·복구, 지난달 내용 불러오기)
export const getLedger = (year, month) => apiFetch(`/management/ledger/?year=${year}&month=${month}`)
export const createLedgerEntry = (year, month, fields) => apiFetch('/management/ledger/', { method: 'POST', body: { year, month, fields } })
export const updateLedgerEntry = (id, fields, expectedUpdatedAt) =>
  apiFetch(`/management/ledger/${id}/`, { method: 'PUT', body: { fields, expected_updated_at: expectedUpdatedAt } })
export const ledgerAction = (id, action, expectedUpdatedAt) =>
  apiFetch(`/management/ledger/${id}/${action}/`, { method: 'POST', body: { expected_updated_at: expectedUpdatedAt } })
export const previewLedgerCopy = (year, month) => apiFetch(`/management/ledger/copy/?year=${year}&month=${month}`)
export const copyLedger = (body) => apiFetch('/management/ledger/copy/', { method: 'POST', body })
// 경영지원 관리 엑셀 이관: 미리보기(저장 안 함) → 같은 파일 + 선택값으로 가져오기
function importForm(file, year, month, extra = {}) {
  const form = new FormData()
  form.append('file', file)
  form.append('year', year)
  form.append('month', month)
  Object.entries(extra).forEach(([k, v]) => v !== undefined && v !== null && form.append(k, v))
  return form
}
export const previewLedgerImport = (file, year, month, sheet) =>
  apiFetch('/management/ledger/import/preview/', { method: 'POST', body: importForm(file, year, month, { sheet }) })
export const importLedger = (file, year, month, extra) =>
  apiFetch('/management/ledger/import/', { method: 'POST', body: importForm(file, year, month, extra) })
// 장부 엑셀 내려받기 — kind: month / quarter / year (숨긴 행 제외, 다시 [엑셀 가져오기]로 올려도 같은 값으로 읽힘)
export function exportLedger(year, kind, month) {
  const params = new URLSearchParams({ year, period: kind })
  if (kind === 'month') params.set('month', month)
  if (kind === 'quarter') params.set('quarter', Math.floor((month - 1) / 3) + 1)
  return downloadFile(`/management/ledger/export/?${params}`, '경영지원_관리.xlsx')
}
// 경영지원 상세 (손익분기점·인당 생산성·미수금 상세·자금 수지 예측 포함)
export const getDetail = (period) => apiFetch(`/management/detail/?${periodParams(period)}`)
// AI 분석 코멘트 — 조회는 저장된 것만 (AI 호출 없음), 생성은 [분석하기] (body: year, quarter, expected_latest_id, consent)
export const getAiComment = (period) => apiFetch(`/management/ai-comment/?${periodParams(period)}`)
export const generateAiComment = (body) => apiFetch('/management/ai-comment/', { method: 'POST', body })
