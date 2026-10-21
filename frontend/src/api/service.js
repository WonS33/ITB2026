import { apiFetch } from './client'
import { periodParams } from '@/period'

export const getServiceDashboard = (period) => apiFetch(`/service/dashboard/?${periodParams(period)}`)
export const getTripReports = (period) => apiFetch(`/service/reports/?${periodParams(period)}`)
export const getTripReport = (id) => apiFetch(`/service/reports/${id}/`)

// 교체 부품 단가 (조회: 서비스 열람 / 추가·삭제: 서비스 수정 권한 — 백엔드에서도 확인함)
export const getPartPrices = () => apiFetch('/service/part-prices/')
export const addPartPrice = (data) => apiFetch('/service/part-prices/', { method: 'POST', body: data })
export const deletePartPrice = (id) => apiFetch(`/service/part-prices/${id}/`, { method: 'DELETE' })

// 요청처 → 시·도·시·군 대응표
export const getRequesterRegions = () => apiFetch('/service/requester-regions/')
export const updateRequesterRegion = (id, data) => apiFetch(`/service/requester-regions/${id}/`, { method: 'PATCH', body: data })
