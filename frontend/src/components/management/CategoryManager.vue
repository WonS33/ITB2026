<script setup>
// 그 외 지출 항목 관리: 추가·이름 변경·순서(↑↓)·고정/변동·비활성화·삭제(금액이 입력된 적 없는 항목만), [변경 저장]으로 한 번에
// (조원 저장소 settings/category-manager.tsx 를 옮김)
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getCategories, saveCategories } from '@/api/management'

const NAME_MAX = 30
const saved = ref(null) // 서버에서 받은 목록 { rows, version }
const rows = ref([])
const deletedIds = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const conflict = ref(false)
const pendingDelete = ref(null)
let newCount = 0

function fill(d) {
  saved.value = d
  rows.value = d.rows.map((r) => ({ ...r, key: `id-${r.id}`, isNew: false }))
  deletedIds.value = []
}

const snapshot = (list) => JSON.stringify(list.map((r) => [r.id, r.name, r.cost_type, r.is_active]))
const dirty = computed(() => !!saved.value && (deletedIds.value.length > 0 || snapshot(rows.value) !== snapshot(saved.value.rows)))

// 이름 검사: 빈 이름, 너무 김, 중복(앞뒤 공백·연속 공백·대소문자 무시)
const normalize = (name) => name.trim().replace(/\s+/g, ' ').toLowerCase()
const errors = computed(() => {
  const result = {}
  const seen = {}
  rows.value.forEach((r) => {
    const key = normalize(r.name)
    if (!key) result[r.key] = '항목 이름을 입력하세요.'
    else if (r.name.trim().length > NAME_MAX) result[r.key] = `${NAME_MAX}자까지 입력할 수 있습니다.`
    else if (seen[key]) result[r.key] = result[seen[key]] = '같은 이름의 항목이 이미 있습니다.'
    else seen[key] = r.key
  })
  return result
})
const hasErrors = computed(() => Object.keys(errors.value).length > 0)

function move(index, delta) {
  const list = [...rows.value]
  const [item] = list.splice(index, 1)
  list.splice(index + delta, 0, item)
  rows.value = list
}
function add() {
  newCount += 1
  const key = `new-${newCount}`
  rows.value = [...rows.value, { id: null, key, name: '', cost_type: '', is_active: true, used_months: 0, isNew: true }]
  requestAnimationFrame(() => document.getElementById(`cat-name-${key}`)?.focus())
}
function remove(row) {
  if (row.isNew) rows.value = rows.value.filter((r) => r.key !== row.key)
  else pendingDelete.value = row // 저장된 항목은 한 번 묻는다
}
function confirmDelete() {
  const row = pendingDelete.value
  rows.value = rows.value.filter((r) => r.key !== row.key)
  deletedIds.value = [...deletedIds.value, row.id]
  pendingDelete.value = null
}

async function load() {
  loading.value = true
  error.value = ''
  conflict.value = false
  try {
    fill(await getCategories())
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const res = await saveCategories({
      items: rows.value.map((r) => ({ id: r.id, name: r.name, cost_type: r.cost_type, is_active: r.is_active })),
      deleted_ids: deletedIds.value,
      version: saved.value.version,
    })
    fill(res)
    message.value = res.message
  } catch (e) {
    error.value = e.message
    conflict.value = e.status === 409
  } finally {
    saving.value = false
  }
}

onBeforeRouteLeave(() => !dirty.value || window.confirm('저장하지 않은 변경이 있습니다. 화면을 떠날까요?'))
const beforeUnload = (e) => { if (dirty.value) e.preventDefault() }
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); load() })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
defineExpose({ dirty })
</script>

<template>
  <div class="card">
    <div class="card-body">
      <h2 class="h6 mb-1">그 외 지출 항목</h2>
      <p class="small text-muted">
        순서는 월간 입력 화면의 표시 순서입니다. 비활성화한 항목은 월간 입력에서 숨겨지고, 과거 금액은 그대로 남습니다.
        금액이 입력된 적 없는 항목만 삭제할 수 있습니다. 이름을 바꾸면 과거 금액의 이름도 함께 바뀌니, 다른 용도로 쓰려면 새 항목을 추가하세요.
      </p>

      <div v-if="loading && !saved" class="text-muted">불러오는 중…</div>
      <div v-else-if="saved" class="table-responsive">
        <table class="table table-sm align-middle" style="min-width: 640px">
          <thead class="table-light">
            <tr><th>순서</th><th>항목명</th><th>고정/변동</th><th>상태</th><th class="text-end">사용</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="row.key" :class="{ 'table-secondary': !row.is_active }">
              <td class="text-nowrap">
                <button type="button" class="btn btn-sm btn-light px-2" :disabled="index === 0" :aria-label="`${row.name || '새 항목'} 위로`" @click="move(index, -1)">↑</button>
                <button type="button" class="btn btn-sm btn-light px-2 ms-1" :disabled="index === rows.length - 1" :aria-label="`${row.name || '새 항목'} 아래로`" @click="move(index, 1)">↓</button>
              </td>
              <td>
                <input :id="`cat-name-${row.key}`" v-model="row.name" class="form-control form-control-sm" :class="{ 'is-invalid': errors[row.key] }"
                       :maxlength="NAME_MAX + 10" aria-label="항목명" placeholder="예: 연구개발비" />
                <div v-if="errors[row.key]" class="invalid-feedback">{{ errors[row.key] }}</div>
              </td>
              <td>
                <select v-model="row.cost_type" class="form-select form-select-sm" aria-label="고정비/변동비">
                  <option value="">미분류</option>
                  <option value="fixed">고정비</option>
                  <option value="variable">변동비</option>
                </select>
              </td>
              <td>
                <button type="button" class="btn btn-sm text-nowrap" :class="row.is_active ? 'btn-outline-secondary' : 'btn-outline-primary'"
                        :aria-pressed="!row.is_active" @click="row.is_active = !row.is_active">
                  {{ row.is_active ? '● 사용 중 → 비활성화' : '○ 비활성 → 다시 사용' }}
                </button>
              </td>
              <td class="text-end small text-muted text-nowrap">{{ row.isNew ? '새 항목' : `${row.used_months}개월` }}</td>
              <td class="text-end">
                <button v-if="row.isNew || row.used_months === 0" type="button" class="btn btn-sm btn-outline-danger"
                        :aria-label="`${row.name || '새 항목'} 삭제`" @click="remove(row)">삭제</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="error" class="alert alert-danger py-2 d-flex align-items-center gap-2">
        <span>{{ error }}</span>
        <button v-if="conflict" type="button" class="btn btn-sm btn-outline-danger ms-auto" @click="load">최신 목록 다시 불러오기</button>
      </div>
      <div v-if="message" class="alert alert-success py-2">{{ message }}</div>

      <div class="d-flex flex-wrap align-items-center gap-2">
        <button type="button" class="btn btn-outline-secondary" @click="add">+ 항목 추가</button>
        <button type="button" class="btn btn-primary" :disabled="saving || !dirty || hasErrors" @click="save">
          {{ saving ? '저장 중…' : '변경 저장' }}
        </button>
        <small v-if="hasErrors" class="text-danger">항목 이름을 확인하세요 (빈 이름·중복)</small>
        <small v-else-if="dirty" class="text-warn">저장하지 않은 변경 있음</small>
      </div>
    </div>

    <template v-if="pendingDelete">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="cat-del-title">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="cat-del-title" class="modal-title h5">「{{ pendingDelete.name }}」 항목을 삭제할까요?</h2>
              <button type="button" class="btn-close" aria-label="닫기" @click="pendingDelete = null"></button>
            </div>
            <div class="modal-body">한 번도 금액이 입력되지 않은 항목입니다. [변경 저장]을 눌러야 실제로 삭제됩니다.</div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" @click="pendingDelete = null">돌아가기</button>
              <button type="button" class="btn btn-danger" @click="confirmDelete">삭제</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>
