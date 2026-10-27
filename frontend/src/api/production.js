import { apiFetch, downloadFile } from './client'
import { periodParams } from '@/period'

export const getTarget = (year) => apiFetch(`/production/targets/${year}/`)
export const putTarget = (year, targetQuantity) =>
  apiFetch(`/production/targets/${year}/`, { method: 'PUT', body: { target_quantity: targetQuantity } })
export const getDashboard = (period) => apiFetch(`/production/dashboard/?${periodParams(period)}`)
export const searchSerials = (q) => apiFetch(`/production/serials/?q=${encodeURIComponent(q)}`)
export const getSerial = (serialFull) => apiFetch(`/production/serials/${encodeURIComponent(serialFull)}/`)
export const getDueCalendar = (year, month) => apiFetch(`/production/due-calendar/?year=${year}&month=${month}`)
// 납기 임박 (오늘 기준: 14일 안 + 납기 지남, 출고가 끝나지 않은 수주)
export const getDueSoon = () => apiFetch('/production/due-soon/')
// 납기 캘린더 검색 (모든 달: 수주번호·판매처·사업명·일련번호·거래처 주문번호)
export const searchDue = (q) => apiFetch(`/production/due-calendar/search/?q=${encodeURIComponent(q)}`)

// 목록 화면: 기간 + 걸러내기 조건(빈 값은 빼고 보냄) + 쪽 번호
function listParams(period, filters = {}, page) {
  const params = new URLSearchParams(periodParams(period))
  Object.entries(filters).forEach(([k, v]) => v && params.set(k, v))
  if (page) params.set('page', page)
  return params.toString()
}
// 제조내역 목록 (제조년월 기준) — filters: { q, model, shipped: 'yes'|'no' }
export const getRecords = (period, filters, page) => apiFetch(`/production/records/?${listParams(period, filters, page)}`)
export const exportRecords = (period, filters) =>
  downloadFile(`/production/records/export/?${listParams(period, filters)}`, '제조내역.xlsx')
// 수주 내역 목록 (납기일 기준) — filters: { q, industry }
export const getOrders = (period, filters, page) => apiFetch(`/production/orders/?${listParams(period, filters, page)}`)
export const exportOrders = (period, filters) =>
  downloadFile(`/production/orders/export/?${listParams(period, filters)}`, '수주내역.xlsx')
// 판매 실적 (설정: date_basis, customer_basis, product_group, compare / 교차 필터: industry, customer, product)
export const getSales = (period, options) => apiFetch(`/production/sales/?${listParams(period, options)}`)
