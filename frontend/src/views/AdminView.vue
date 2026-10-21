<script setup>
// 관리자 설정 (specs/02-users-permissions.md 6절)
// 직원 목록 + 역할·열람 범위·수정 권한 변경 + 비밀번호 초기화. 계정 발급은 다음 단계.
// 권한 변경은 바로 저장하지 않는다: 표에서 바꾼 값은 임시로 두고(drafts),
// 맨 아래 [변경] → 확인 팝업에서 바뀌는 내용을 확인 → [확인]을 눌러야 서버에 저장한다.
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { fetchUsers, resetPassword, updateUser } from '@/api/admin'
import { auth, loadMe, TEAM_LABELS } from '@/auth'

// 백엔드 User.Role과 같은 값. 대표·관리자는 팀 체크와 관계없이 전체 권한
const ROLE_OPTIONS = [
  { value: 'ceo', label: '대표' },
  { value: 'admin', label: '관리자' },
  { value: 'leader', label: '팀장' },
  { value: 'member', label: '팀원' },
]
const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map((r) => [r.value, r.label]))
const FULL_ACCESS_ROLES = ['ceo', 'admin']
// 경영지원팀 소속(열람 범위에 체크)이면 팀장·팀원 모두 전체 권한 — 백엔드 User.FULL_ACCESS_TEAM과 같음
const FULL_ACCESS_TEAM = 'management'
const TEAMS = Object.keys(TEAM_LABELS) // 경영지원팀, 생산팀, 서비스팀
const EDIT_TEAMS = TEAMS.filter((t) => t !== FULL_ACCESS_TEAM) // 경영지원팀은 소속만으로 전체 수정이라 따로 체크 안 함
const FIELDS = [
  { key: 'role', label: '역할' },
  { key: 'view_teams', label: '열람 범위' },
  { key: 'edit_teams', label: '수정 권한' },
]

const users = ref([]) // 서버에 저장된 값
const drafts = reactive({}) // 직원 id → 화면에서 바꾸고 있는 값 { role, view_teams, edit_teams }
const loading = ref(true)
const error = ref('')
const notice = ref('')
const resetResult = ref(null) // { name, username, temporary_password } — 화면을 떠나면 사라짐
const copied = ref(false)
const resettingId = ref(null)
const showConfirm = ref(false)
const saving = ref(false)

// r: { role, view_teams } — 저장된 값(users)이나 바꾸고 있는 값(drafts) 모두 같은 모양
const isFullAccessRole = (role) => FULL_ACCESS_ROLES.includes(role)
const inFullAccessTeam = (r) => r.view_teams.includes(FULL_ACCESS_TEAM)
const isFullAccess = (r) => isFullAccessRole(r.role) || inFullAccessTeam(r)
const teamNames = (list) => list.map((t) => TEAM_LABELS[t]).join(', ')

// 소속팀(보여주기만, DB 항목 아님): 열람 범위에 체크된 팀. 대표·관리자는 팀 체크가 없으면 '-'
const affiliation = (d) => teamNames(d.view_teams) || (isFullAccessRole(d.role) ? '-' : '없음')
const sameList = (a, b) => a.length === b.length && a.every((v) => b.includes(v))

function resetDraft(user) {
  drafts[user.id] = { role: user.role, view_teams: [...user.view_teams], edit_teams: [...user.edit_teams] }
}

// 저장된 값과 다른 항목만 골라 낸다 → 줄 강조, 확인 팝업, 서버로 보낼 값에 함께 쓴다
function changedFields(user) {
  const d = drafts[user.id]
  if (!d) return []
  return FIELDS.filter(({ key }) => (key === 'role' ? d.role !== user.role : !sameList(d[key], user[key])))
}

const changes = computed(() =>
  users.value
    .map((user) => ({ user, fields: changedFields(user) }))
    .filter((c) => c.fields.length > 0),
)

// 확인 팝업에 보여줄 글자. 대표·관리자는 "전체", 경영지원팀 소속은 수정 권한이 "전체"
function display(key, r) {
  if (key === 'role') return ROLE_LABELS[r.role]
  if (isFullAccessRole(r.role)) return '전체'
  if (key === 'edit_teams' && inFullAccessTeam(r)) return '전체'
  const names = teamNames(r[key]) || '없음'
  return key === 'view_teams' && inFullAccessTeam(r) ? `${names} (전체 권한)` : names
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    users.value = await fetchUsers()
    users.value.forEach(resetDraft)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function onReset(user) {
  if (!confirm(`${user.name}(${user.username})의 비밀번호를 초기화할까요?\n지금 쓰던 비밀번호로는 더 이상 로그인할 수 없습니다.`)) return
  resettingId.value = user.id
  error.value = ''
  copied.value = false
  try {
    const res = await resetPassword(user.id)
    resetResult.value = { name: user.name, username: user.username, temporary_password: res.temporary_password }
    users.value = users.value.map((u) => (u.id === user.id ? res.user : u)) // 권한 임시 변경(drafts)은 그대로 둠
  } catch (e) {
    error.value = e.message
  } finally {
    resettingId.value = null
  }
}

// 수정 권한을 켜면 열람도 함께 켜고, 열람을 끄면 수정도 함께 끈다 (서버 규칙: 수정 ⊂ 열람)
function onTeamToggle(user, kind, team, checked) {
  const d = drafts[user.id]
  const add = (list) => (list.includes(team) ? list : [...list, team])
  const remove = (list) => list.filter((t) => t !== team)
  if (kind === 'view') {
    d.view_teams = checked ? add(d.view_teams) : remove(d.view_teams)
    if (!checked) d.edit_teams = remove(d.edit_teams)
  } else {
    d.edit_teams = checked ? add(d.edit_teams) : remove(d.edit_teams)
    if (checked) d.view_teams = add(d.view_teams)
  }
  notice.value = ''
}

function undoAll() {
  users.value.forEach(resetDraft)
  notice.value = ''
}

// 확인 팝업의 [확인]: 바뀐 직원마다 바뀐 항목만 서버에 보낸다.
// 실패한 직원은 임시 변경을 그대로 남겨 두고 이유를 보여준다(성공한 직원은 저장됨).
async function applyChanges() {
  saving.value = true
  error.value = ''
  notice.value = ''
  const failed = []
  let savedCount = 0
  let changedMe = false
  for (const { user, fields } of changes.value) {
    const data = Object.fromEntries(fields.map(({ key }) => [key, drafts[user.id][key]]))
    try {
      const updated = await updateUser(user.id, data)
      users.value = users.value.map((u) => (u.id === user.id ? updated : u))
      resetDraft(updated)
      savedCount += 1
      if (user.id === auth.user.id) changedMe = true
    } catch (e) {
      failed.push(`${user.name}: ${e.message}`)
    }
  }
  if (changedMe) await loadMe() // 내 권한을 바꿨으면 메뉴도 새로 그림
  saving.value = false
  showConfirm.value = false
  if (savedCount) notice.value = `${savedCount}명의 권한을 변경했습니다. 그 직원의 메뉴는 새로고침하면 바뀝니다.`
  if (failed.length) error.value = `저장하지 못한 직원이 있습니다 — ${failed.join(' / ')}`
}

async function copyPassword() {
  try {
    await navigator.clipboard.writeText(resetResult.value.temporary_password)
    copied.value = true
  } catch {
    copied.value = false // 복사가 막힌 브라우저면 직접 선택해서 복사
  }
}

const formatDate = (iso) => (iso ? new Date(iso).toLocaleString('ko-KR') : '로그인 기록 없음')

// 저장하지 않은 변경이 있는데 다른 화면으로 가거나 새로고침하면 한 번 묻는다
const LEAVE_MESSAGE = '저장하지 않은 권한 변경이 있습니다. 이 화면을 떠나면 변경 내용이 사라집니다. 떠날까요?'
onBeforeRouteLeave(() => changes.value.length === 0 || confirm(LEAVE_MESSAGE))
function onBeforeUnload(e) {
  if (changes.value.length) e.preventDefault()
}

onMounted(() => {
  load()
  window.addEventListener('beforeunload', onBeforeUnload)
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
</script>

<template>
  <div class="pb-5">
    <h1 class="h4 mb-3">관리자 설정</h1>

    <!-- 임시 비밀번호는 이때 한 번만 보인다 (서버에는 해시만 저장됨) -->
    <div v-if="resetResult" class="alert alert-success">
      <div class="mb-2">
        <strong>{{ resetResult.name }}({{ resetResult.username }})</strong>의 비밀번호를 초기화했습니다.
        아래 임시 비밀번호를 본인에게 직접 전달해 주세요.
      </div>
      <div class="d-flex align-items-center gap-2 mb-2">
        <code class="fs-5 user-select-all bg-white px-2 py-1 border rounded">{{ resetResult.temporary_password }}</code>
        <button class="btn btn-sm btn-outline-success" @click="copyPassword">{{ copied ? '복사됨' : '복사' }}</button>
      </div>
      <div class="small">
        ⚠ 이 비밀번호는 <strong>지금만</strong> 볼 수 있습니다. 이 안내를 닫거나 화면을 옮기면 다시 볼 수 없으니, 잃어버리면 한 번 더 초기화하세요.
        직원이 이 비밀번호로 로그인하면 비밀번호 변경 안내가 나옵니다.
      </div>
      <button class="btn btn-sm btn-success mt-2" @click="resetResult = null">전달했습니다 (닫기)</button>
    </div>

    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="notice" class="alert alert-success py-2">{{ notice }}</div>

    <div class="card">
      <div class="card-header">
        직원 목록
        <span class="small text-muted ms-2">역할·체크박스를 바꾼 뒤 맨 아래 [변경]을 눌러야 저장됩니다. 바뀐 줄은 노란색으로 표시됩니다.</span>
      </div>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>아이디</th>
              <th>이름</th>
              <th>소속팀</th>
              <th>역할</th>
              <th>열람 범위</th>
              <th>수정 권한</th>
              <th>마지막 로그인</th>
              <th class="text-end">비밀번호</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="8" class="text-center text-muted py-3">불러오는 중…</td></tr>
            <tr v-for="u in users" :key="u.id" :class="{ 'table-warning': changedFields(u).length }">
              <td>{{ u.username }}</td>
              <td>{{ u.name }}</td>
              <td>{{ affiliation(drafts[u.id]) }}</td>
              <td>
                <!-- 본인 역할은 바꿀 수 없음 (관리자 페이지 권한을 실수로 없애지 않게, 서버에서도 막음) -->
                <select
                  v-model="drafts[u.id].role"
                  class="form-select form-select-sm"
                  style="width: 8rem"
                  :disabled="u.id === auth.user.id || saving"
                  @change="notice = ''"
                >
                  <option v-for="r in ROLE_OPTIONS" :key="r.value" :value="r.value">{{ r.label }}</option>
                </select>
              </td>
              <!-- 열람 범위: 경영지원팀을 체크하면 전체 권한이라 생산·서비스 체크는 숨긴다 -->
              <td>
                <span v-if="isFullAccessRole(drafts[u.id].role)" class="text-muted">전체</span>
                <template v-else>
                  <template v-for="team in TEAMS" :key="team">
                    <div
                      v-if="team === FULL_ACCESS_TEAM || !inFullAccessTeam(drafts[u.id])"
                      class="form-check form-check-inline mb-0"
                    >
                      <!-- 본인의 경영지원팀 소속은 뺄 수 없음 (관리자 페이지 권한 보호, 서버에서도 막음) -->
                      <input
                        :id="`view-${u.id}-${team}`"
                        class="form-check-input"
                        type="checkbox"
                        :checked="drafts[u.id].view_teams.includes(team)"
                        :disabled="saving || (team === FULL_ACCESS_TEAM && u.id === auth.user.id)"
                        @change="onTeamToggle(u, 'view', team, $event.target.checked)"
                      />
                      <label class="form-check-label small" :for="`view-${u.id}-${team}`">{{ TEAM_LABELS[team] }}</label>
                    </div>
                  </template>
                  <span v-if="inFullAccessTeam(drafts[u.id])" class="small text-muted">→ 전체 권한</span>
                </template>
              </td>
              <!-- 수정 권한: 생산팀·서비스팀만 체크 (대표·관리자·경영지원팀 소속은 전체) -->
              <td>
                <span v-if="isFullAccess(drafts[u.id])" class="text-muted">전체</span>
                <template v-else>
                  <div v-for="team in EDIT_TEAMS" :key="team" class="form-check form-check-inline mb-0">
                    <input
                      :id="`edit-${u.id}-${team}`"
                      class="form-check-input"
                      type="checkbox"
                      :checked="drafts[u.id].edit_teams.includes(team)"
                      :disabled="saving"
                      @change="onTeamToggle(u, 'edit', team, $event.target.checked)"
                    />
                    <label class="form-check-label small" :for="`edit-${u.id}-${team}`">{{ TEAM_LABELS[team] }}</label>
                  </div>
                </template>
              </td>
              <td class="small text-muted">{{ formatDate(u.last_login) }}</td>
              <td class="text-end text-nowrap">
                <span v-if="u.must_change_password" class="small text-muted me-2">초기 비밀번호 사용 중</span>
                <!-- 본인 비밀번호는 [비밀번호 변경] 메뉴에서 바꾼다 (서버에서도 막음) -->
                <button
                  v-if="u.id !== auth.user.id"
                  class="btn btn-sm btn-outline-danger"
                  :disabled="resettingId === u.id"
                  @click="onReset(u)"
                >
                  비밀번호 초기화
                </button>
                <span v-else class="small text-muted">본인</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 맨 아래: 바뀐 내용 개수 + [되돌리기] + [변경] -->
      <div class="card-footer d-flex align-items-center justify-content-end gap-2">
        <span class="small me-auto" :class="changes.length ? 'text-dark' : 'text-muted'">
          {{ changes.length ? `권한이 바뀐 직원 ${changes.length}명 (아직 저장 안 됨)` : '바뀐 내용이 없습니다.' }}
        </span>
        <button class="btn btn-outline-secondary" :disabled="!changes.length || saving" @click="undoAll">되돌리기</button>
        <button class="btn btn-primary" :disabled="!changes.length || saving" @click="showConfirm = true">변경</button>
      </div>
    </div>

    <!-- 확인 팝업: 무엇이 어떻게 바뀌는지 보여주고 [확인]을 눌러야 저장 -->
    <template v-if="showConfirm">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="confirm-title" class="modal-title h5">권한 변경 확인</h2>
              <button type="button" class="btn-close" aria-label="닫기" :disabled="saving" @click="showConfirm = false"></button>
            </div>
            <div class="modal-body">
              <p class="mb-2">아래 {{ changes.length }}명의 권한이 바뀝니다. 맞으면 [확인]을 눌러 주세요.</p>
              <table class="table table-sm table-bordered align-middle mb-0">
                <thead class="table-light">
                  <tr>
                    <th>직원</th>
                    <th>항목</th>
                    <th>변경 전</th>
                    <th></th>
                    <th>변경 후</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="c in changes" :key="c.user.id">
                    <tr v-for="(f, i) in c.fields" :key="f.key">
                      <td v-if="i === 0" :rowspan="c.fields.length">{{ c.user.name }}<br /><span class="small text-muted">{{ c.user.username }}</span></td>
                      <td>{{ f.label }}</td>
                      <td class="text-muted">{{ display(f.key, c.user) }}</td>
                      <td class="text-center">→</td>
                      <td class="fw-semibold">{{ display(f.key, drafts[c.user.id]) }}</td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" :disabled="saving" @click="showConfirm = false">취소</button>
              <button type="button" class="btn btn-primary" :disabled="saving" @click="applyChanges">
                {{ saving ? '저장 중…' : '확인' }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>
