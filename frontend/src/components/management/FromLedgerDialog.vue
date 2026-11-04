<script setup>
// [경영지원 관리에서 불러오기] 미리보기 확인창 — [입력란에 채우기]를 누르면 입력란에 값만 채우고, 저장은 [임시저장]·[확정]으로
// 계산은 fromLedger.js, 행은 GET /api/management/monthly/{y}/{m}/ledger/ (읽기만)
import { computed, onMounted, reactive, ref } from 'vue'
import { getMonthlyLedger } from '@/api/management'
import { BLOCKS, VENDOR_KEYS, defaultVendorCategory, planFill, skippedNotes, sumLedgerRows } from '@/fromLedger'

const props = defineProps({
  year: { type: Number, required: true },
  month: { type: Number, required: true },
  categories: { type: Array, required: true }, // 이 달 입력 화면의 그 외 지출 항목 [{category_id, name, is_active}]
  current: { type: Function, required: true }, // 칸 → 지금 입력란 값
  fieldLabels: { type: Object, required: true },
})
const emit = defineEmits(['apply', 'close'])

const won = (v) => `${(v ?? 0).toLocaleString('ko-KR')}원`
const loading = ref(true)
const error = ref('')
const rows = ref([])
const vendorLabels = ref({})
const choice = reactive({
  vat: Object.fromEntries(BLOCKS.map((b) => [b.kind, b.vat])),
  unclassifiedPurchase: null,
  vendorCategory: {},
})

const sums = computed(() => sumLedgerRows(rows.value))
const lines = computed(() => planFill(sums.value, choice))
const notes = computed(() => skippedNotes(sums.value, choice, vendorLabels.value, won))
const categoryName = (id) => props.categories.find((c) => c.category_id === id)?.name ?? '(알 수 없는 항목)'
const lineLabel = (l) => (l.target.type === 'field' ? props.fieldLabels[l.target.field] : `그 외 지출 · ${categoryName(l.target.categoryId)}`)
const lineCurrent = (l) => props.current(l.target)

onMounted(async () => {
  try {
    const res = await getMonthlyLedger(props.year, props.month)
    rows.value = res.rows
    vendorLabels.value = res.expense_type_labels
    Object.assign(choice.vendorCategory, defaultVendorCategory(props.categories, res.expense_type_labels))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="ledger-title">
    <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h2 id="ledger-title" class="modal-title h5">{{ year }}년 {{ month }}월 경영지원 관리에서 불러오기</h2>
          <button type="button" class="btn-close" aria-label="닫기" @click="emit('close')"></button>
        </div>
        <div class="modal-body">
          <p v-if="loading" class="text-muted">불러오는 중…</p>
          <div v-else-if="error" class="alert alert-danger py-2">{{ error }}</div>
          <p v-else-if="!rows.length" class="mb-0">이 달 경영지원 관리에 외상매입금·미지급비용 행이 없습니다.</p>
          <template v-else>
            <p class="small text-muted">
              경영지원 관리의 외상매입금 → 매입, 미지급비용-직원 → 경비 지출, 미지급비용-업체(자동이체 포함) → 그 외 지출로 채웁니다.
              장부는 부가세 포함 금액이라, 체크한 블록은 ÷1.1 공급가액으로 바꿔 넣습니다. 채운 뒤 [임시저장]이나 [확정]을 눌러야 저장됩니다.
            </p>

            <!-- 블록 합계 + ÷1.1 환산 체크 -->
            <table class="table table-sm align-middle">
              <thead class="table-light">
                <tr><th>블록</th><th class="text-end">행</th><th class="text-end">합계(부가세 포함)</th><th class="text-center">÷1.1 환산</th></tr>
              </thead>
              <tbody>
                <tr v-for="b in BLOCKS" :key="b.kind">
                  <td>{{ b.label }}</td>
                  <td class="text-end">{{ sums.blockTotal[b.kind].count }}</td>
                  <td class="text-end">{{ won(sums.blockTotal[b.kind].amount) }}</td>
                  <td class="text-center">
                    <input v-model="choice.vat[b.kind]" class="form-check-input" type="checkbox" :aria-label="`${b.label} ÷1.1 환산`" />
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-if="sums.vendorAuto.count" class="small text-muted">
              미지급비용-업체 중 자동이체 {{ sums.vendorAuto.count }}행({{ won(sums.vendorAuto.amount) }})도 포함합니다.
            </p>

            <!-- 넣을 칸 고르기 -->
            <div class="row g-2 mb-3">
              <div v-if="sums.unclassifiedPurchase.count" class="col-md-6">
                <label class="form-label small mb-1" for="unclassified">매입유형이 빈 외상매입금 {{ sums.unclassifiedPurchase.count }}행</label>
                <select id="unclassified" v-model="choice.unclassifiedPurchase" class="form-select form-select-sm">
                  <option :value="null">채우지 않음</option>
                  <option value="merchandise_purchase">{{ fieldLabels.merchandise_purchase }}</option>
                  <option value="material_purchase">{{ fieldLabels.material_purchase }}</option>
                </select>
              </div>
              <template v-for="key in VENDOR_KEYS" :key="key">
                <div v-if="sums.vendor[key].count" class="col-md-6">
                  <label class="form-label small mb-1" :for="`vendor-${key}`">업체 "{{ vendorLabels[key] }}" {{ sums.vendor[key].count }}행 → 그 외 지출 항목</label>
                  <select :id="`vendor-${key}`" v-model="choice.vendorCategory[key]" class="form-select form-select-sm">
                    <option :value="null">채우지 않음</option>
                    <option v-for="c in categories.filter((c) => c.is_active)" :key="c.category_id" :value="c.category_id">{{ c.name }}</option>
                  </select>
                </div>
              </template>
            </div>

            <!-- 미리보기 -->
            <table v-if="lines.length" class="table table-sm align-middle mb-2">
              <thead class="table-light">
                <tr><th>입력 칸</th><th class="text-end">행</th><th class="text-end">원본(부가세 포함)</th><th class="text-end">지금 값</th><th class="text-end">채울 값</th></tr>
              </thead>
              <tbody>
                <tr v-for="l in lines" :key="lineLabel(l)">
                  <td>{{ lineLabel(l) }}</td>
                  <td class="text-end">{{ l.count }}</td>
                  <td class="text-end">{{ won(l.source) }}</td>
                  <td class="text-end text-muted">{{ won(lineCurrent(l)) }}</td>
                  <td class="text-end fw-semibold" :class="{ 'text-primary': l.value !== (lineCurrent(l) ?? 0) }">{{ won(l.value) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="small text-muted">채울 칸이 없습니다.</p>
            <p v-for="n in notes" :key="n" class="small text-warn mb-1">{{ n }}</p>
          </template>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" @click="emit('close')">돌아가기</button>
          <button type="button" class="btn btn-primary" :disabled="loading || !lines.length" @click="emit('apply', lines)">입력란에 채우기</button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop show"></div>
</template>
