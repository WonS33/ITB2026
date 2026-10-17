import { apiFetch } from './client'
import { periodParams } from '@/period'

export const getTarget = (year) => apiFetch(`/production/targets/${year}/`)
export const putTarget = (year, targetQuantity) =>
  apiFetch(`/production/targets/${year}/`, { method: 'PUT', body: { target_quantity: targetQuantity } })
export const getDashboard = (period) => apiFetch(`/production/dashboard/?${periodParams(period)}`)
