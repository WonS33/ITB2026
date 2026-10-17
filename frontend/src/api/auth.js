import { apiFetch } from './client'

export const fetchMe = () => apiFetch('/auth/me/')
export const login = (username, password) =>
  apiFetch('/auth/login/', { method: 'POST', body: { username, password } })
export const logout = () => apiFetch('/auth/logout/', { method: 'POST' })
