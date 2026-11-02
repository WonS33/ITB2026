import { apiFetch, downloadFile } from './client'
import { periodParams } from '@/period'

export const getServiceDashboard = (period) => apiFetch(`/service/dashboard/?${periodParams(period)}`)
export const getTripReports = (period) => apiFetch(`/service/reports/?${periodParams(period)}`)
export const getTripReport = (id) => apiFetch(`/service/reports/${id}/`)
// 출장보고서 직접 입력 (서비스 수정 권한). 같은 시작일·요청처가 있으면 409 → allow_duplicate: true로 다시 보냄
export const createTripReport = (data) => apiFetch('/service/reports/', { method: 'POST', body: data })

// 교체 부품 단가 (조회: 서비스 열람 / 추가·삭제: 서비스 수정 권한 — 백엔드에서도 확인함)
export const getPartPrices = () => apiFetch('/service/part-prices/')
export const addPartPrice = (data) => apiFetch('/service/part-prices/', { method: 'POST', body: data })
export const deletePartPrice = (id) => apiFetch(`/service/part-prices/${id}/`, { method: 'DELETE' })

// 요청처 → 시·도·시·군 대응표
export const getRequesterRegions = () => apiFetch('/service/requester-regions/')
export const updateRequesterRegion = (id, data) => apiFetch(`/service/requester-regions/${id}/`, { method: 'PATCH', body: data })

// 부품 단가표: 파트넘버별 뉴토크 기준값 + 출장지(업체)별 평균·최저·최고·최고−최저
export const getPartCatalog = (q = '', category = '') =>
  apiFetch(`/service/part-catalog/?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`)
export const getPartCatalogItem = (id) => apiFetch(`/service/part-catalog/${id}/`)
// 부품별 할인율·추가단가 (null이면 전체 기본값 사용)
export const setPartCatalogItem = (id, body) => apiFetch(`/service/part-catalog/${id}/`, { method: 'PATCH', body })
export const getCatalogChoices = () => apiFetch('/service/part-catalog/choices/')
export const setPriceStandard = (body) => apiFetch('/service/price-standard/', { method: 'PUT', body })
// 출장지(업체)별 비교: 뉴토크 기준값 대비 평균 차이율 + 업체가 견적한 부품별 차이
export const getCompanyComparison = (category = '') =>
  apiFetch(`/service/part-catalog/companies/?category=${encodeURIComponent(category)}`)
// 엑셀 내려받기: 부품 단가표(화면과 같은 검색 조건) / 출장지별 비교(업체 요약 + 부품별 차이)
export const downloadPartCatalog = (q = '', category = '') =>
  downloadFile(`/service/part-catalog/export/?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`, '부품단가.xlsx')
export const downloadCompanyComparison = (category = '') =>
  downloadFile(`/service/part-catalog/companies/export/?category=${encodeURIComponent(category)}`, '출장지별단가비교.xlsx')
