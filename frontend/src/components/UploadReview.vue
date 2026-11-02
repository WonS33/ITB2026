<script setup>
// 업로드 확인·수정 표 (specs/03-common.md 4절 ③④⑤)
// - 오류 칸은 빨간색 + 메시지, 이미 저장된 번호는 "중복(건너뜀)", 행마다 "제외" 선택
// - 출장보고서처럼 기준이 고유 번호가 아닌 종류는 중복 행에 "중복 아님 — 저장" 체크칸을 보여준다
// - 제조내역처럼 최신 업로드 기준(update_existing)인 종류는 이미 있는 번호를 "갱신"으로 보여 주고 바뀐 칸(이전 → 새 값)을 적는다
// - [다시 검사]: 고친 값을 서버에 보내 다시 검사 / [저장]: 고친 값 반영 후 최종 저장
import { reactive, ref, watch } from 'vue'
import { cancelBatch, confirmBatch, updateBatch } from '@/api/uploads'

const props = defineProps({ batch: { type: Object, required: true } })
const emit = defineEmits(['update', 'saved', 'cancelled'])

const drafts = reactive({}) // 행 id → { values, excluded, allow_duplicate } (화면에서 고친 값)
const busy = ref(false)
const error = ref('')

function resetDrafts(batch) {
  for (const key of Object.keys(drafts)) delete drafts[key]
  for (const row of batch.rows) {
    drafts[row.id] = { values: { ...row.values }, excluded: row.excluded, allow_duplicate: !!row.allow_duplicate }
  }
}
watch(() => props.batch, resetDrafts, { immediate: true })

// 다른 칸 값에 따라 바뀌는 선택 목록 (예: 시·도 → 시·군). 목록이 없으면 빈 배열
const dependentChoices = (col, row) => col.choices_map[drafts[row.id].values[col.choices_by]] || []

// 시·도를 바꿔서 기존 시·군이 새 목록에 없으면 비운다
watch(
  drafts,
  () => {
    for (const col of props.batch.columns.filter((c) => c.choices_by)) {
      for (const row of props.batch.rows) {
        const values = drafts[row.id]?.values
        if (values?.[col.key] && !dependentChoices(col, row).includes(values[col.key])) values[col.key] = ''
      }
    }
  },
  { deep: true },
)

function changedRows() {
  return props.batch.rows
    .filter((row) => {
      const d = drafts[row.id]
      return (
        d.excluded !== row.excluded ||
        d.allow_duplicate !== !!row.allow_duplicate ||
        Object.keys(d.values).some((k) => d.values[k] !== row.values[k])
      )
    })
    .map((row) => ({ id: row.id, ...drafts[row.id] }))
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

// 바뀐 칸 이름 (열 제목)
const labelOf = (key) => props.batch.columns.find((c) => c.key === key)?.label ?? key

function rowClass(row) {
  if (drafts[row.id].excluded) return 'table-secondary text-muted'
  if (row.superseded) return 'table-secondary text-muted'
  if (row.duplicate) return 'table-warning'
  if (row.update && !Object.keys(row.errors).length) return 'table-info'
  if (Object.keys(row.errors).length) return 'table-danger'
  return ''
}
</script>

<template>
  <div class="card">
    <div class="card-body">
      <div class="d-flex flex-wrap gap-3 align-items-center mb-2">
        <strong>{{ batch.file_name }}</strong>
        <span class="badge bg-primary">
          저장 예정 {{ batch.summary.to_save }}행<template v-if="batch.update_existing"> (새로 {{ batch.summary.to_save - batch.summary.update_rows }} · 갱신 {{ batch.summary.update_rows }})</template>
        </span>
        <span class="badge bg-danger">오류 {{ batch.summary.error_rows }}행</span>
        <span class="badge bg-warning text-dark">
          {{ batch.update_existing ? '건너뜀' : '중복(건너뜀)' }} {{ batch.summary.duplicate_rows }}행<template v-if="batch.summary.superseded_rows"> (파일 아래 행으로 대체 {{ batch.summary.superseded_rows }})</template>
        </span>
        <span class="badge bg-secondary">제외 {{ batch.summary.excluded_rows }}행</span>
        <span v-if="batch.summary.skipped_rows" class="text-muted small">
          ※ 일련번호가 없는 행 {{ batch.summary.skipped_rows }}개는 추출 단계에서 제외했습니다.
        </span>
      </div>

      <div class="table-responsive" style="max-height: 420px">
        <table class="table table-sm table-bordered align-middle small mb-2">
          <thead class="table-light sticky-top">
            <tr>
              <th class="text-nowrap">제외</th>
              <th class="text-nowrap">행</th>
              <th class="text-nowrap">상태</th>
              <th v-for="col in batch.columns" :key="col.key" class="text-nowrap">{{ col.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in batch.rows" :key="row.id" :class="rowClass(row)">
              <td class="text-center"><input v-model="drafts[row.id].excluded" type="checkbox" class="form-check-input" /></td>
              <td class="text-nowrap">{{ row.row_no }}</td>
              <td class="text-nowrap">
                <span v-if="drafts[row.id].excluded">제외</span>
                <span v-else-if="row.superseded" title="같은 번호가 파일 아래쪽에 다시 나와 마지막 행을 씁니다">아래 행으로 대체</span>
                <span v-else-if="Object.keys(row.errors).length" class="text-danger">오류</span>
                <span v-else-if="row.duplicate">{{ batch.update_existing ? '변경 없음(건너뜀)' : '이미 저장됨' }}</span>
                <template v-else-if="row.update">
                  <span class="fw-semibold">갱신</span>
                  <!-- 바뀐 칸: 이전 값 → 새 값 (빈 값은 "빈칸") -->
                  <ul class="list-unstyled mb-0 mt-1 changes">
                    <li v-for="(c, key) in row.changes" :key="key">{{ labelOf(key) }}: {{ c.old || '빈칸' }} → <strong>{{ c.new || '빈칸' }}</strong></li>
                  </ul>
                </template>
                <span v-else class="text-success">{{ batch.update_existing ? '새로 저장' : '정상' }}</span>
                <!-- 같은 날 같은 곳에 실제로 두 번 간 경우: 사람이 확인하고 저장 -->
                <label
                  v-if="batch.allow_duplicate_override && !drafts[row.id].excluded && (row.matches_existing || row.in_file_duplicate)"
                  class="form-check small mt-1 mb-0 text-nowrap"
                >
                  <input v-model="drafts[row.id].allow_duplicate" type="checkbox" class="form-check-input" />
                  중복 아님 — 저장
                </label>
              </td>
              <td v-for="col in batch.columns" :key="col.key" :style="{ minWidth: col.multiline ? '16rem' : col.choices || col.choices_by || col.suggestions ? '10rem' : '7rem' }">
                <!-- 열 종류: 선택 목록(choices) / 다른 칸에 따라 바뀌는 선택 목록(choices_by) / 여러 줄(multiline) / 한 줄 입력 -->
                <select
                  v-if="col.choices_by"
                  v-model="drafts[row.id].values[col.key]"
                  class="form-select form-select-sm"
                  :class="{ 'is-invalid': row.errors[col.key] }"
                  :disabled="drafts[row.id].excluded || !dependentChoices(col, row).length"
                  :aria-label="col.label"
                >
                  <option value="">{{ dependentChoices(col, row).length ? '선택' : '없음' }}</option>
                  <option v-for="c in dependentChoices(col, row)" :key="c" :value="c">{{ c }}</option>
                </select>
                <select
                  v-else-if="col.choices"
                  v-model="drafts[row.id].values[col.key]"
                  class="form-select form-select-sm"
                  :class="{ 'is-invalid': row.errors[col.key] }"
                  :disabled="drafts[row.id].excluded"
                  :aria-label="col.label"
                >
                  <option value="">선택</option>
                  <option v-for="c in col.choices" :key="c" :value="c">{{ c }}</option>
                </select>
                <textarea
                  v-else-if="col.multiline"
                  v-model="drafts[row.id].values[col.key]"
                  rows="3"
                  class="form-control form-control-sm"
                  :class="{ 'is-invalid': row.errors[col.key] }"
                  :disabled="drafts[row.id].excluded"
                  :aria-label="col.label"
                ></textarea>
                <!-- suggestions가 있으면 직접 입력하면서 추천 목록에서 고를 수 있다 (예: 부품명) -->
                <input
                  v-else
                  v-model="drafts[row.id].values[col.key]"
                  class="form-control form-control-sm"
                  :class="{ 'is-invalid': row.errors[col.key] }"
                  :disabled="drafts[row.id].excluded"
                  :aria-label="col.label"
                  :list="col.suggestions ? `suggest-${col.key}` : undefined"
                />
                <div v-if="row.errors[col.key]" class="invalid-feedback d-block">{{ row.errors[col.key] }}</div>
              </td>
            </tr>
          </tbody>
        </table>
        <datalist v-for="col in batch.columns.filter((c) => c.suggestions)" :id="`suggest-${col.key}`" :key="col.key">
          <option v-for="name in col.suggestions" :key="name" :value="name" />
        </datalist>
      </div>

      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-primary btn-sm" :disabled="busy" @click="recheck">다시 검사</button>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="save">저장</button>
        <button class="btn btn-outline-secondary btn-sm ms-auto" :disabled="busy" @click="cancel">업로드 취소</button>
      </div>
      <p class="text-muted small mt-2 mb-0">
        값을 고친 뒤 [다시 검사]로 확인하세요.
        <template v-if="batch.update_existing">
          이미 저장된 번호는 <strong>새로 올린 값으로 갱신</strong>합니다(파란색, 바뀐 칸 표시). 바뀐 값이 없으면 건너뜁니다(노란색).
          같은 번호가 파일에 여러 번 있으면 마지막 행만 씁니다.
        </template>
        <template v-else>이미 저장된 번호(노란색)는 저장할 때 자동으로 건너뜁니다.</template>
        <template v-if="batch.allow_duplicate_override">같은 날 같은 곳에 실제로 두 번 출장 갔다면 "중복 아님 — 저장"을 체크하세요.</template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.changes {
  font-size: 0.75rem;
  white-space: nowrap;
}
</style>
