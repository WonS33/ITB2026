import { apiFetch } from './client'
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
