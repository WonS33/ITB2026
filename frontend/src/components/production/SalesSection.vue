<script setup>
// 판매 실적: 직원이 기준을 바꿔 가며 보는 화면 (specs/05-production.md 1절, specs/09-metrics.md 3절)
// - 설정: 기준 날짜 · 거래처 기준 · 제품 묶음 · 비교 기간 (브라우저에 기억 — 개인 편의용)
// - 교차 필터: 산업 분야·거래처·제품을 누르면 나머지 순위가 그 조건으로 좁혀진다
import { reactive, ref, watch } from 'vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import SalesRanking from '@/components/production/SalesRanking.vue'
import { getSales } from '@/api/production'
import { industryColor } from '@/charts'
import { period } from '@/period'

const OPTIONS = {
  date_basis: { label: '기준 날짜', choices: [['due', '납기일'], ['order', '수주일'], ['delivery', '납품일']] },
  customer_basis: { label: '거래처', choices: [['customer', '판매처'], ['final_orderer', '최종발주처']] },
  product_group: { label: '제품 묶음', choices: [['name', '품명 그대로'], ['model', '모델별'], ['size', '구경별'], ['type', '종류별']] },
  compare: { label: '비교', choices: [['none', '비교 안 함'], ['previous', '직전 기간'], ['last_year', '전년 동기']] },
}
const DEFAULTS = { date_basis: 'due', customer_basis: 'customer', product_group: 'name', compare: 'none' }
const STORAGE_KEY = 'production.sales.settings'

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    // 저장된 값이 지금 고를 수 있는 값일 때만 쓴다
    return Object.fromEntries(
      Object.entries(DEFAULTS).map(([k, v]) => [k, OPTIONS[k].choices.some(([c]) => c === saved[k]) ? saved[k] : v]),
    )
  } catch {
    return { ...DEFAULTS }
  }
}

const settings = reactive(loadSettings())
const filters = reactive({ industry: '', customer: '', product: '' })
const FILTER_NAMES = { industry: '산업 분야', customer: '거래처', product: '제품' }
const data = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    data.value = await getSales(period, { ...settings, ...filters })
  } catch (e) {
    error.value = e.message
  }
}

watch(
  settings,
  () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {
      // 저장이 막힌 브라우저에서도 화면은 그대로 동작
    }
  },
  { deep: true },
)
// 기준이 바뀌면 같은 이름이 다른 뜻이 되므로 그 필터는 푼다
watch(() => settings.customer_basis, () => (filters.customer = ''))
watch(() => settings.product_group, () => (filters.product = ''))
watch([period, settings, filters], load, { deep: true, immediate: true })

const toggle = (key, name) => (filters[key] = filters[key] === name ? '' : name)
const clearFilters = () => Object.assign(filters, { industry: '', customer: '', product: '' })
const activeFilters = () => Object.entries(filters).filter(([, v]) => v)
const choiceLabel = (key) => OPTIONS[key].choices.find(([v]) => v === settings[key])[1]
const signed = (n) => (n > 0 ? `▲ ${n}` : n < 0 ? `▼ ${-n}` : '변동 없음')
const changeRate = (c) => (c.total ? `${c.change >= 0 ? '+' : ''}${Math.round((c.change / c.total) * 1000) / 10}%` : '')
</script>

<template>
  <div class="mb-4">
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <div class="d-flex flex-wrap align-items-baseline gap-2 mb-1">
        <h2 class="h6 mb-0">{{ data.period.label }} 판매 실적 <span class="text-muted fw-normal">· 총 {{ data.sales.total.toLocaleString() }}대</span></h2>
        <span v-if="data.sales.compare" class="small">
          {{ data.sales.compare.label }} {{ data.sales.compare.total.toLocaleString() }}대 대비
          <strong>{{ signed(data.sales.compare.change) }}대</strong>
          <span class="text-muted">{{ changeRate(data.sales.compare) }}</span>
        </span>
      </div>
      <p class="text-muted small mb-2">
        수주서 제품 수량 기준 · 기간은 {{ choiceLabel('date_basis') }}, 거래처는 {{ choiceLabel('customer_basis') }} 기준
        <template v-if="settings.date_basis === 'due' && settings.customer_basis === 'customer'">(기업 확인 전 임시 기준)</template>
        <template v-if="data.sales.missing_date_orders"> · {{ choiceLabel('date_basis') }}이 비어 있는 수주서 {{ data.sales.missing_date_orders }}건은 이 기준에서 빠집니다</template>
      </p>

      <!-- 설정: 직원이 바꿔 보며 인사이트를 찾는 영역 (고른 값은 이 브라우저에 기억) -->
      <div class="d-flex flex-wrap align-items-center gap-3 small mb-2 p-2 rounded settings">
        <label v-for="(o, key) in OPTIONS" :key="key" class="d-flex align-items-center gap-1">
          <span class="text-muted text-nowrap">{{ o.label }}</span>
          <select v-model="settings[key]" class="form-select form-select-sm w-auto">
            <option v-for="[value, text] in o.choices" :key="value" :value="value">{{ text }}</option>
          </select>
        </label>
      </div>

      <!-- 지금 걸러 보는 조건 -->
      <div class="d-flex flex-wrap align-items-center gap-2 small mb-3" style="min-height: 1.75rem">
        <template v-if="activeFilters().length">
          <span class="text-muted">걸러 보는 중:</span>
          <button
            v-for="[key, value] in activeFilters()"
            :key="key"
            type="button"
            class="btn btn-sm btn-outline-secondary py-0"
            :aria-label="`${FILTER_NAMES[key]} ${value} 걸러내기 해제`"
            @click="filters[key] = ''"
          >{{ FILTER_NAMES[key] }} = {{ value }} ✕</button>
          <button type="button" class="btn btn-link btn-sm p-0" @click="clearFilters">모두 해제</button>
        </template>
        <span v-else class="text-muted">산업 분야·거래처·제품을 누르면 나머지 순위가 그 조건으로 좁혀집니다.</span>
      </div>

      <div class="row g-3">
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">산업 분야별 비중</h3>
            <ShareDoughnut
              :items="data.sales.by_industry"
              :total="data.sales.by_industry.reduce((s, i) => s + i.quantity, 0)"
              :color-of="industryColor"
              name-header="분야"
              clickable
              @select="toggle('industry', $event)"
            />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">산업 분야별 순위</h3>
            <SalesRanking
              :items="data.sales.by_industry"
              :total="data.sales.by_industry.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.industry"
              :color-of="industryColor"
              :compare-label="data.sales.compare?.label || ''"
              @select="toggle('industry', $event)"
            />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">거래처별 순위 <span class="text-muted fw-normal small">· {{ choiceLabel('customer_basis') }}</span></h3>
            <SalesRanking
              :items="data.sales.by_customer"
              :total="data.sales.by_customer.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.customer"
              :compare-label="data.sales.compare?.label || ''"
              @select="toggle('customer', $event)"
            />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">제품별 순위 <span class="text-muted fw-normal small">· {{ choiceLabel('product_group') }}</span></h3>
            <SalesRanking
              :items="data.sales.by_product"
              :total="data.sales.by_product.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.product"
              :compare-label="data.sales.compare?.label || ''"
              @select="toggle('product', $event)"
            />
            <p v-if="settings.product_group !== 'name'" class="text-muted small mt-1 mb-0">
              품명 "종류 구경: 모델"(예: 제수 150A: NTI-03) 형식으로 묶습니다. 형식이 다른 품명은 "기타(형식 다름)".
            </p>
          </div></div>
        </div>
      </div>
      <p v-if="data.sales.compare" class="text-muted small mt-2 mb-0">
        증감 = 이번 기간 − {{ data.sales.compare.label }} (같은 설정·같은 걸러내기 조건). 이번 기간에 없는 항목은 순위에 나오지 않습니다.
      </p>
    </template>
  </div>
</template>

<style scoped>
.settings {
  background: #f4f6f9;
}
</style>
