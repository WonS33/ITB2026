<script setup>
// 관리자 설정 (specs/02-users-permissions.md 6절)
// 지금 단계: 직원 목록 보기 + 비밀번호 초기화. 권한 체크박스·계정 발급은 다음 단계에서 추가한다.
import { onMounted, ref } from 'vue'
import { fetchUsers, resetPassword } from '@/api/admin'
import { auth, TEAM_LABELS } from '@/auth'

const users = ref([])
const loading = ref(true)
const error = ref('')
const resetResult = ref(null) // { name, username, temporary_password } — 화면을 떠나면 사라짐
const copied = ref(false)
const resettingId = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    users.value = await fetchUsers()
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
    users.value = users.value.map((u) => (u.id === user.id ? res.user : u))
  } catch (e) {
    error.value = e.message
  } finally {
    resettingId.value = null
  }
}

async function copyPassword() {
  try {
    await navigator.clipboard.writeText(resetResult.value.temporary_password)
    copied.value = true
  } catch {
    copied.value = false // 복사가 막힌 브라우저면 직접 선택해서 복사
  }
}

const teams = (list) => list.map((t) => TEAM_LABELS[t]).join(', ') || '-'
const formatDate = (iso) => (iso ? new Date(iso).toLocaleString('ko-KR') : '로그인 기록 없음')

onMounted(load)
</script>

<template>
  <div>
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

    <div class="card">
      <div class="card-header">직원 목록</div>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>아이디</th>
              <th>이름</th>
              <th>역할</th>
              <th>열람 범위</th>
              <th>수정 권한</th>
              <th>비밀번호</th>
              <th>마지막 로그인</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="8" class="text-center text-muted py-3">불러오는 중…</td></tr>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.username }}</td>
              <td>{{ u.name }}</td>
              <td>{{ u.role_display }}</td>
              <td>{{ u.has_full_access ? '전체' : teams(u.view_teams) }}</td>
              <td>{{ u.has_full_access ? '전체' : teams(u.edit_teams) }}</td>
              <td>
                <span v-if="u.must_change_password" class="badge bg-warning text-dark">초기 비밀번호 사용 중</span>
                <span v-else class="badge bg-light text-dark border">본인이 변경함</span>
              </td>
              <td class="small text-muted">{{ formatDate(u.last_login) }}</td>
              <td class="text-end">
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
    </div>
  </div>
</template>
