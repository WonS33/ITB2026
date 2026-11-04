<script setup>
// 생산량 집계: 직원이 기준을 바꿔 가며 보는 화면 (specs/05-production.md 1절, specs/09-metrics.md 3절)
// 2026-11-04 기업 확인: "판매량 집계" → "생산량 집계", 제조년월 기준 (제조내역 1행 = 1대)
// - 산업 분야는 PO번호와 같은 번호의 수주서에서 가져온다 (못 찾으면 "수주서 미연결")
// - 설정: 거래처 기준 · 제품 묶음 · 비교 기간 (브라우저에 기억 — 개인 편의용)
// - 교차 필터: 산업 분야·거래처·제품을 누르면 나머지 순위가 그 조건으로 좁혀진다
import { reactive, ref, watch } from 'vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import BreakdownRanking from '@/components/production/BreakdownRanking.vue'
import { getBreakdown } from '@/api/production'
import { industryColor } from '@/charts'
import { period } from '@/period'

const OPTIONS = {
  customer_basis: { label: '거래처', choices: [['customer', '거래처'], ['final_orderer', '최종발주처']] },
  product_group: { label: '제품 묶음', choices: [['model', '모델별'], ['series', '시리즈별']] },
  compare: { label: '비교', choices: [['none', '비교 안 함'], ['previous', '직전 기간'], ['last_year', '전년 동기']] },
}
const DEFAULTS = { customer_basis: 'customer', product_group: 'model', compare: 'none' }
const STORAGE_KEY = 'production.breakdown.settings'

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
    data.value = await getBreakdown(period, { ...settings, ...filters })
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
        <h2 class="h6 mb-0">{{ data.period.label }} 생산량 집계 <span class="text-muted fw-normal">· 총 {{ data.breakdown.total.toLocaleString() }}대</span></h2>
        <span v-if="data.breakdown.compare" class="small">
          {{ data.breakdown.compare.label }} {{ data.breakdown.compare.total.toLocaleString() }}대 대비
          <strong>{{ signed(data.breakdown.compare.change) }}대</strong>
          <span class="text-muted">{{ changeRate(data.breakdown.compare) }}</span>
        </span>
      </div>
      <p class="text-muted small mb-2">
        제조내역 기준(제조년월, 1행 = 1대) · 거래처는 제조내역의 {{ choiceLabel('customer_basis') }} ·
        산업 분야는 PO번호와 같은 번호의 수주서에서 가져옵니다
        <template v-if="data.breakdown.unlinked"> · 수주서를 찾지 못한 {{ data.breakdown.unlinked }}대는 "수주서 미연결"</template>
        <template v-if="data.breakdown.missing_date_records"> · 제조년월이 비어 있는 제조내역 {{ data.breakdown.missing_date_records }}건은 빠집니다</template>
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
              :items="data.breakdown.by_industry"
              :total="data.breakdown.by_industry.reduce((s, i) => s + i.quantity, 0)"
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
            <BreakdownRanking
              :items="data.breakdown.by_industry"
              :total="data.breakdown.by_industry.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.industry"
              :color-of="industryColor"
              :compare-label="data.breakdown.compare?.label || ''"
              @select="toggle('industry', $event)"
            />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">거래처별 순위 <span class="text-muted fw-normal small">· {{ choiceLabel('customer_basis') }}</span></h3>
            <BreakdownRanking
              :items="data.breakdown.by_customer"
              :total="data.breakdown.by_customer.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.customer"
              :compare-label="data.breakdown.compare?.label || ''"
              @select="toggle('customer', $event)"
            />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">제품별 순위 <span class="text-muted fw-normal small">· {{ choiceLabel('product_group') }}</span></h3>
            <BreakdownRanking
              :items="data.breakdown.by_product"
              :total="data.breakdown.by_product.reduce((s, i) => s + i.quantity, 0)"
              :selected="filters.product"
              :compare-label="data.breakdown.compare?.label || ''"
              @select="toggle('product', $event)"
            />
          </div></div>
        </div>
      </div>
      <p v-if="data.breakdown.compare" class="text-muted small mt-2 mb-0">
        증감 = 이번 기간 − {{ data.breakdown.compare.label }} (같은 설정·같은 걸러내기 조건). 이번 기간에 없는 항목은 순위에 나오지 않습니다.
      </p>
    </template>
  </div>
</template>

<style scoped>
.settings {
  background: #f4f6f9;
}
</style>
