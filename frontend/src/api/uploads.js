import { apiFetch } from './client'

export function uploadFile(kind, file) {
  const form = new FormData()
  form.append('kind', kind)
  form.append('file', file)
  return apiFetch('/uploads/', { method: 'POST', body: form })
}

// rows: [{ id, values: {...}, excluded }]
export const updateBatch = (id, rows) => apiFetch(`/uploads/${id}/`, { method: 'PATCH', body: { rows } })
export const confirmBatch = (id) => apiFetch(`/uploads/${id}/confirm/`, { method: 'POST' })
export const cancelBatch = (id) => apiFetch(`/uploads/${id}/cancel/`, { method: 'POST' })
