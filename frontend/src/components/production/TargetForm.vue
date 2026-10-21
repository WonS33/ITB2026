<script setup>
// 연간 목표 생산량: 열람 권한자는 보기만, 수정 권한자는 입력·저장
import { ref, watch } from 'vue'
import { canEdit } from '@/auth'
import { getTarget, putTarget } from '@/api/production'

const props = defineProps({ year: { type: Number, required: true } })
const emit = defineEmits(['saved'])

const target = ref(null) // 저장된 값
const input = ref('')
const editing = ref(false)
const message = ref('')
const error = ref('')

async function load() {
  error.value = ''
  editing.value = false
  try {
    target.value = (await getTarget(props.year)).target_quantity
  } catch (e) {
    error.value = e.message
  }
}

function startEdit() {
  input.value = target.value ?? ''
  message.value = ''
  editing.value = true
}

async function save() {
  error.value = ''
  try {
    target.value = (await putTarget(props.year, Number(input.value))).target_quantity
    editing.value = false
    message.value = '저장했습니다.'
    emit('saved')
  } catch (e) {
    error.value = e.data?.target_quantity?.[0] || e.message
  }
}

watch(() => props.year, load, { immediate: true })
</script>

<template>
  <!-- 대시보드 제목 줄 옆에 한 줄로 표시 (연 1회 입력하는 값이라 작게) -->
  <div class="d-flex flex-wrap align-items-center gap-2 small">
    <span class="text-muted">{{ year }}년 연간 목표 생산량</span>
    <strong v-if="!editing">{{ target === null ? '미입력' : `${target.toLocaleString()}대` }}</strong>
    <form v-else class="d-flex gap-2" @submit.prevent="save">
      <input v-model="input" type="number" min="0" class="form-control form-control-sm" style="width: 7rem"
             aria-label="연간 목표 생산량" required />
      <button class="btn btn-primary btn-sm">저장</button>
      <button type="button" class="btn btn-outline-secondary btn-sm" @click="editing = false">취소</button>
    </form>
    <button v-if="canEdit('production') && !editing" class="btn btn-outline-primary btn-sm py-0" @click="startEdit">
      {{ target === null ? '목표 입력' : '목표 수정' }}
    </button>
    <span v-if="message" class="text-success">{{ message }}</span>
    <span v-if="error" class="text-danger">{{ error }}</span>
  </div>
</template>
