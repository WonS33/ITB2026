<script setup>
// 경영지원 관리 엑셀 이관 (조원 저장소 ledger/import 화면을 옮김) — 고객사 「경영지원_관리」 엑셀 → 장부
// 추출(미리보기) → 사람이 확인·선택 → 저장. 미리보기는 DB에 아무것도 쓰지 않고, 가져올 때 같은 파일을 다시 보내 서버가 다시 검사한다
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { importLedger, previewLedgerImport } from '@/api/management'
import { won } from '@/money'

const KIND_LABEL = { ar: '외상매출금', ap: '외상매입금', accrued_staff: '미지급비용-직원', accrued_vendor: '미지급비용-업체' }
const AR_STATUSES = [
  { value: 'long_overdue', label: '장기 미수금' },
  { value: 'collected', label: '당월 수금' },
  { value: 'scheduled', label: '당월 수금예정' },
]
const AR_LABEL = Object.fromEntries(AR_STATUSES.map((s) => [s.value, s.label]))
const PURCHASE = [{ value: 'goods', label: '상품매입' }, { value: 'raw_material', label: '원재료매입' }]
const EXPENSE = [{ value: 'advertising', label: '광고선전비' }, { value: 'entertainment', label: '접대비' }, { value: 'other', label: '기타' }]
const TOTAL_STATE = {
  match: { text: '일치', cls: 'badge-soft' },
  mismatch: { text: '불일치', cls: 'badge-low' },
  // 수식만 있고 계산 결과가 저장되지 않은 파일 (이 앱에서 내려받은 파일 등) — 엑셀에서 열어 저장하면 계산값이 생긴다. 오류 아님
  no_result: { text: '계산값 없음 (엑셀에서 열어 저장하면 검산 가능)', cls: 'badge-soft' },
  no_total: { text: '총액 칸 비어 있음', cls: 'badge-soft' },
}

const route = useRoute()
const now = new Date()
const thisMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const monthText = ref(/^\d{4}-\d{2}$/.test(route.query.month ?? '') && route.query.month <= thisMonth ? route.query.month : thisMonth)
const file = ref(null)
const sheet = ref('')
const sheetChoices = ref([])
const preview = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const blockers = ref([])
const result = ref(null)
const mode = ref(null)
const choices = reactive({ ar_status: {}, purchase_type: {}, expense_type: {}, settled_on: {} })

const ym = computed(() => ({ year: Number(monthText.value.slice(0, 4)), month: Number(monthText.value.slice(5, 7)) }))

function reset() {
  preview.value = null
  result.value = null
  blockers.value = []
  mode.value = null
  Object.values(choices).forEach((c) => Object.keys(c).forEach((k) => delete c[k]))
}
function pickFile(e) {
  file.value = e.target.files[0] ?? null
  sheet.value = ''
  sheetChoices.value = []
  reset()
}

async function runPreview() {
  if (!file.value) return
  loading.value = true
  error.value = ''
  reset()
  try {
    preview.value = await previewLedgerImport(file.value, ym.value.year, ym.value.month, sheet.value || null)
    sheet.value = preview.value.sheet_name
  } catch (e) {
    error.value = e.message
    sheetChoices.value = e.data?.sheet_choices ?? []
  } finally {
    loading.value = false
  }
}

// ---------- 행마다 고를 값 ----------
const finalStatus = (r) => r.ar_status ?? choices.ar_status[r.row] ?? null
const settledOf = (r) => choices.settled_on[r.row] ?? r.settled_on ?? preview.value.default_settled_on
function setAll(field, value, kind) {
  preview.value.blocks.find((b) => b.kind === kind).rows.forEach((r) => {
    if (!r.errors.length) choices[field][r.row] = value
  })
}

// "남은 할 일" — [가져오기] 버튼 활성화용 (서버가 다시 확인)
const todo = computed(() => {
  if (!preview.value) return null
  const rows = preview.value.blocks.flatMap((b) => b.rows)
  const ok = rows.filter((r) => !r.errors.length)
  return {
    errors: preview.value.fatal.length + rows.filter((r) => r.errors.length).length,
    unclassified: ok.filter((r) => r.kind === 'ar' && !finalStatus(r)).length,
    purchase: ok.filter((r) => r.kind === 'ap' && !choices.purchase_type[r.row]).length,
    needsMode: preview.value.existing_total > 0 && !mode.value,
    empty: !preview.value.fatal.length && !rows.length,
    count: ok.length,
  }
})
const ready = computed(() => todo.value && !todo.value.errors && !todo.value.unclassified && !todo.value.purchase && !todo.value.needsMode && !todo.value.empty)

async function runImport() {
  saving.value = true
  error.value = ''
  blockers.value = []
  // 당월 수금 행 완료일: 사람이 고친 값 > 파일 값(적요 날짜·기본값)
  const settled = {}
  preview.value.blocks.forEach((b) => b.rows.forEach((r) => {
    if (b.kind === 'ar' && finalStatus(r) === 'collected') settled[r.row] = settledOf(r)
  }))
  try {
    result.value = await importLedger(file.value, ym.value.year, ym.value.month, {
      sheet: preview.value.sheet_name,
      file_sha256: preview.value.file_sha256,
      mode: mode.value ?? 'none',
      expected_existing: preview.value.existing_total,
      choices: JSON.stringify({ ...choices, settled_on: settled }),
    })
    preview.value = null
  } catch (e) {
    error.value = e.message
    blockers.value = e.data?.blockers ?? []
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <p class="small text-muted">
      고객사 「경영지원_관리」 엑셀(외상매출금 · 외상매입금 · 미지급비용-직원 · 미지급비용-업체 블록)을 장부로 옮깁니다.
      먼저 미리보기로 확인하고, 엑셀에 없는 값(외상매입금 매입유형 등)을 고른 뒤 가져옵니다. 미리보기만으로는 아무것도 저장되지 않습니다.
    </p>

    <!-- 1) 파일·기준년월 -->
    <div class="card mb-3"><div class="card-body d-flex flex-wrap align-items-end gap-3">
      <div>
        <label class="form-label small mb-1" for="imp-month">기준년월</label>
        <input id="imp-month" v-model="monthText" type="month" :max="thisMonth" class="form-control form-control-sm" @change="reset" />
      </div>
      <div>
        <label class="form-label small mb-1" for="imp-file">엑셀 파일 (.xlsx, 5MB까지)</label>
        <input id="imp-file" type="file" accept=".xlsx" class="form-control form-control-sm" @change="pickFile" />
      </div>
      <div v-if="sheetChoices.length || (preview && preview.sheet_candidates.length > 1)">
        <label class="form-label small mb-1" for="imp-sheet">시트</label>
        <select id="imp-sheet" v-model="sheet" class="form-select form-select-sm">
          <option v-for="s in (sheetChoices.length ? sheetChoices : preview.sheet_candidates)" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <button type="button" class="btn btn-sm btn-primary" :disabled="!file || loading" @click="runPreview">{{ loading ? '읽는 중…' : '미리보기' }}</button>
      <RouterLink :to="{ path: '/management/ledger', query: { month: monthText } }" class="small ms-auto">경영지원 관리로 →</RouterLink>
    </div></div>

    <div v-if="error" class="alert alert-danger py-2">
      {{ error }}
      <ul v-if="blockers.length > 1" class="small mb-0 mt-1"><li v-for="(b, i) in blockers.slice(0, 15)" :key="i">{{ b.message }}</li></ul>
    </div>
    <div v-if="result" class="alert alert-success py-2">
      {{ result.year }}년 {{ result.month }}월에 {{ result.saved }}행을 가져왔습니다<template v-if="result.hidden"> (기존 {{ result.hidden }}행은 숨김)</template>.
      <span class="small">{{ result.blocks.filter((b) => b.count).map((b) => `${KIND_LABEL[b.kind]} ${b.count}행 ${won(b.sum)}`).join(' · ') }}</span>
      <RouterLink :to="{ path: '/management/ledger', query: { month: monthText } }" class="ms-2">장부에서 보기 →</RouterLink>
    </div>

    <!-- 2) 미리보기 -->
    <template v-if="preview">
      <div class="small text-muted mb-2">파일 {{ preview.file_name }} · 시트 {{ preview.sheet_name }}</div>
      <div v-if="preview.sheet_note" class="alert alert-warning py-2 small">{{ preview.sheet_note }}</div>
      <div v-if="preview.fatal.length" class="alert alert-danger py-2"><div v-for="m in preview.fatal" :key="m">{{ m }}</div></div>

      <div v-if="preview.existing_total" class="card mb-3"><div class="card-body">
        <div class="fw-semibold mb-2">{{ preview.year }}년 {{ preview.month }}월에 이미 {{ preview.existing_total }}행이 있습니다. 어떻게 할까요?</div>
        <label class="form-check"><input v-model="mode" type="radio" value="overwrite" class="form-check-input" /> 덮어쓰기 — 기존 {{ preview.existing_total }}행을 숨기고(삭제 아님, 복구 가능) 파일 내용으로 바꿉니다</label>
        <label class="form-check"><input v-model="mode" type="radio" value="append" class="form-check-input" /> 추가 — 기존 행은 그대로 두고 파일 내용을 더합니다 (같은 거래처가 두 번 들어갈 수 있음)</label>
      </div></div>

      <div v-for="b in preview.blocks" :key="b.kind" class="card mb-3"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <h2 class="h6 mb-0">{{ KIND_LABEL[b.kind] }}</h2>
          <span class="small text-muted">{{ b.rows.length }}행 · 합계 {{ won(b.sum) }}<template v-if="b.kind === 'accrued_vendor'"> (자동이체 {{ won(b.auto_transfer_sum) }} 포함)</template></span>
          <span v-for="t in b.totals" :key="t.range" class="badge ms-1" :class="TOTAL_STATE[t.state].cls"
                :title="`파일 총액 ${t.file_total === null ? '-' : won(t.file_total)} / 행 합계 ${won(t.rows_sum)}`">
            총액 {{ t.range }} {{ TOTAL_STATE[t.state].text }}<template v-if="t.state === 'mismatch'"> (파일 {{ won(t.file_total) }} ≠ 행 합계 {{ won(t.rows_sum) }})</template>
          </span>
          <span v-if="b.kind === 'ap'" class="ms-auto small">매입유형 모두
            <button v-for="p in PURCHASE" :key="p.value" type="button" class="btn btn-sm btn-outline-secondary ms-1" @click="setAll('purchase_type', p.value, 'ap')">{{ p.label }}</button>
          </span>
        </div>
        <p v-if="b.skipped_code_only.length || b.skipped_zero.length" class="small text-muted mb-2">
          건너뜀: <template v-if="b.skipped_zero.length">잔액 0원 {{ b.skipped_zero.join(', ') }}행 </template><template v-if="b.skipped_code_only.length">코드만 있는 {{ b.skipped_code_only.join(', ') }}행</template>
        </p>
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light"><tr class="text-nowrap">
              <th>행</th><th v-if="b.kind === 'ar'">코드</th><th>거래처명</th><th class="text-end">잔액</th><th>적요</th>
              <th v-if="b.kind === 'ar'">상태</th><th v-if="b.kind === 'ar'">수금 완료일</th>
              <th v-if="b.kind === 'ap'">매입유형</th>
              <th v-if="b.kind === 'accrued_vendor'">비용유형</th><th v-if="b.kind === 'accrued_vendor'">자동이체</th>
              <th>확인</th>
            </tr></thead>
            <tbody>
              <tr v-if="!b.rows.length"><td colspan="9" class="text-muted small">가져올 행이 없습니다.</td></tr>
              <tr v-for="r in b.rows" :key="r.row" :class="{ 'table-danger': r.errors.length }">
                <td class="text-muted">{{ r.row }}</td>
                <td v-if="b.kind === 'ar'" class="text-nowrap">{{ r.partner_code ?? '-' }}</td>
                <td>{{ r.partner_name }}</td>
                <td class="text-end">{{ r.amount === null ? '-' : r.amount.toLocaleString() }}</td>
                <td class="small">{{ r.note }}</td>
                <template v-if="b.kind === 'ar'">
                  <td class="text-nowrap">
                    <template v-if="r.ar_status">{{ AR_LABEL[r.ar_status] }} <small class="text-muted">({{ r.ar_status_source === 'red' ? '빨간 글씨' : '메모' }})</small></template>
                    <select v-else v-model="choices.ar_status[r.row]" class="form-select form-select-sm" :class="{ 'is-invalid': !finalStatus(r) }" aria-label="상태 고르기">
                      <option :value="undefined" disabled>미분류 — 고르세요</option>
                      <option v-for="s in AR_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
                    </select>
                  </td>
                  <td>
                    <input v-if="finalStatus(r) === 'collected'" type="date" class="form-control form-control-sm" :max="preview.default_settled_on"
                           :value="settledOf(r)" aria-label="수금 완료일" @change="choices.settled_on[r.row] = $event.target.value" />
                    <span v-else class="text-muted">-</span>
                  </td>
                </template>
                <td v-if="b.kind === 'ap'">
                  <select v-model="choices.purchase_type[r.row]" class="form-select form-select-sm" :class="{ 'is-invalid': !r.errors.length && !choices.purchase_type[r.row] }" aria-label="매입유형">
                    <option :value="undefined" disabled>고르세요</option>
                    <option v-for="p in PURCHASE" :key="p.value" :value="p.value">{{ p.label }}</option>
                  </select>
                </td>
                <template v-if="b.kind === 'accrued_vendor'">
                  <td>
                    <select :value="choices.expense_type[r.row] ?? 'other'" class="form-select form-select-sm" aria-label="비용유형" @change="choices.expense_type[r.row] = $event.target.value">
                      <option v-for="x in EXPENSE" :key="x.value" :value="x.value">{{ x.label }}</option>
                    </select>
                  </td>
                  <td>{{ r.auto_transfer ? '자동이체' : '-' }}</td>
                </template>
                <td class="small">
                  <div v-for="m in r.errors" :key="m" class="text-danger">{{ m }}</div>
                  <div v-for="m in r.warnings" :key="m" class="text-warn">{{ m }}</div>
                  <div v-if="r.settled_source === 'note' && finalStatus(r) === 'collected'" class="text-muted">완료일 = 적요 날짜</div>
                  <div v-else-if="finalStatus(r) === 'collected' && !choices.settled_on[r.row]" class="text-muted">완료일 = 기준월 말일(오늘 이전)</div>
                  <div v-if="r.note_date_ignored" class="text-warn">{{ r.note_date_ignored }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div></div>

      <!-- 3) 남은 할 일 → 가져오기 -->
      <div class="card"><div class="card-body d-flex flex-wrap align-items-center gap-3">
        <ul class="small mb-0">
          <li v-if="todo.errors" class="text-danger">파일 오류 {{ todo.errors }}건 — 엑셀을 고친 뒤 다시 올려 주세요</li>
          <li v-if="todo.unclassified">외상매출금 상태를 고를 행 {{ todo.unclassified }}개</li>
          <li v-if="todo.purchase">외상매입금 매입유형을 고를 행 {{ todo.purchase }}개</li>
          <li v-if="todo.needsMode">덮어쓰기·추가 중에 고르세요</li>
          <li v-if="todo.empty">가져올 데이터가 없습니다</li>
          <li v-if="ready" class="text-success">준비됐습니다. {{ todo.count }}행을 가져옵니다.</li>
        </ul>
        <button type="button" class="btn btn-primary ms-auto" :disabled="!ready || saving" @click="runImport">{{ saving ? '가져오는 중…' : `${todo.count}행 가져오기` }}</button>
      </div></div>
    </template>
  </div>
</template>
