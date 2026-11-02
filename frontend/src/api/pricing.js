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
// 기준값 변경 기록 / 화면에서 기준값 바꾸기 (새 적용일로 저장, 예전 값은 기록으로 남음)
export const getPriceSettings = () => apiFetch('/pricing/settings/')
export const savePriceSetting = (body) => apiFetch('/pricing/settings/', { method: 'POST', body })
// 대외비 화면 열람 기록 (최근 100건)
export const getAccessLog = () => apiFetch('/pricing/access-log/')
