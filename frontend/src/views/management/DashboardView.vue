<script setup>
// 경영지원팀 메인 대시보드 (조원 저장소 main-dashboard 를 옮김)
// ① KPI 4개 → ② 목표 달성 현황(목표매출 달성률·매출 구성·매입·지출 구성) → ③ 추이 및 분석(월별 추이·산업 분야별·제품별 생산량) → ④ 팀별 현황
// 숫자는 모두 서버(backend/management/metrics.py)가 계산한다. 확정된 달만 집계하고, 간이 지표는 회계상 값과 다를 수 있다
import { computed, ref, watch } from 'vue'
import { exportTargets, getDashboard } from '@/api/management'
import PeriodSelector from '@/components/PeriodSelector.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import FlowChart from '@/components/management/FlowChart.vue'
import TargetCard from '@/components/management/TargetCard.vue'
import { industryColor, OTHER_COLOR, SERIES_COLORS } from '@/charts'
import { pctText, won, wonShort } from '@/money'
import { period } from '@/period'

const data = ref(null)
const error = ref('')
const exporting = ref(false)

async function load() {
  error.value = ''
  try {
    data.value = await getDashboard(period)
  } catch (e) {
    error.value = e.message
  }
}
watch(period, load, { deep: true, immediate: true })

const s = computed(() => data.value)

// ---------- 확정 안내 ----------
function monthsText(list) {
  if (!list.length) return ''
  const nums = list.map((m) => m.month)
  const contiguous = nums.every((n, i) => i === 0 || n === nums[i - 1] + 1)
  return contiguous && nums.length > 1 ? `${nums[0]}~${nums.at(-1)}월` : `${nums.join('·')}월`
}
const notice = computed(() => {
  const c = s.value?.confirmation
  if (!c) return null
  const un = monthsText(c.unconfirmed_months)
  const ok = monthsText(c.confirmed_months)
  const pend = monthsText(c.pending_months)
  if (c.unconfirmed_months.length) {
    return c.has_data
      ? { tone: 'warning', text: `${un}이 아직 확정되지 않아 ${ok}만 집계되었습니다. 증감은 비교 기간도 같은 월끼리 맞춰 계산했습니다.` }
      : { tone: 'warning', text: `${un}이 아직 확정되지 않아 집계할 데이터가 없습니다.` }
  }
  if (c.pending_months.length) {
    return c.has_data
      ? { tone: 'info', text: `${pend}은 아직 마감 전이라 ${ok}만 집계되었습니다. 증감은 같은 월끼리 맞춰 계산했습니다.` }
      : { tone: 'info', text: `${pend}은 아직 마감 전이라 집계할 데이터가 없습니다.` }
  }
  return null
})

// ---------- KPI 비교 줄 ----------
const PREV_NAME = { month: '전월', quarter: '전분기', year: '전년' }
const REASON = { 'no-current-data': '-', 'no-data': '비교 데이터 없음', 'zero-base': '비교값 0' }
function deltas(pick) {
  const c = s.value.changes
  const rows = [{ label: PREV_NAME[s.value.period.kind], ...pick(c.previous), partial: c.previous.is_partial }]
  if (c.last_year) rows.push({ label: '전년 동기', ...pick(c.last_year), partial: c.last_year.is_partial })
  return rows
}
const rateDeltas = (key) => deltas((c) => ({ value: c[key].rate, reason: c[key].reason, kind: 'rate' }))
const profitDeltas = () => deltas((c) => ({ value: c.profit_diff, reason: c.profit_diff === null ? 'no-data' : null, kind: 'amount' }))
const deltaText = (d) => {
  if (d.value === null || d.value === undefined) return REASON[d.reason] ?? '-'
  const sign = d.value > 0 ? '▲' : d.value < 0 ? '▼' : ''
  return d.kind === 'rate' ? `${sign}${Math.abs(d.value).toFixed(1)}%` : `${sign}${wonShort(Math.abs(d.value))}`
}

// ---------- 구성 도넛 ----------
const revenueItems = computed(() => s.value.revenue.items.map((i) => ({ name: i.label, quantity: i.amount })))
const costItems = computed(() => s.value.costs.items.map((i) => ({ name: i.label, quantity: i.amount })))
const fixedColor = (names) => (name) => {
  const i = names.indexOf(name)
  return i < 0 || i >= SERIES_COLORS.length ? OTHER_COLOR : SERIES_COLORS[i]
}
const revenueColor = fixedColor(['제품', '상품', '용역'])
const costColor = fixedColor(['상품 매입', '원재료 매입', '경비', '그 외 지출'])
// 생산량 집계: 산업 분야는 생산팀 화면과 같은 색, 제품(모델)은 많은 순서로 색 (8번째부터 회색)
const industryItems = computed(() => s.value.teams.industry.map((i) => ({ name: i.name, quantity: i.quantity })))
const productItems = computed(() => s.value.teams.product.map((i) => ({ name: i.name, quantity: i.quantity })))
const productColor = (name) => fixedColor(productItems.value.map((i) => i.name))(name)

async function downloadTargets() {
  exporting.value = true
  try {
    await exportTargets(period.year)
  } catch (e) {
    error.value = e.message
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <PeriodSelector />
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="!s" class="text-muted">불러오는 중…</div>
    <template v-else>
      <div v-if="notice" class="alert py-2" :class="notice.tone === 'warning' ? 'alert-warning' : 'alert-light border'">{{ notice.text }}</div>

      <!-- ① KPI -->
      <div class="row g-3 mb-4">
        <div class="col-sm-6 col-xl-3">
          <div class="card h-100"><div class="card-body">
            <div class="kpi-title">매출</div>
            <div class="kpi-value">{{ wonShort(s.revenue.total) }}</div>
            <div class="small text-muted">확정 {{ s.confirmation.confirmed_months.length }}개월 / {{ s.period.months.length }}개월</div>
            <ul class="list-unstyled small mb-0 mt-2"><li v-for="d in rateDeltas('revenue')" :key="d.label">{{ d.label }} {{ deltaText(d) }}<span v-if="d.partial" title="비교 기간에 미확정 달이 섞여 있음">*</span></li></ul>
          </div></div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card h-100"><div class="card-body">
            <div class="kpi-title">매입·지출 합계</div>
            <div class="kpi-value">{{ wonShort(s.costs.total) }}</div>
            <div class="small text-muted">상품 매입 + 원재료 매입 + 경비 + 그 외 지출</div>
            <ul class="list-unstyled small mb-0 mt-2"><li v-for="d in rateDeltas('costs')" :key="d.label">{{ d.label }} {{ deltaText(d) }}<span v-if="d.partial">*</span></li></ul>
          </div></div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card h-100"><div class="card-body">
            <div class="kpi-title">간이 이익 <span class="badge badge-soft">간이 지표</span></div>
            <div class="kpi-value" :class="{ 'text-danger': s.profit.amount < 0 }">{{ wonShort(s.profit.amount) }}</div>
            <div v-if="s.confirmation.has_data" class="small" :class="s.profit.amount < 0 ? 'text-danger' : 'text-muted'">
              {{ s.profit.amount < 0 ? '적자 · ' : '' }}간이 이익률 {{ pctText(s.profit.margin) }}
            </div>
            <div class="small text-muted">매출 − 매입·지출 (회계상 이익과 다를 수 있음)</div>
            <ul class="list-unstyled small mb-0 mt-2"><li v-for="d in profitDeltas()" :key="d.label">{{ d.label }} {{ deltaText(d) }}<span v-if="d.partial">*</span></li></ul>
          </div></div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card h-100"><div class="card-body">
            <div class="kpi-title">미수금<template v-if="s.receivables.month"> ({{ s.receivables.month.month }}월 외상매출금 기준)</template></div>
            <template v-if="s.receivables.month">
              <div class="kpi-value">{{ wonShort(s.receivables.total) }}</div>
              <div class="small text-muted">거래처 {{ s.receivables.customer_count }}곳<template v-if="s.receivables.is_current_month"> · 이번 달 작성 중</template></div>
              <ul class="list-unstyled small mb-0 mt-2">
                <li :class="{ 'text-danger': s.receivables.long_overdue.amount > 0 }">장기 미수금 {{ wonShort(s.receivables.long_overdue.amount) }} ({{ s.receivables.long_overdue.count }}건)</li>
                <li>당월 수금예정 {{ wonShort(s.receivables.scheduled.amount) }} ({{ s.receivables.scheduled.count }}건)</li>
              </ul>
            </template>
            <template v-else>
              <div class="kpi-value">-</div>
              <div class="small text-muted">이 기간에 경영지원 관리 입력 없음</div>
            </template>
          </div></div>
        </div>
      </div>
      <p class="small text-muted mt-n3 mb-4">* 비교 기간에 확정 안 된 달이 섞여 있어 참고용입니다. 매출·매입·지출은 확정된 달만 더합니다.</p>

      <!-- ② 목표 달성 현황 -->
      <div class="d-flex align-items-center gap-2 mb-2">
        <h2 class="h5 mb-0">목표 달성 현황</h2>
        <button type="button" class="btn btn-sm btn-outline-secondary ms-auto" :disabled="exporting" @click="downloadTargets">
          {{ period.year }}년 목표 대비 실적 엑셀
        </button>
      </div>
      <div class="row g-3 mb-4">
        <div class="col-lg-4"><TargetCard :targets="s.targets" :period="s.period" /></div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6 mb-3">매출 구성 <small class="text-muted fw-normal">총매출 {{ wonShort(s.revenue.total) }}</small></h3>
            <ShareDoughnut :items="revenueItems" :total="s.revenue.total" :color-of="revenueColor" name-header="구분" unit="원" value-header="금액" :size="150" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6 mb-3">매입·지출 구성 <small class="text-muted fw-normal">합계 {{ wonShort(s.costs.total) }}</small></h3>
            <ShareDoughnut :items="costItems" :total="s.costs.total" :color-of="costColor" name-header="구분" unit="원" value-header="금액" :size="150" />
            <details v-if="s.costs.other_items.length" class="small mt-2">
              <summary>그 외 지출 항목별 보기</summary>
              <ul class="list-unstyled mt-2 mb-0">
                <li v-for="i in s.costs.other_items" :key="i.key" class="d-flex justify-content-between"><span>{{ i.label }}</span><span>{{ won(i.amount) }}</span></li>
              </ul>
            </details>
          </div></div>
        </div>
      </div>

      <!-- ③ 추이 및 분석 -->
      <h2 class="h5 mb-2">추이 및 분석</h2>
      <div class="mb-3"><FlowChart :points="s.trend" :highlight="s.period.months.map((m) => ({ year: s.period.year, month: m }))" /></div>
      <div class="row g-3 mb-4">
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6 mb-3">산업 분야별 생산량 <small class="text-muted fw-normal">{{ s.teams.production_total.toLocaleString() }}대</small></h3>
            <ShareDoughnut :items="industryItems" :total="s.teams.production_total" :color-of="industryColor" name-header="산업 분야" :size="150" />
            <p class="small text-muted mt-2 mb-0">제조년월 기준 · 제조내역 1행 = 1대 · PO번호로 수주서의 산업 분야와 연결<template v-if="s.teams.unlinked"> (수주서 미연결 {{ s.teams.unlinked }}대)</template></p>
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6 mb-3">제품별 생산량 <small class="text-muted fw-normal">{{ s.teams.production_total.toLocaleString() }}대</small></h3>
            <ShareDoughnut :items="productItems" :total="s.teams.production_total" :color-of="productColor" name-header="모델" :size="150" />
            <p class="small text-muted mt-2 mb-0">제조년월 기준 · 모델명별</p>
          </div></div>
        </div>
      </div>

      <!-- ④ 팀별 현황 -->
      <h2 class="h5 mb-2">팀별 현황</h2>
      <div class="row g-3">
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <div class="d-flex"><h3 class="h6">생산팀</h3><RouterLink to="/production" class="small ms-auto">생산팀 화면 →</RouterLink></div>
            <div class="row text-center g-2">
              <div class="col-4"><div class="small text-muted">생산량</div><div class="fw-bold fs-5">{{ s.teams.production.actual.toLocaleString() }}대</div>
                <div v-if="s.teams.production.period_target !== null" class="small text-muted">목표 {{ s.teams.production.period_target.toLocaleString() }}대</div></div>
              <div class="col-4"><div class="small text-muted">목표 달성률</div><div class="fw-bold fs-5">{{ pctText(s.teams.production.achievement_rate) }}</div></div>
              <div class="col-4"><div class="small text-muted">납기 일정</div><div class="fw-bold fs-5">{{ s.teams.production.due_count.toLocaleString() }}대</div>
                <div v-if="s.teams.production.due_pending" class="small text-muted">출고 전 {{ s.teams.production.due_pending.toLocaleString() }}대</div></div>
            </div>
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <div class="d-flex"><h3 class="h6">서비스팀</h3><RouterLink to="/service" class="small ms-auto">서비스팀 화면 →</RouterLink></div>
            <div class="row text-center g-2">
              <div class="col-4"><div class="small text-muted">출장 횟수</div><div class="fw-bold fs-5">{{ s.teams.service.trip_count.toLocaleString() }}회</div></div>
              <div class="col-4"><div class="small text-muted">유상 비율</div><div class="fw-bold fs-5">{{ pctText(s.teams.service.paid_rate) }}</div>
                <div class="small text-muted">유상 {{ s.teams.service.paid }} · 무상 {{ s.teams.service.unpaid }}</div></div>
              <div class="col-4"><div class="small text-muted">A/S 제품</div><div class="fw-bold fs-5">{{ s.teams.service.product_quantity.toLocaleString() }}대</div></div>
            </div>
          </div></div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.kpi-title {
  font-weight: 600;
  margin-bottom: 0.35rem;
}
.kpi-value {
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 0.25rem;
}
</style>
