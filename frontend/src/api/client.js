// 백엔드 API 호출 공통 함수
// - JSON으로 주고받는다
// - 조회(GET)가 아닌 요청에는 CSRF 토큰(위조 요청 방지용)을 헤더에 붙인다
// - 실패하면 status(401, 403 등)와 서버 메시지를 담은 ApiError를 던진다

export class ApiError extends Error {
  constructor(status, data) {
    super((data && data.detail) || `요청 실패 (${status})`)
    this.status = status
    this.data = data
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : ''
}

export async function apiFetch(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers['X-CSRFToken'] = getCookie('csrftoken')

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}
