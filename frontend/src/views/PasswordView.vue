<script setup>
// 본인 비밀번호 변경 (specs/02-users-permissions.md 5절)
// 첫 로그인이면 안내 문구를 보여주고, [나중에]로 넘어갈 수도 있다 (강제로 막지는 않음)
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth, changePassword, homePath } from '@/auth'
import { checkPassword, SPECIAL_CHARS } from '@/passwordRules'

const router = useRouter()
const route = useRoute()

const current = ref('')
const next = ref('')
const confirm = ref('')
const errors = ref({})
const done = ref(false)
const submitting = ref(false)

const firstLogin = computed(() => auth.user?.must_change_password)
const nextPath = computed(() => route.query.next || homePath())
const rules = computed(() => checkPassword(next.value))

async function submit() {
  errors.value = {}
  if (next.value !== confirm.value) {
    errors.value = { confirm: ['새 비밀번호와 확인이 다릅니다.'] }
    return
  }
  submitting.value = true
  try {
    await changePassword(current.value, next.value)
    done.value = true
    current.value = next.value = confirm.value = ''
  } catch (e) {
    // 서버가 칸별 오류를 돌려줌: { current_password: [...], new_password: [...] }
    errors.value = e.data && typeof e.data === 'object' ? e.data : { detail: [e.message] }
  } finally {
    submitting.value = false
  }
}

const list = (v) => (Array.isArray(v) ? v : v ? [v] : [])
</script>

<template>
  <div style="max-width: 440px">
    <h1 class="h4 mb-3">비밀번호 변경</h1>

    <div v-if="firstLogin && !done" class="alert alert-warning">
      <strong>처음 로그인하셨습니다.</strong> 관리자가 발급한 초기 비밀번호를 본인만 아는 비밀번호로 바꿔 주세요.
    </div>
    <div v-if="done" class="alert alert-success">
      비밀번호를 바꿨습니다.
      <RouterLink :to="nextPath" class="alert-link ms-1">화면으로 이동</RouterLink>
    </div>

    <form v-if="!done" class="card card-body" @submit.prevent="submit">
      <div class="mb-3">
        <label class="form-label" for="current">현재 비밀번호</label>
        <input id="current" v-model="current" type="password" class="form-control" autocomplete="current-password"
               :class="{ 'is-invalid': errors.current_password }" required />
        <div v-for="m in list(errors.current_password)" :key="m" class="invalid-feedback">{{ m }}</div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="new">새 비밀번호</label>
        <input id="new" v-model="next" type="password" class="form-control" autocomplete="new-password"
               :class="{ 'is-invalid': errors.new_password }" required />
        <div v-for="m in list(errors.new_password)" :key="m" class="invalid-feedback">{{ m }}</div>
        <!-- 입력하는 동안 규칙을 지켰는지 바로 보여준다 (최종 검사는 서버) -->
        <ul class="list-unstyled small mt-2 mb-1">
          <li v-for="r in rules" :key="r.label" :class="r.ok ? 'text-success' : 'text-muted'">
            {{ r.ok ? '✔' : '○' }} {{ r.label }}
          </li>
        </ul>
        <div class="form-text">
          쓸 수 있는 특수기호: <code class="user-select-all">{{ SPECIAL_CHARS }}</code><br />
          흔한 비밀번호(예: password1!), 아이디·이름과 비슷한 비밀번호는 쓸 수 없습니다.
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label" for="confirm">새 비밀번호 확인</label>
        <input id="confirm" v-model="confirm" type="password" class="form-control" autocomplete="new-password"
               :class="{ 'is-invalid': errors.confirm }" required />
        <div v-for="m in list(errors.confirm)" :key="m" class="invalid-feedback">{{ m }}</div>
      </div>
      <div v-for="m in list(errors.detail)" :key="m" class="alert alert-danger py-2">{{ m }}</div>
      <div class="d-flex gap-2">
        <button class="btn btn-primary" :disabled="submitting">변경</button>
        <button v-if="firstLogin" type="button" class="btn btn-outline-secondary" @click="router.push(nextPath)">나중에</button>
      </div>
    </form>
  </div>
</template>
