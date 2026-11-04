<script setup>
// 월간 입력: 연·월을 골라 매출·매입·지출을 입력 → 임시저장 / 확정 (확정된 달만 대시보드에 반영)
// 규칙(조원 저장소 entry 화면을 옮김): 미래 달 입력 불가, 이번 달은 임시저장만, 지난 달은 확정까지.
// 버튼 숨김은 화면 편의일 뿐, 같은 규칙을 백엔드 API에서도 다시 확인한다.
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { exportMonthly, getMonthly, saveMonthly, unconfirmMonthly } from '@/api/management'
import MoneyInput from '@/components/MoneyInput.vue'
import FromLedgerDialog from '@/components/management/FromLedgerDialog.vue'

const SECTIONS = [
  { title: '매출', total: '매출 합계', fields: [
    { key: 'product_sales', label: '제품 매출', help: '자사가 생산한 제품을 판매한 금액' },
    { key: 'merchandise_sales', label: '상품 매출', help: '외부에서 사들여 그대로 판매한 상품 금액' },
    { key: 'service_sales', label: '용역 매출', help: '설치·수리·현장 서비스 등 용역으로 받은 금액' },
  ] },
  { title: '매입', total: '매입 합계', fields: [
    { key: 'merchandise_purchase', label: '상품 매입', help: '되팔기 위해 사들인 상품의 매입 금액' },
    { key: 'material_purchase', label: '원재료 매입', help: '제품 생산에 쓰는 원재료 매입 금액' },
  ] },
]
const STATUS = {
  new: { label: '입력 전', cls: 'badge-soft' },
  draft: { label: '임시저장', cls: 'badge-soft-brand' },
  confirmed: { label: '확정', cls: 'bg-success' },
}

// 기본 입력 월 = 지난달
const now = new Date()
const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
const sel = reactive({ year: lastMonth.getFullYear(), month: lastMonth.getMonth() + 1 })
const years = Array.from({ length: 5 }, (_, i) => now.getFullYear() - i)

const data = ref(null) // 서버에서 받은 그 달 정보
const form = reactive({ values: {}, others: {}, cash: null })
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const pending = ref(null) // 확인창에 띄울 작업 { intent, title, ... }
const conflict = ref(false) // 다른 사람이 먼저 저장함 (409)
const showLedger = ref(false)
const exporting = ref(false)

const ab = computed(() => data.value?.abilities ?? {})
const n = (v) => v ?? 0
const won = (v) => `${n(v).toLocaleString('ko-KR')}원`

function fill(d) {
  data.value = d
  Object.keys(form.values).forEach((k) => delete form.values[k])
  Object.assign(form.values, d.values)
  Object.keys(form.others).forEach((k) => delete form.others[k])
  d.other_expenses.forEach((e) => (form.others[e.category_id] = e.amount))
  form.cash = d.cash_balance
}

// 저장한 값과 지금 입력값이 다른지 (다른 달로 옮기거나 화면을 떠날 때 묻기 위해)
const dirty = computed(() => {
  const d = data.value
  if (!d) return false
  return Object.keys(d.values).some((k) => n(form.values[k]) !== d.values[k])
    || d.other_expenses.some((e) => n(form.others[e.category_id]) !== e.amount)
    || (form.cash ?? null) !== (d.cash_balance ?? null)
})

async function load() {
  loading.value = true
  error.value = ''
  conflict.value = false
  try {
    fill(await getMonthly(sel.year, sel.month))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function changeMonth(year, month) {
  if (dirty.value && !window.confirm('저장하지 않은 입력이 있습니다. 다른 달로 옮길까요?')) return
  sel.year = year
  sel.month = month
  message.value = ''
  load()
}
function step(diff) {
  const d = new Date(sel.year, sel.month - 1 + diff, 1)
  changeMonth(d.getFullYear(), d.getMonth() + 1)
}

const salesTotal = computed(() => SECTIONS[0].fields.reduce((s, f) => s + n(form.values[f.key]), 0))
const purchaseTotal = computed(() => SECTIONS[1].fields.reduce((s, f) => s + n(form.values[f.key]), 0))
const otherTotal = computed(() => (data.value?.other_expenses ?? []).reduce((s, e) => s + n(form.others[e.category_id]), 0))
const expenseTotal = computed(() => n(form.values.expense) + otherTotal.value)
const sectionTotal = (i) => (i === 0 ? salesTotal.value : purchaseTotal.value)

// 자릿수 실수 의심: 전월의 10배 이상 또는 1/10 이하 (전월 값이 없거나 0원이면 확인 안 함)
function anomaly(current, previous) {
  if (previous === undefined || previous === null || previous === 0) return false
  return n(current) >= previous * 10 || n(current) * 10 <= previous
}
const prevValue = (key) => data.value?.previous?.values[key]
const prevOther = (id) => data.value?.previous?.other_expenses[id]
const anomalyCount = computed(() => {
  if (!data.value?.previous) return 0
  return Object.keys(form.values).filter((k) => anomaly(form.values[k], prevValue(k))).length
    + data.value.other_expenses.filter((e) => anomaly(form.others[e.category_id], prevOther(e.category_id))).length
})

// 0원(빈칸)인 칸 이름 — 확정 전에 한 번 더 보여 준다
const zeroFields = computed(() => [
  ...SECTIONS.flatMap((s) => s.fields).filter((f) => !n(form.values[f.key])).map((f) => f.label),
  ...(n(form.values.expense) ? [] : ['경비 지출']),
])

function body(intent) {
  return {
    intent,
    values: Object.fromEntries(Object.keys(data.value.values).map((k) => [k, n(form.values[k])])),
    other_expenses: data.value.other_expenses.map((e) => ({ category_id: e.category_id, amount: n(form.others[e.category_id]) })),
    cash_balance: form.cash ?? null,
    expected_updated_at: data.value.updated_at, // 불러온 뒤 다른 사람이 저장했으면 서버가 409로 거부
  }
}

// 다른 사람이 먼저 저장했을 때: 지금 입력은 버리고 최신 값을 다시 불러온다
function reloadLatest() {
  if (window.confirm('지금 화면에 입력한 값은 사라지고 최신 저장 값으로 바뀝니다. 다시 불러올까요?')) load()
}

// [경영지원 관리에서 불러오기] → 입력란에만 채움 (저장은 사람이)
const FIELD_LABELS = Object.fromEntries([...SECTIONS.flatMap((s) => s.fields), { key: 'expense', label: '경비 지출' }].map((f) => [f.key, f.label]))
const currentOf = (t) => (t.type === 'field' ? form.values[t.field] : form.others[t.categoryId])
function applyLedger(lines) {
  for (const l of lines) {
    if (l.target.type === 'field') form.values[l.target.field] = l.value
    else form.others[l.target.categoryId] = l.value
  }
  showLedger.value = false
  message.value = `경영지원 관리 값 ${lines.length}칸을 입력란에 채웠습니다. 확인 후 [임시저장]이나 [확정]을 눌러야 저장됩니다.`
}

// 엑셀 내려받기 (저장된 값 기준)
const quarter = computed(() => Math.floor((sel.month - 1) / 3) + 1)
async function download(kind) {
  exporting.value = true
  error.value = ''
  try {
    await exportMonthly(sel.year, kind, sel.month)
  } catch (e) {
    error.value = e.message
  } finally {
    exporting.value = false
  }
}

function ask(intent) {
  const label = `${sel.year}년 ${sel.month}월`
  pending.value = {
    confirm: { intent, title: `${label} 확정`, button: '확정', text: '확정하면 대시보드 집계에 반영됩니다.' },
    update_confirmed: { intent, title: `${label} 확정 데이터 수정`, button: '수정 저장', text: '확정 상태를 유지한 채 값을 바꿉니다. 대시보드 숫자가 바로 바뀝니다.' },
    unconfirm: { intent, title: `${label} 확정 취소`, button: '확정 취소', danger: true, text: '임시저장 상태로 돌아가고 대시보드 집계에서 빠집니다. 입력한 값은 그대로 남습니다.' },
  }[intent]
}

async function run(intent) {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const res = intent === 'unconfirm'
      ? await unconfirmMonthly(sel.year, sel.month, data.value.updated_at)
      : await saveMonthly(sel.year, sel.month, body(intent))
    fill(res)
    message.value = res.message
  } catch (e) {
    error.value = e.message
    conflict.value = e.status === 409
  } finally {
    saving.value = false
    pending.value = null
  }
}

// 저장하지 않은 입력이 있으면 화면을 떠날 때 한 번 묻는다
onBeforeRouteLeave(() => !dirty.value || window.confirm('저장하지 않은 입력이 있습니다. 화면을 떠날까요?'))
const beforeUnload = (e) => { if (dirty.value) e.preventDefault() }
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); load() })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<template>
  <div>
    <!-- 연·월 고르기 + 상태 -->
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <button class="btn btn-outline-secondary btn-sm" aria-label="이전 달" @click="step(-1)">‹</button>
      <select class="form-select form-select-sm w-auto" aria-label="연도" :value="sel.year"
              @change="changeMonth(Number($event.target.value), sel.month)">
        <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
      </select>
      <select class="form-select form-select-sm w-auto" aria-label="월" :value="sel.month"
              @change="changeMonth(sel.year, Number($event.target.value))">
        <option v-for="m in 12" :key="m" :value="m">{{ m }}월</option>
      </select>
      <button class="btn btn-outline-secondary btn-sm" aria-label="다음 달" @click="step(1)">›</button>
      <span v-if="data" class="badge ms-1" :class="STATUS[data.status].cls">{{ STATUS[data.status].label }}</span>
      <small v-if="data?.updated_by" class="text-muted ms-1">
        마지막 저장: {{ data.updated_by }} · {{ new Date(data.updated_at).toLocaleString('ko-KR') }}
      </small>
      <!-- 엑셀 내려받기: 저장된 값 기준, 분기·연간 합계 시트는 확정된 달만 -->
      <div class="ms-auto d-flex align-items-center gap-2">
        <small class="text-muted">엑셀 다운로드</small>
        <div class="btn-group btn-group-sm" role="group" aria-label="엑셀 다운로드 기간">
          <button type="button" class="btn btn-outline-secondary" :disabled="exporting" @click="download('month')">{{ sel.month }}월</button>
          <button type="button" class="btn btn-outline-secondary" :disabled="exporting" @click="download('quarter')">{{ quarter }}분기</button>
          <button type="button" class="btn btn-outline-secondary" :disabled="exporting" @click="download('year')">{{ sel.year }}년</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger py-2 d-flex align-items-center gap-2">
      <span>{{ error }}</span>
      <button v-if="conflict" type="button" class="btn btn-sm btn-outline-danger ms-auto" @click="reloadLatest">최신 값 다시 불러오기</button>
    </div>
    <div v-if="message" class="alert alert-success py-2">{{ message }}</div>
    <div v-if="ab.notice" class="alert alert-light border py-2">{{ ab.notice }}</div>
    <div v-if="anomalyCount" class="alert alert-warning py-2">
      전월보다 10배 이상 크거나 1/10 이하인 칸이 {{ anomalyCount }}개 있습니다. 자릿수를 확인해 주세요.
    </div>

    <div v-if="loading && !data" class="text-muted">불러오는 중…</div>
    <form v-else-if="data" @submit.prevent>
      <fieldset :disabled="ab.read_only || saving">
        <div class="row g-3">
          <!-- 매출·매입 -->
          <div v-for="(s, i) in SECTIONS" :key="s.title" class="col-lg-6">
            <div class="card h-100">
              <div class="card-body">
                <h2 class="h6 mb-3">{{ s.title }}</h2>
                <div v-for="f in s.fields" :key="f.key" class="mb-3">
                  <label :for="f.key" class="form-label mb-1">{{ f.label }}</label>
                  <MoneyInput :id="f.key" v-model="form.values[f.key]" :invalid="anomaly(form.values[f.key], prevValue(f.key))" />
                  <div class="form-text">
                    {{ f.help }}<template v-if="prevValue(f.key) !== undefined"> · 전월 {{ won(prevValue(f.key)) }}</template>
                  </div>
                </div>
                <div class="d-flex justify-content-between border-top pt-2 fw-semibold">
                  <span>{{ s.total }}</span><span>{{ won(sectionTotal(i)) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 지출: 경비 + 그 외 지출 항목 -->
          <div class="col-lg-6">
            <div class="card h-100">
              <div class="card-body">
                <h2 class="h6 mb-3">지출</h2>
                <div class="mb-3">
                  <label for="expense" class="form-label mb-1">경비 지출</label>
                  <MoneyInput id="expense" v-model="form.values.expense" :invalid="anomaly(form.values.expense, prevValue('expense'))" />
                  <div class="form-text">
                    임차료·공과금·직원 경비 등 일반 경비<template v-if="prevValue('expense') !== undefined"> · 전월 {{ won(prevValue('expense')) }}</template>
                  </div>
                </div>
                <div class="small text-muted fw-semibold mb-2">그 외 지출</div>
                <div v-for="e in data.other_expenses" :key="e.category_id" class="row g-2 align-items-center mb-2">
                  <label :for="`other-${e.category_id}`" class="col-5 col-form-label py-0">
                    {{ e.name }} <span v-if="!e.is_active" class="badge badge-soft">사용 안 함</span>
                  </label>
                  <div class="col-7">
                    <MoneyInput :id="`other-${e.category_id}`" v-model="form.others[e.category_id]"
                                :invalid="anomaly(form.others[e.category_id], prevOther(e.category_id))" />
                  </div>
                </div>
                <p v-if="!data.other_expenses.length" class="small text-muted">등록된 그 외 지출 항목이 없습니다.</p>
                <div class="d-flex justify-content-between border-top pt-2 fw-semibold">
                  <span>지출 합계 <small class="text-muted fw-normal">(경비 + 그 외 지출)</small></span><span>{{ won(expenseTotal) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 월말 통장 잔액 (선택) -->
          <div class="col-lg-6">
            <div class="card h-100">
              <div class="card-body">
                <h2 class="h6 mb-3">월말 통장 잔액 <span class="badge badge-soft">선택</span></h2>
                <MoneyInput id="cash" v-model="form.cash" />
                <div class="form-text">그달 말일 기준 통장 잔액. 비워 두어도 되고, 매출·지출 합계에는 들어가지 않습니다.</div>
              </div>
            </div>
          </div>
        </div>
      </fieldset>

      <!-- 버튼: 상태·권한에 따라 다르게 보인다 -->
      <div class="d-flex flex-wrap gap-2 justify-content-end mt-3">
        <button v-if="!ab.read_only" type="button" class="btn btn-outline-secondary me-auto" :disabled="saving" @click="showLedger = true">
          경영지원 관리에서 불러오기
        </button>
        <button v-if="ab.can_unconfirm" type="button" class="btn btn-outline-danger" :disabled="saving" @click="ask('unconfirm')">확정 취소</button>
        <button v-if="ab.can_save_draft" type="button" class="btn btn-outline-secondary" :disabled="saving" @click="run('draft')">
          {{ saving ? '저장 중…' : '임시저장' }}
        </button>
        <button v-if="ab.can_confirm" type="button" class="btn btn-primary" :disabled="saving" @click="ask('confirm')">확정</button>
        <button v-if="ab.can_edit_confirmed" type="button" class="btn btn-primary" :disabled="saving || !dirty" @click="ask('update_confirmed')">수정 저장</button>
      </div>
    </form>

    <FromLedgerDialog v-if="showLedger" :year="sel.year" :month="sel.month" :categories="data.other_expenses"
                      :current="currentOf" :field-labels="FIELD_LABELS" @apply="applyLedger" @close="showLedger = false" />

    <!-- 확인창 -->
    <template v-if="pending">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="entry-confirm-title">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="entry-confirm-title" class="modal-title h5">{{ pending.title }}</h2>
              <button type="button" class="btn-close" aria-label="닫기" :disabled="saving" @click="pending = null"></button>
            </div>
            <div class="modal-body">
              <p>{{ pending.text }}</p>
              <table v-if="pending.intent !== 'unconfirm'" class="table table-sm mb-2">
                <tbody>
                  <tr><th class="fw-normal">매출 합계</th><td class="text-end">{{ won(salesTotal) }}</td></tr>
                  <tr><th class="fw-normal">매입 합계</th><td class="text-end">{{ won(purchaseTotal) }}</td></tr>
                  <tr><th class="fw-normal">지출 합계</th><td class="text-end">{{ won(expenseTotal) }}</td></tr>
                </tbody>
              </table>
              <p v-if="pending.intent !== 'unconfirm' && zeroFields.length" class="text-warning-emphasis small mb-1">
                0원인 칸: {{ zeroFields.join(', ') }}
              </p>
              <p v-if="pending.intent !== 'unconfirm' && anomalyCount" class="text-warning-emphasis small mb-0">
                전월과 자릿수가 크게 다른 칸이 {{ anomalyCount }}개 있습니다.
              </p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" :disabled="saving" @click="pending = null">돌아가기</button>
              <button type="button" class="btn" :class="pending.danger ? 'btn-danger' : 'btn-primary'" :disabled="saving" @click="run(pending.intent)">
                {{ saving ? '저장 중…' : pending.button }}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>
