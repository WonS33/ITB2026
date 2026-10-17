// 백엔드 API 호출 공통 함수
// - JSON으로 주고받는다
// - 조회(GET)가 아닌 요청에는 CSRF 토큰(위조 요청 방지용)을 헤더에 붙인다
// - 실패하면 status(401, 403 등)와 서버 메시지를 담은 ApiError를 던진다

export class ApiError extends Error {
  constructor(status, data) {
    super(firstMessage(data) || `요청 실패 (${status})`)
    this.status = status
    this.data = data
  }
}

// 서버 오류 메시지 꺼내기: {"detail": "..."} 또는 {"file": ["..."]} 모양
function firstMessage(data) {
  if (!data || typeof data !== 'object') return ''
  if (data.detail) return data.detail
  const first = Object.values(data)[0]
  return Array.isArray(first) ? first[0] : typeof first === 'string' ? first : ''
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : ''
}

// body가 FormData(파일 업로드)이면 그대로 보내고, 그 외에는 JSON으로 바꿔 보낸다
export async function apiFetch(path, { method = 'GET', body } = {}) {
  const isForm = body instanceof FormData
  const headers = { Accept: 'application/json' }
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (method !== 'GET') headers['X-CSRFToken'] = getCookie('csrftoken')

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}
