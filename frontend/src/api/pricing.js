// 제품 단가·원가 (대표·관리자·경영지원팀만 — 백엔드 API에서도 확인)
import { apiFetch } from './client'

// sim: { exchange_rate, margin, option, base } — 값이 있으면 저장하지 않고 다시 계산만 함 (시뮬레이션)
export function getProductPrices(sim = {}) {
  const params = new URLSearchParams()
  Object.entries(sim).forEach(([k, v]) => v !== '' && v !== null && v !== undefined && params.set(k, v))
  return apiFetch(`/pricing/products/?${params}`)
}
export const calcCommission = (model, saleAmount) =>
  apiFetch(`/pricing/commission/?model=${encodeURIComponent(model)}&sale_amount=${encodeURIComponent(saleAmount)}`)
