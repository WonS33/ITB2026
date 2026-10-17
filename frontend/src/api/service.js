import { apiFetch } from './client'
import { periodParams } from '@/period'

export const getServiceDashboard = (period) => apiFetch(`/service/dashboard/?${periodParams(period)}`)
export const getTripReports = (period) => apiFetch(`/service/reports/?${periodParams(period)}`)
export const getTripReport = (id) => apiFetch(`/service/reports/${id}/`)
