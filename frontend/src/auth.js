// 로그인한 사용자 정보를 화면 전체에서 함께 쓰기 위한 저장소
// (화면에서 메뉴·버튼을 숨기는 용도일 뿐, 실제 권한 확인은 백엔드 API에서 한다)
import { reactive } from 'vue'
import * as authApi from './api/auth'

export const auth = reactive({
  user: null, // 로그인 안 했으면 null
  loaded: false, // 처음 한 번 /me 를 확인했는지
})

export const TEAM_LABELS = { production: '생산팀', service: '서비스팀' }
export const TEAM_ROUTES = { production: '/production', service: '/service' }

export async function loadMe() {
  try {
    auth.user = await authApi.fetchMe()
  } catch {
    auth.user = null
  }
  auth.loaded = true
}

export async function login(username, password) {
  auth.user = await authApi.login(username, password)
}

export async function logout() {
  await authApi.logout()
  auth.user = null
}

// 본인 비밀번호 변경 → 첫 로그인 안내(must_change_password)가 꺼진 최신 정보로 바꾼다
export async function changePassword(currentPassword, newPassword) {
  auth.user = await authApi.changePassword(currentPassword, newPassword)
}

export const canView = (team) => !!auth.user && auth.user.view_teams.includes(team)
export const canEdit = (team) => !!auth.user && auth.user.edit_teams.includes(team)

// 로그인 직후·첫 화면으로 보낼 주소: 볼 수 있는 첫 팀 화면
export function homePath() {
  const team = auth.user?.view_teams[0]
  return team ? TEAM_ROUTES[team] : '/forbidden'
}
