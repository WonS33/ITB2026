<script setup>
// 파일 업로드 카드: 파일 선택 → 업로드(추출) → 확인 표(UploadReview) → 저장
import { ref } from 'vue'
import UploadReview from '@/components/UploadReview.vue'
import { uploadFile } from '@/api/uploads'

const props = defineProps({
  kind: { type: String, required: true }, // 예: manufacturing_excel
  title: { type: String, required: true },
  accept: { type: String, default: '' }, // 예: .xlsx
  help: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const fileInput = ref(null)
const batch = ref(null)
const busy = ref(false)
const error = ref('')
const message = ref('')

async function upload() {
  const file = fileInput.value.files[0]
  if (!file) {
    error.value = '파일을 선택해 주세요.'
    return
  }
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    batch.value = await uploadFile(props.kind, file)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

function finish(text) {
  batch.value = null
  fileInput.value.value = ''
  message.value = text
}

function onSaved(result) {
  finish(`${result.saved_count}행을 저장했습니다.`)
  emit('saved')
}
</script>

<template>
  <div class="card mb-4">
    <div class="card-body">
      <h2 class="h6">{{ title }}</h2>
      <p v-if="help" class="text-muted small">{{ help }}</p>
      <div v-show="!batch" class="d-flex flex-wrap gap-2">
        <input ref="fileInput" type="file" :accept="accept" class="form-control form-control-sm w-auto" />
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="upload">
          {{ busy ? '추출 중…' : '업로드' }}
        </button>
      </div>
      <div v-if="error" class="alert alert-danger py-2 mt-2 mb-0">{{ error }}</div>
      <div v-if="message" class="alert alert-success py-2 mt-2 mb-0">{{ message }}</div>
      <UploadReview
        v-if="batch"
        :batch="batch"
        class="mt-2"
        @update="batch = $event"
        @saved="onSaved"
        @cancelled="finish('업로드를 취소했습니다.')"
      />
    </div>
  </div>
</template>
