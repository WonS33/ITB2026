import { apiFetch } from './client'

export const fetchMe = () => apiFetch('/auth/me/')
export const login = (username, password) =>
  apiFetch('/auth/login/', { method: 'POST', body: { username, password } })
export const logout = () => apiFetch('/auth/logout/', { method: 'POST' })
export const changePassword = (currentPassword, newPassword) =>
  apiFetch('/auth/password/', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
