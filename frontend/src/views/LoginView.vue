<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { homePath, login } from '@/auth'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    await login(username.value, password.value)
    router.replace(route.query.next || homePath())
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="container py-5" style="max-width: 400px">
    <h1 class="h4 mb-4 text-center">경영지표 대시보드</h1>
    <form class="card card-body" @submit.prevent="submit">
      <div class="mb-3">
        <label class="form-label" for="username">아이디</label>
        <input id="username" v-model="username" class="form-control" autocomplete="username" required />
      </div>
      <div class="mb-3">
        <label class="form-label" for="password">비밀번호</label>
        <input
          id="password"
          v-model="password"
          type="password"
          class="form-control"
          autocomplete="current-password"
          required
        />
      </div>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <button class="btn btn-primary w-100" :disabled="submitting">로그인</button>
      <p class="text-muted small mt-3 mb-0">계정은 경영지원팀에서 발급합니다. 비밀번호를 잊었으면 관리자에게 초기화를 요청하세요.</p>
    </form>
  </div>
</template>
