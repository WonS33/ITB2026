<script setup>
// 경영지원 관리 장부 (조원 저장소 ledger 화면을 옮김) — 고객사 「경영지원_관리」 엑셀의 블록 4개
// 기준년월·구분 탭·숨긴 항목 보기, 표 안에서 바로 행 추가·수정, 숨김·복구, 지난달 내용 불러오기
// 외상매출금의 장기 미수금 + 당월 수금예정이 대시보드 미수금이 되고, 나머지 세 구분은 월간 입력 [불러오기]의 원본이다
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createLedgerEntry, getLedger, ledgerAction, updateLedgerEntry } from '@/api/management'
import MoneyInput from '@/components/MoneyInput.vue'
import LedgerCopyDialog from '@/components/management/LedgerCopyDialog.vue'
import RowHistoryDialog from '@/components/management/RowHistoryDialog.vue'
import { won } from '@/money'

const KINDS = [
  { key: 'ar', param: 'ar' },
  { key: 'ap', param: 'ap' },
  { key: 'accrued_staff', param: 'staff' },
  { key: 'accrued_vendor', param: 'vendor' },
]
// 그룹 합계 줄 이름 (엑셀 '총액' 옆 메모 문구)
const AR_GROUP_TOTAL = { long_overdue: '장기 미수금 업체', collected: '당월 수금된 업체', scheduled: '당월 수금예정인 업체' }
const KIND_TOTAL = { ap: '당월 매입 지출', accrued_staff: '당월 경비 지출' }

const route = useRoute()
const router = useRouter()
const now = new Date()
const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const monthText = ref(/^\d{4}-\d{2}$/.test(route.query.month ?? '') && route.query.month <= thisMonth ? route.query.month : thisMonth)
const kind = ref(KINDS.find((k) => k.param === route.query.tab)?.key ?? 'ar')
const showHidden = ref(route.query.hidden === '1')

const data = ref(null)
const error = ref('')
const message = ref('')
const editing = ref(null) // 고치는 행 id 또는 'new'
const draft = reactive({})
const saving = ref(false)
const confirmAsk = ref(null)
const historyOf = ref(null)
const copying = ref(false)

const ym = computed(() => ({ year: Number(monthText.value.slice(0, 4)), month: Number(monthText.value.slice(5, 7)) }))
const labels = computed(() => {
  const map = (list) => Object.fromEntries((list ?? []).map((c) => [c.value, c.label]))
  return { kinds: map(data.value?.kinds), ar: map(data.value?.ar_statuses), purchase: map(data.value?.purchase_types), expense: map(data.value?.expense_types) }
})
const settleWord = computed(() => (kind.value === 'ar' ? '수금' : '지급'))

async function load() {
  error.value = ''
  editing.value = null
  try {
    data.value = await getLedger(ym.value.year, ym.value.month)
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)

function sync() {
  const q = {}
  if (monthText.value !== thisMonth) q.month = monthText.value
  if (kind.value !== 'ar') q.tab = KINDS.find((k) => k.key === kind.value).param
  if (showHidden.value) q.hidden = '1'
  router.replace({ query: q })
}
function changeMonth(value) {
  if (!value || value > thisMonth) return
  if (editing.value && !window.confirm('저장하지 않은 입력이 있습니다. 다른 달로 옮길까요?')) return
  monthText.value = value
  message.value = ''
  sync()
  load()
}

// ---------- 표 ----------
const visible = computed(() => (data.value?.rows ?? []).filter((r) => r.hidden === showHidden.value))
const rowsOf = (k) => visible.value.filter((r) => r.kind === k)
const counts = computed(() => Object.fromEntries(KINDS.map((k) => [k.key, rowsOf(k.key).length])))
const sum = (rows) => rows.reduce((s, r) => s + r.amount, 0)
const current = computed(() => rowsOf(kind.value))
// 외상매출금: 장기 미수금 → 당월 수금 → 당월 수금예정 (행이 없는 그룹도 총액 0으로)
const arGroups = computed(() =>
  ['long_overdue', 'collected', 'scheduled'].map((status) => {
    const rows = current.value.filter((r) => r.ar_status === status)
    return { status, rows, total: sum(rows) }
  }),
)
// 미지급비용-업체: 엑셀 총액(자동이체 제외) + 자동이체 합계 + 전체 합계 (금액이 빠져 보이지 않게 셋 다)
const vendorTotals = computed(() => {
  const all = sum(current.value)
  const auto = sum(current.value.filter((r) => r.auto_transfer))
  return { excluding: all - auto, auto, all }
})
const columns = computed(() => {
  const cols = []
  if (kind.value === 'ar') cols.push('코드')
  cols.push('거래처명', '잔액', '적요', `${settleWord.value} 예정일`, `${settleWord.value} 완료일`)
  if (kind.value === 'ar') cols.push('상태')
  if (kind.value === 'ap') cols.push('매입유형')
  if (kind.value === 'accrued_vendor') cols.push('비용유형', '자동이체')
  return cols
})

// ---------- 입력 ----------
function startEdit(row) {
  if (editing.value && !window.confirm('고치던 행이 있습니다. 버리고 다른 행을 고칠까요?')) return
  Object.keys(draft).forEach((k) => delete draft[k])
  Object.assign(draft, row
    ? { ...row, due_on: row.due_on ?? '', settled_on: row.settled_on ?? '' }
    : {
        kind: kind.value,
        // 새 행 기본값: 외상매출금 = 당월 수금예정, 업체 = 기타. 외상매입금 매입유형은 직접 고르게 비워 둔다
        ar_status: kind.value === 'ar' ? 'scheduled' : '',
        purchase_type: '',
        expense_type: kind.value === 'accrued_vendor' ? 'other' : '',
        auto_transfer: false,
        partner_code: '',
        partner_name: '',
        amount: null,
        note: '',
        due_on: '',
        settled_on: '',
      })
  editing.value = row ? row.id : 'new'
  message.value = ''
  error.value = ''
}
function onArStatus() {
  if (draft.ar_status !== 'collected') draft.settled_on = '' // 당월 수금이 아니면 완료일을 지운다
}
const settledDisabled = computed(() => draft.kind === 'ar' && draft.ar_status !== 'collected')

async function save(row) {
  saving.value = true
  error.value = ''
  const fields = {
    kind: draft.kind,
    ar_status: draft.ar_status,
    purchase_type: draft.purchase_type,
    expense_type: draft.expense_type,
    auto_transfer: draft.auto_transfer,
    partner_code: draft.partner_code,
    partner_name: draft.partner_name,
    amount: draft.amount ?? 0,
    note: draft.note,
    due_on: draft.due_on || null,
    settled_on: draft.settled_on || null,
  }
  try {
    const res = row
      ? await updateLedgerEntry(row.id, fields, row.updated_at)
      : await createLedgerEntry(ym.value.year, ym.value.month, fields)
    await load() // 다시 불러온 뒤에 안내 (표가 바뀌기 전에 안내가 먼저 뜨지 않게)
    message.value = res.message
  } catch (e) {
    error.value = e.status === 409 ? `${e.message} [다시 불러오기]를 눌러 주세요.` : e.message
  } finally {
    saving.value = false
  }
}

const ask = (row, action) =>
  (confirmAsk.value = action === 'hide'
    ? { row, action, title: `${row.partner_name} 행을 숨길까요?`, text: `${won(row.amount)}. 숨긴 행은 표·총액·대시보드에서 빠집니다. 삭제되지는 않으며 [숨긴 항목 보기]에서 복구할 수 있습니다.`, button: '숨기기', danger: true }
    : { row, action, title: `${row.partner_name} 행을 복구할까요?`, text: '표와 총액에 다시 포함됩니다.', button: '복구', danger: false })

async function runAction() {
  const { row, action } = confirmAsk.value
  confirmAsk.value = null
  try {
    const res = await ledgerAction(row.id, action, row.updated_at)
    await load()
    message.value = res.message
  } catch (e) {
    error.value = e.message
  }
}

async function copyDone(text) {
  copying.value = false
  await load()
  message.value = text
}
</script>

<template>
  <div>
    <p class="small mb-1">「경영지원 관리」 엑셀의 외상매출금 · 외상매입금 · 미지급비용-직원 · 미지급비용-업체</p>
    <p class="small text-muted">
      기준년월별 거래처 잔액이며, 잔액은 ERP 잔액 그대로(부가세 포함) 입력하세요. 외상매출금의 장기 미수금 + 당월 수금예정이 대시보드 미수금이 됩니다.
      저장한 내용은 [변경 이력]에 남습니다.
    </p>

    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <label class="small text-muted" for="ledger-month">기준년월</label>
      <input id="ledger-month" type="month" class="form-control form-control-sm w-auto" :max="thisMonth" :value="monthText" @change="changeMonth($event.target.value)" />
      <button type="button" class="btn btn-sm btn-outline-secondary" @click="copying = true">지난달 내용 불러오기</button>
      <RouterLink :to="{ path: '/management/ledger/import', query: { month: monthText } }" class="btn btn-sm btn-outline-secondary">엑셀 가져오기</RouterLink>
      <label class="form-check-label small d-flex align-items-center gap-1 ms-auto">
        <input v-model="showHidden" type="checkbox" class="form-check-input mt-0" @change="editing = null; sync()" /> 숨긴 항목 보기
      </label>
    </div>

    <div v-if="error" class="alert alert-danger py-2 d-flex align-items-center gap-2">
      <span>{{ error }}</span><button type="button" class="btn btn-sm btn-outline-danger ms-auto" @click="load">다시 불러오기</button>
    </div>
    <div v-if="message" class="alert alert-success py-2">{{ message }}</div>
    <div v-if="!data" class="text-muted">불러오는 중…</div>

    <div v-else class="card"><div class="card-body">
      <ul class="nav nav-tabs mb-3" role="tablist">
        <li v-for="k in KINDS" :key="k.key" class="nav-item" role="presentation">
          <button type="button" class="nav-link" :class="{ active: kind === k.key }" role="tab" :aria-selected="kind === k.key"
                  @click="editing = null; kind = k.key; sync()">
            {{ labels.kinds[k.key] }} <span class="badge badge-soft">{{ counts[k.key] }}</span>
          </button>
        </li>
      </ul>
      <p v-if="showHidden" class="small text-muted bg-light rounded px-2 py-1">숨긴 항목만 보고 있습니다. 숨긴 행은 총액·대시보드에 포함되지 않습니다.</p>

      <div class="table-responsive">
        <table class="table table-sm align-middle mb-2" style="min-width: 900px">
          <thead class="table-light"><tr class="text-nowrap"><th v-for="c in columns" :key="c" :class="{ 'text-end': c === '잔액' }">{{ c }}</th><th></th></tr></thead>
          <tbody>
            <!-- 외상매출금: 상태 그룹별 -->
            <template v-if="kind === 'ar'">
              <template v-for="g in arGroups" :key="g.status">
                <tr class="table-light"><td :colspan="columns.length + 1" class="small fw-semibold" :class="{ 'text-danger': g.status === 'long_overdue' }">{{ labels.ar[g.status] }}</td></tr>
                <tr v-if="!g.rows.length"><td :colspan="columns.length + 1" class="small text-muted">해당 거래처가 없습니다.</td></tr>
                <template v-for="r in g.rows" :key="r.id">
                  <tr :class="{ 'text-danger': r.ar_status === 'long_overdue', editing: editing === r.id }">
                    <td class="text-nowrap">{{ r.partner_code || '-' }}</td>
                    <td>{{ r.partner_name }}</td>
                    <td class="text-end">{{ r.amount.toLocaleString() }}</td>
                    <td class="small">{{ r.note }}</td>
                    <td class="text-nowrap">{{ r.due_on ?? '-' }}</td>
                    <td class="text-nowrap">{{ r.settled_on ?? '-' }}</td>
                    <td class="text-nowrap">{{ labels.ar[r.ar_status] }}</td>
                    <td class="text-end text-nowrap">
                      <button type="button" class="btn btn-sm btn-light" @click="historyOf = r">이력</button>
                      <template v-if="r.hidden"><button type="button" class="btn btn-sm btn-outline-primary ms-1" @click="ask(r, 'restore')">복구</button></template>
                      <template v-else>
                        <button type="button" class="btn btn-sm btn-outline-secondary ms-1" @click="startEdit(r)">수정</button>
                        <button type="button" class="btn btn-sm btn-outline-danger ms-1" @click="ask(r, 'hide')">숨기기</button>
                      </template>
                    </td>
                  </tr>
                </template>
                <tr class="fw-semibold"><td :colspan="2" class="text-end small">총액 · {{ AR_GROUP_TOTAL[g.status] }}</td><td class="text-end">{{ g.total.toLocaleString() }}</td><td :colspan="columns.length - 2"></td></tr>
              </template>
            </template>
            <!-- 그 밖의 구분 -->
            <template v-else>
              <tr v-if="!current.length"><td :colspan="columns.length + 1" class="text-center text-muted py-3">{{ showHidden ? '숨긴 항목이 없습니다.' : '입력된 행이 없습니다.' }}</td></tr>
              <template v-for="r in current" :key="r.id">
                <tr :class="{ 'auto-transfer': r.auto_transfer, editing: editing === r.id }">
                  <td>{{ r.partner_name }}</td>
                  <td class="text-end">{{ r.amount.toLocaleString() }}</td>
                  <td class="small">{{ r.note }}</td>
                  <td class="text-nowrap">{{ r.due_on ?? '-' }}</td>
                  <td class="text-nowrap">{{ r.settled_on ?? '-' }}</td>
                  <td v-if="kind === 'ap'" class="text-nowrap">{{ labels.purchase[r.purchase_type] ?? '(미지정)' }}</td>
                  <td v-if="kind === 'accrued_vendor'" class="text-nowrap">{{ labels.expense[r.expense_type] }}</td>
                  <td v-if="kind === 'accrued_vendor'" class="text-nowrap">{{ r.auto_transfer ? '자동이체' : '-' }}</td>
                  <td class="text-end text-nowrap">
                    <button type="button" class="btn btn-sm btn-light" @click="historyOf = r">이력</button>
                    <template v-if="r.hidden"><button type="button" class="btn btn-sm btn-outline-primary ms-1" @click="ask(r, 'restore')">복구</button></template>
                    <template v-else>
                      <button type="button" class="btn btn-sm btn-outline-secondary ms-1" @click="startEdit(r)">수정</button>
                      <button type="button" class="btn btn-sm btn-outline-danger ms-1" @click="ask(r, 'hide')">숨기기</button>
                    </template>
                  </td>
                </tr>
              </template>
              <template v-if="kind === 'accrued_vendor'">
                <tr class="fw-semibold"><td class="text-end small">총액(자동이체 제외) · 당월 그 외 지출</td><td class="text-end">{{ vendorTotals.excluding.toLocaleString() }}</td><td :colspan="columns.length - 1"></td></tr>
                <tr class="small"><td class="text-end">자동이체 합계</td><td class="text-end">{{ vendorTotals.auto.toLocaleString() }}</td><td :colspan="columns.length - 1"></td></tr>
                <tr class="small"><td class="text-end">전체 합계</td><td class="text-end">{{ vendorTotals.all.toLocaleString() }}</td><td :colspan="columns.length - 1"></td></tr>
              </template>
              <tr v-else class="fw-semibold"><td class="text-end small">총액 · {{ KIND_TOTAL[kind] }}</td><td class="text-end">{{ sum(current).toLocaleString() }}</td><td :colspan="columns.length - 1"></td></tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- 입력 줄 (추가·수정 공용) -->
      <div v-if="editing" class="border rounded-3 p-3 bg-light">
        <div class="small fw-semibold mb-2">{{ editing === 'new' ? `${labels.kinds[kind]} 행 추가` : '행 수정' }}</div>
        <div class="row g-2 align-items-end">
          <div v-if="draft.kind === 'ar'" class="col-md-2">
            <label class="form-label small mb-1" for="lg-code">코드</label>
            <input id="lg-code" v-model="draft.partner_code" class="form-control form-control-sm" inputmode="numeric" maxlength="10" placeholder="숫자 10자리" />
          </div>
          <div class="col-md-3">
            <label class="form-label small mb-1" for="lg-name">거래처명 <span class="text-danger">*</span></label>
            <input id="lg-name" v-model="draft.partner_name" class="form-control form-control-sm" maxlength="60" />
          </div>
          <div class="col-md-2">
            <label class="form-label small mb-1" for="lg-amount">잔액 <span class="text-danger">*</span></label>
            <MoneyInput id="lg-amount" v-model="draft.amount" />
          </div>
          <div v-if="draft.kind === 'ar'" class="col-md-2">
            <label class="form-label small mb-1" for="lg-status">상태</label>
            <select id="lg-status" v-model="draft.ar_status" class="form-select form-select-sm" @change="onArStatus">
              <option v-for="c in data.ar_statuses" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </div>
          <div v-if="draft.kind === 'ap'" class="col-md-2">
            <label class="form-label small mb-1" for="lg-purchase">매입유형 <span class="text-danger">*</span></label>
            <select id="lg-purchase" v-model="draft.purchase_type" class="form-select form-select-sm">
              <option value="">선택</option>
              <option v-for="c in data.purchase_types" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </div>
          <template v-if="draft.kind === 'accrued_vendor'">
            <div class="col-md-2">
              <label class="form-label small mb-1" for="lg-expense">비용유형</label>
              <select id="lg-expense" v-model="draft.expense_type" class="form-select form-select-sm">
                <option v-for="c in data.expense_types" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </div>
            <div class="col-md-1">
              <label class="form-check small mt-4"><input v-model="draft.auto_transfer" type="checkbox" class="form-check-input" /> 자동이체</label>
            </div>
          </template>
          <div class="col-md-3">
            <label class="form-label small mb-1" for="lg-note">적요</label>
            <input id="lg-note" v-model="draft.note" class="form-control form-control-sm" maxlength="200" />
          </div>
          <div class="col-md-2">
            <label class="form-label small mb-1" for="lg-due">{{ settleWord }} 예정일</label>
            <input id="lg-due" v-model="draft.due_on" type="date" class="form-control form-control-sm" />
          </div>
          <div class="col-md-2">
            <label class="form-label small mb-1" for="lg-settled">{{ settleWord }} 완료일<span v-if="draft.ar_status === 'collected'" class="text-danger"> *</span></label>
            <input id="lg-settled" v-model="draft.settled_on" type="date" class="form-control form-control-sm" :max="data.today" :disabled="settledDisabled"
                   :title="settledDisabled ? '외상매출금은 당월 수금일 때만 입력합니다' : ''" />
          </div>
          <div class="col-md-auto ms-auto">
            <button type="button" class="btn btn-sm btn-outline-secondary" @click="editing = null">취소</button>
            <button type="button" class="btn btn-sm btn-primary ms-1" :disabled="saving"
                    @click="save(editing === 'new' ? null : data.rows.find((r) => r.id === editing))">{{ saving ? '저장 중…' : '저장' }}</button>
          </div>
        </div>
      </div>
      <button v-else-if="!showHidden" type="button" class="btn btn-sm btn-outline-primary" @click="startEdit(null)">+ {{ labels.kinds[kind] }} 행 추가</button>
    </div></div>

    <LedgerCopyDialog v-if="copying" :year="ym.year" :month="ym.month" :kind-labels="labels.kinds" @done="copyDone" @close="copying = false" />
    <RowHistoryDialog v-if="historyOf" type="LedgerEntry" :id="historyOf.id" :label="`${monthText} ${labels.kinds[historyOf.kind]} · ${historyOf.partner_name}`" @close="historyOf = null" />

    <template v-if="confirmAsk">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="ledger-ask-title">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="ledger-ask-title" class="modal-title h5">{{ confirmAsk.title }}</h2>
              <button type="button" class="btn-close" aria-label="닫기" @click="confirmAsk = null"></button>
            </div>
            <div class="modal-body">{{ confirmAsk.text }}</div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" @click="confirmAsk = null">돌아가기</button>
              <button type="button" class="btn" :class="confirmAsk.danger ? 'btn-danger' : 'btn-primary'" @click="runAction">{{ confirmAsk.button }}</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>

<style scoped>
/* 지금 아래 입력 줄에서 고치는 행 */
.editing > td {
  background: var(--brand-soft) !important;
}
/* 자동이체 행: 연한 초록 바탕 (엑셀 표시 그대로, "자동이체" 글자도 함께) */
.auto-transfer > td {
  background: #eef7ef;
}
</style>
