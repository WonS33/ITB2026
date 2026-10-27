<script setup>
// 업로드 이력 (생산팀·서비스팀 공통): 언제·누가·어떤 파일을 올려 몇 건이 저장됐는지
// 라우터 meta.team 으로 어느 팀 이력인지 정한다 (백엔드도 그 팀 수정 권한을 확인)
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getUploadHistory } from '@/api/uploads'

const route = useRoute()
const team = computed(() => route.meta.team)
const data = ref(null)
const error = ref('')
const kind = ref('') // 파일 종류 걸러내기

async function load() {
  error.value = ''
  data.value = null
  kind.value = ''
  try {
    data.value = await getUploadHistory(team.value)
  } catch (e) {
    error.value = e.message
  }
}
watch(team, load, { immediate: true })

const kinds = computed(() => [...new Map((data.value?.results || []).map((r) => [r.kind, r.kind_display])).entries()])
const rows = computed(() => (data.value?.results || []).filter((r) => !kind.value || r.kind === kind.value))

// 상태: 기호 + 글자 (색만으로 구분하지 않음)
const STATUS = {
  saved: { icon: '✓', cls: 'text-success' },
  extracted: { icon: '…', cls: 'text-warning-emphasis' },
  cancelled: { icon: '✕', cls: 'text-muted' },
}
const when = (iso) => {
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <div class="card mb-4"><div class="card-body">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <h2 class="h6 mb-0">업로드 이력 <span class="text-muted fw-normal small">· 최근 {{ data?.limit ?? 100 }}건까지</span></h2>
      <select v-if="kinds.length > 1" v-model="kind" class="form-select form-select-sm w-auto" aria-label="파일 종류">
        <option value="">모든 파일 종류</option>
        <option v-for="[value, label] in kinds" :key="value" :value="value">{{ label }}</option>
      </select>
    </div>

    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <template v-if="data">
      <p v-if="!rows.length" class="text-muted small mb-0">업로드 기록이 없습니다.</p>
      <div v-else class="table-responsive" style="max-height: 70vh">
        <table class="table table-sm small mb-0 align-middle">
          <thead class="table-light sticky-top">
            <tr><th>올린 시각</th><th>올린 사람</th><th>종류</th><th>파일 이름</th><th>상태</th><th class="text-end">추출</th><th class="text-end">저장</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id" :class="{ 'text-muted': r.status === 'cancelled' }">
              <td class="text-nowrap">{{ when(r.created_at) }}</td>
              <td class="text-nowrap">{{ r.uploaded_by }}</td>
              <td class="text-nowrap">{{ r.kind_display }}</td>
              <td class="text-break">{{ r.file_name }}</td>
              <td class="text-nowrap" :class="STATUS[r.status]?.cls">{{ STATUS[r.status]?.icon }} {{ r.status_display }}</td>
              <td class="text-end">{{ r.row_count }}행</td>
              <td class="text-end">{{ r.status === 'saved' ? `${r.saved_count}건` : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-muted small mt-2 mb-0">
        추출 = 파일에서 읽어 확인 화면에 올라온 행 수, 저장 = 실제로 저장된 건수(이미 있던 번호·제외한 행은 빠짐).
        "확인 대기"는 확인 화면에서 저장·취소하지 않고 나간 업로드입니다. 원본 파일은 보관하지 않습니다.
      </p>
    </template>
  </div></div>
</template>
