import { apiFetch } from './client'

// 관리자 페이지 API (대표·관리자·경영지원팀만 — 백엔드에서도 확인함)
export const fetchUsers = () => apiFetch('/admin/users/')
export const resetPassword = (id) => apiFetch(`/admin/users/${id}/reset-password/`, { method: 'POST' })
export const updateUser = (id, data) => apiFetch(`/admin/users/${id}/`, { method: 'PATCH', body: data })
