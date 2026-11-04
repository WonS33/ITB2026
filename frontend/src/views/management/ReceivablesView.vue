<script setup>
// 미수금 건별 기록 (조원 저장소 receivables 화면을 옮김) — 건별 메모·수금 기록용. 경과일은 발생일부터 센다
// 대시보드 미수금은 경영지원 관리 장부(외상매출금) 기준이라, 맨 위에 같은 기준일의 두 합계를 나란히 보여 준다
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { exportReceivables, getReceivables, receivableAction } from '@/api/management'
import ReceivableForm from '@/components/management/ReceivableForm.vue'
import RowHistoryDialog from '@/components/management/RowHistoryDialog.vue'
import { won } from '@/money'

const TABS = [
  { key: 'open', label: '미수' },
  { key: 'collected', label: '수금 완료' },
  { key: 'over90', label: '90일 초과' },
  { key: 'overdue', label: '예정일 지남' },
  { key: 'all', label: '전체' },
]
const route = useRoute()
const router = useRouter()
const data = ref(null)
const error = ref('')
const message = ref('')
const tab = ref(TABS.some((t) => t.key === route.query.tab) ? route.query.tab : 'open')
const query = ref(route.query.q ?? '')
const showHidden = ref(route.query.hidden === '1')
const editing = ref(null) // { mode, row }
const confirmAsk = ref(null) // { row, action, title, text, button, danger }
const historyOf = ref(null)
const busyId = ref(null)

async function load() {
  error.value = ''
  try {
    data.value = await getReceivables()
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)

// 탭·검색어·숨김 보기를 주소에 남겨 새로고침·뒤로 가기 후에도 유지
function sync() {
  const q = {}
  if (tab.value !== 'open') q.tab = tab.value
  if (query.value.trim()) q.q = query.value.trim()
  if (showHidden.value) q.hidden = '1'
  router.replace({ query: q })
}

const today = computed(() => data.value?.today)
const visibleRows = computed(() => (data.value?.rows ?? []).filter((r) => r.hidden === showHidden.value))
const matchesSearch = (r) => {
  const q = query.value.replace(/\s+/g, '').toLowerCase()
  return !q || r.customer_name.replace(/\s+/g, '').toLowerCase().includes(q)
}
const matchesTab = (r, key) =>
  ({ open: !r.is_collected, collected: r.is_collected, over90: r.over90, overdue: r.overdue, all: true })[key]
const rows = computed(() => visibleRows.value.filter((r) => matchesSearch(r) && matchesTab(r, tab.value)))
const counts = computed(() => Object.fromEntries(TABS.map((t) => [t.key, visibleRows.value.filter((r) => matchesSearch(r) && matchesTab(r, t.key)).length])))
const hiddenCount = computed(() => (data.value?.rows ?? []).filter((r) => r.hidden).length)

// 오늘 기준 요약 (숨긴 건 제외)
const summary = computed(() => {
  const open = (data.value?.rows ?? []).filter((r) => !r.hidden && !r.is_collected)
  const pick = (list) => ({ amount: list.reduce((s, r) => s + r.amount, 0), count: list.length })
  return [
    { label: '미수 합계', ...pick(open), tone: '' },
    { label: '90일 초과', ...pick(open.filter((r) => r.over90)), tone: 'text-danger' },
    { label: '예정일 지남', ...pick(open.filter((r) => r.overdue)), tone: 'text-warn' },
  ]
})

async function done(text) {
  editing.value = null
  await load() // 다시 불러온 뒤에 안내
  message.value = text
}

const ASK = {
  uncollect: (r) => ({ title: `${r.customer_name} 수금을 취소할까요?`, text: `${r.collected_on} 수금 기록을 지우고 미수로 되돌립니다.`, button: '수금 취소', danger: true }),
  hide: (r) => ({ title: `${r.customer_name} 건을 숨길까요?`, text: `${r.occurred_on} 발생 · ${won(r.amount)}. 숨긴 건은 목록·통계에서 빠집니다. 삭제되지는 않으며 [숨긴 항목 보기]에서 복구할 수 있습니다.`, button: '숨기기', danger: true }),
  restore: () => ({ title: '이 건을 복구할까요?', text: '목록·통계에 다시 포함됩니다.', button: '복구', danger: false }),
}
const ask = (row, action) => (confirmAsk.value = { row, action, ...ASK[action](row) })

async function runAction() {
  const { row, action } = confirmAsk.value
  confirmAsk.value = null
  busyId.value = row.id
  error.value = ''
  message.value = ''
  try {
    const res = await receivableAction(row.id, action, { expected_updated_at: row.updated_at })
    await load()
    message.value = res.message
  } catch (e) {
    error.value = e.status === 409 ? `${e.message} [다시 불러오기]를 눌러 주세요.` : e.message
  } finally {
    busyId.value = null
  }
}

// 엑셀: 이번 달(오늘 기준) / 지난달 말 / 지난 분기 말 — 기준일 = min(기간 말일, 오늘)
const exportOptions = computed(() => {
  if (!today.value) return []
  const [y, m] = today.value.split('-').map(Number)
  const prev = m === 1 ? { year: y - 1, month: 12 } : { year: y, month: m - 1 }
  const q = Math.ceil(m / 3)
  const lastQ = q === 1 ? { year: y - 1, quarter: 4 } : { year: y, quarter: q - 1 }
  return [
    { label: '이번 달 · 오늘 기준', period: { year: y, kind: 'month', month: m } },
    { label: `지난달 · ${prev.month}월 말`, period: { ...prev, kind: 'month' } },
    { label: `지난 분기 · ${lastQ.quarter}분기 말`, period: { ...lastQ, kind: 'quarter' } },
  ]
})
async function download(period) {
  try {
    await exportReceivables(period)
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <p class="small text-muted mb-0">건별 메모·수금 기록용 화면입니다. 경과일은 발생일부터 셉니다. 저장한 내용은 [변경 이력]에 남습니다.</p>
      <div class="ms-auto d-flex align-items-center gap-2">
        <small class="text-muted">엑셀</small>
        <div class="btn-group btn-group-sm" role="group" aria-label="미수금 엑셀 기준일">
          <button v-for="o in exportOptions" :key="o.label" type="button" class="btn btn-outline-secondary" @click="download(o.period)">{{ o.label }}</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger py-2 d-flex align-items-center gap-2">
      <span>{{ error }}</span><button type="button" class="btn btn-sm btn-outline-danger ms-auto" @click="load">다시 불러오기</button>
    </div>
    <div v-if="message" class="alert alert-success py-2">{{ message }}</div>
    <div v-if="!data" class="text-muted">불러오는 중…</div>
    <template v-else>
      <!-- 대시보드 미수금(장부)과 같은 기준일로 비교 — 어긋나면 바로 보이게 (막지는 않음) -->
      <div class="alert alert-light border small" role="note">
        대시보드 미수금은 <RouterLink to="/management">경영지원 관리 외상매출금</RouterLink> 기준입니다.
        <template v-if="data.basis.ar_month">
          {{ data.basis.as_of }} 기준 — 외상매출금({{ data.basis.ar_month.month }}월) <strong>{{ won(data.basis.ar_total) }}</strong>,
          이 화면 <strong>{{ won(data.basis.item_total) }}</strong>
          <span v-if="data.basis.ar_total !== data.basis.item_total" class="text-warn">
            (차이 {{ won(Math.abs(data.basis.item_total - data.basis.ar_total)) }})</span>
        </template>
        <template v-else> 올해 외상매출금 입력이 아직 없습니다. 이 화면 합계({{ data.basis.as_of }} 기준) {{ won(data.basis.item_total) }}</template>
      </div>

      <div class="row g-3 mb-3">
        <div v-for="s in summary" :key="s.label" class="col-sm-4">
          <div class="card h-100"><div class="card-body">
            <div class="small text-muted">{{ s.label }} ({{ today }} 기준)</div>
            <div class="fs-5 fw-bold" :class="s.tone">{{ won(s.amount) }} <small class="text-muted fw-normal fs-6">{{ s.count }}건</small></div>
          </div></div>
        </div>
      </div>

      <div class="card"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
          <div class="btn-group btn-group-sm" role="group" aria-label="미수금 필터">
            <button v-for="t in TABS" :key="t.key" type="button" class="btn" :class="tab === t.key ? 'btn-secondary' : 'btn-outline-secondary'"
                    :aria-pressed="tab === t.key" @click="tab = t.key; sync()">
              {{ t.label }} <span class="opacity-75">{{ counts[t.key] }}</span>
            </button>
          </div>
          <input v-model="query" type="search" class="form-control form-control-sm ms-auto" style="max-width: 14rem" placeholder="거래처 검색" aria-label="거래처 검색" @input="sync" />
          <label class="form-check-label small d-flex align-items-center gap-1">
            <input v-model="showHidden" type="checkbox" class="form-check-input mt-0" @change="sync" /> 숨긴 항목 보기 ({{ hiddenCount }})
          </label>
          <button v-if="!showHidden" type="button" class="btn btn-sm btn-primary" @click="message = ''; editing = { mode: 'create', row: null }">+ 미수금 등록</button>
        </div>
        <p v-if="showHidden" class="small text-muted bg-light rounded px-2 py-1">숨긴 항목만 보고 있습니다. 숨긴 건은 통계에 포함되지 않습니다.</p>

        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0" style="min-width: 900px">
            <thead class="table-light">
              <tr class="text-nowrap"><th>거래처</th><th>발생일</th><th class="text-end">금액(원)</th><th>수금 예정일</th><th class="text-end">경과일</th><th>상태</th><th>비고</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-if="!rows.length"><td colspan="8" class="text-center text-muted py-4">{{ showHidden ? '숨긴 항목이 없습니다.' : '조건에 맞는 미수금이 없습니다.' }}</td></tr>
              <tr v-for="r in rows" :key="r.id" :class="{ 'text-muted': r.is_collected, 'opacity-50': busyId === r.id }">
                <td class="text-truncate" style="max-width: 12rem" :title="r.customer_name">{{ r.customer_name }}</td>
                <td class="text-nowrap">{{ r.occurred_on }}</td>
                <td class="text-end">{{ r.amount.toLocaleString() }}</td>
                <td class="text-nowrap" :class="{ 'text-warn': r.overdue }">{{ r.due_on ?? '-' }}</td>
                <td class="text-end text-nowrap" :class="{ 'text-danger fw-semibold': r.over90 }">{{ r.age_days === null ? '-' : `${r.age_days}일` }}</td>
                <td>
                  <span v-if="r.is_collected" class="badge badge-soft">수금 {{ r.collected_on }}</span>
                  <span v-else class="badge badge-soft-brand">미수</span>
                  <span v-if="r.over90" class="badge badge-low ms-1">90일 초과</span>
                  <span v-if="r.overdue" class="badge badge-warn ms-1">예정일 지남</span>
                  <span v-if="r.hidden" class="badge badge-soft ms-1">숨김 {{ r.deleted_at?.slice(0, 10) }} · {{ r.deleted_by }}</span>
                </td>
                <td class="small text-truncate" style="max-width: 12rem" :title="r.note">{{ r.note }}</td>
                <td class="text-end text-nowrap">
                  <button type="button" class="btn btn-sm btn-light" @click="historyOf = r">이력</button>
                  <template v-if="r.hidden">
                    <button type="button" class="btn btn-sm btn-outline-primary ms-1" :disabled="busyId === r.id" @click="ask(r, 'restore')">복구</button>
                  </template>
                  <template v-else>
                    <button v-if="!r.is_collected" type="button" class="btn btn-sm btn-outline-primary ms-1" :disabled="busyId === r.id"
                            @click="message = ''; editing = { mode: 'collect', row: r }">수금 처리</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary ms-1" :disabled="busyId === r.id"
                            @click="message = ''; editing = { mode: 'edit', row: r }">수정</button>
                    <button v-if="r.is_collected" type="button" class="btn btn-sm btn-outline-secondary ms-1" :disabled="busyId === r.id" @click="ask(r, 'uncollect')">수금 취소</button>
                    <button type="button" class="btn btn-sm btn-outline-danger ms-1" :disabled="busyId === r.id" @click="ask(r, 'hide')">숨기기</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div></div>
    </template>

    <ReceivableForm v-if="editing" :mode="editing.mode" :row="editing.row" :today="today" :customer-names="data.customer_names"
                    @done="done" @close="editing = null" />
    <RowHistoryDialog v-if="historyOf" type="Receivable" :id="historyOf.id" :label="`${historyOf.customer_name} · ${historyOf.occurred_on}`" @close="historyOf = null" />

    <template v-if="confirmAsk">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="rcv-ask-title">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="rcv-ask-title" class="modal-title h5">{{ confirmAsk.title }}</h2>
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

