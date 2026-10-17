<script setup>
// 업로드 확인·수정 표 (specs/03-common.md 4절 ③④⑤)
// - 오류 칸은 빨간색 + 메시지, 이미 저장된 번호는 "중복(건너뜀)", 행마다 "제외" 선택
// - [다시 검사]: 고친 값을 서버에 보내 다시 검사 / [저장]: 고친 값 반영 후 최종 저장
import { reactive, ref, watch } from 'vue'
import { cancelBatch, confirmBatch, updateBatch } from '@/api/uploads'

const props = defineProps({ batch: { type: Object, required: true } })
const emit = defineEmits(['update', 'saved', 'cancelled'])

const drafts = reactive({}) // 행 id → { values, excluded } (화면에서 고친 값)
const busy = ref(false)
const error = ref('')

function resetDrafts(batch) {
  for (const key of Object.keys(drafts)) delete drafts[key]
  for (const row of batch.rows) {
    drafts[row.id] = { values: { ...row.values }, excluded: row.excluded }
  }
}
watch(() => props.batch, resetDrafts, { immediate: true })

function changedRows() {
  return props.batch.rows
    .filter((row) => {
      const d = drafts[row.id]
      return d.excluded !== row.excluded || Object.keys(d.values).some((k) => d.values[k] !== row.values[k])
    })
    .map((row) => ({ id: row.id, values: drafts[row.id].values, excluded: drafts[row.id].excluded }))
}

async function run(action) {
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (e) {
    error.value = e.message
    if (e.data?.batch) emit('update', e.data.batch) // 저장 실패 시 최신 검사 결과로 갱신
  } finally {
    busy.value = false
  }
}

const recheck = () =>
  run(async () => {
    emit('update', await updateBatch(props.batch.id, changedRows()))
  })

const save = () =>
  run(async () => {
    const changes = changedRows()
    if (changes.length) {
      const updated = await updateBatch(props.batch.id, changes)
      emit('update', updated)
      if (updated.summary.error_rows) throw new Error('오류가 있는 행을 고치거나 제외한 뒤 저장해 주세요.')
    }
    emit('saved', await confirmBatch(props.batch.id))
  })

const cancel = () =>
  run(async () => {
    emit('cancelled', await cancelBatch(props.batch.id))
  })

function rowClass(row) {
  if (drafts[row.id].excluded) return 'table-secondary text-muted'
  if (row.duplicate) return 'table-warning'
  if (Object.keys(row.errors).length) return 'table-danger'
  return ''
}
</script>

<template>
  <div class="card">
    <div class="card-body">
      <div class="d-flex flex-wrap gap-3 align-items-center mb-2">
        <strong>{{ batch.file_name }}</strong>
        <span class="badge bg-primary">저장 예정 {{ batch.summary.to_save }}행</span>
        <span class="badge bg-danger">오류 {{ batch.summary.error_rows }}행</span>
        <span class="badge bg-warning text-dark">중복(건너뜀) {{ batch.summary.duplicate_rows }}행</span>
        <span class="badge bg-secondary">제외 {{ batch.summary.excluded_rows }}행</span>
        <span v-if="batch.summary.skipped_rows" class="text-muted small">
          ※ 일련번호가 없는 행 {{ batch.summary.skipped_rows }}개는 추출 단계에서 제외했습니다.
        </span>
      </div>

      <div class="table-responsive" style="max-height: 420px">
        <table class="table table-sm table-bordered align-middle small mb-2">
          <thead class="table-light sticky-top">
            <tr>
              <th>제외</th>
              <th>행</th>
              <th>상태</th>
              <th v-for="col in batch.columns" :key="col.key" class="text-nowrap">{{ col.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in batch.rows" :key="row.id" :class="rowClass(row)">
              <td class="text-center"><input v-model="drafts[row.id].excluded" type="checkbox" class="form-check-input" /></td>
              <td class="text-nowrap">{{ row.row_no }}</td>
              <td class="text-nowrap">
                <span v-if="drafts[row.id].excluded">제외</span>
                <span v-else-if="Object.keys(row.errors).length" class="text-danger">오류</span>
                <span v-else-if="row.duplicate">이미 저장됨</span>
                <span v-else class="text-success">정상</span>
              </td>
              <td v-for="col in batch.columns" :key="col.key" style="min-width: 7rem">
                <input
                  v-model="drafts[row.id].values[col.key]"
                  class="form-control form-control-sm"
                  :class="{ 'is-invalid': row.errors[col.key] }"
                  :disabled="drafts[row.id].excluded"
                  :aria-label="col.label"
                />
                <div v-if="row.errors[col.key]" class="invalid-feedback d-block">{{ row.errors[col.key] }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-primary btn-sm" :disabled="busy" @click="recheck">다시 검사</button>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="save">저장</button>
        <button class="btn btn-outline-secondary btn-sm ms-auto" :disabled="busy" @click="cancel">업로드 취소</button>
      </div>
      <p class="text-muted small mt-2 mb-0">값을 고친 뒤 [다시 검사]로 확인하세요. 이미 저장된 번호(노란색)는 저장할 때 자동으로 건너뜁니다.</p>
    </div>
  </div>
</template>
