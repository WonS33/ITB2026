<script setup>
// 경영지원 상세 (조원 저장소 management-detail 을 옮김) — 표·수치 위주, 금액은 원 단위 전체
// 매출 구성·이익 계산·분기별 목표 표 → 지출 항목 표 → 손익분기점·인당 생산성 → 매출 구성 월별 추이 → 미수금 상세 → 자금 수지 예측
// 계산은 서버(management/metrics.py, detail_metrics.py). 간이 지표는 회계상 값과 다를 수 있고, 예측은 실제값과 구분해 표시한다
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getDetail } from '@/api/management'
import PeriodSelector from '@/components/PeriodSelector.vue'
import CashForecast from '@/components/management/CashForecast.vue'
import RevenueMixChart from '@/components/management/RevenueMixChart.vue'
import { pctText, won } from '@/money'
import { period } from '@/period'

const data = ref(null)
const error = ref('')
const route = useRoute()
let scrolled = false
async function load() {
  error.value = ''
  try {
    data.value = await getDetail(period)
    // 대시보드의 "손익분기점 보기 →"·"전체 보기 →"(#break-even, #receivables): 그린 뒤 그 구역으로 한 번 이동
    if (route.hash && !scrolled) {
      scrolled = true
      await nextTick()
      document.querySelector(route.hash)?.scrollIntoView({ block: 'start' })
    }
  } catch (e) {
    error.value = e.message
  }
}
watch(period, load, { deep: true, immediate: true })
const s = computed(() => data.value)

const PREV_NAME = { month: '전월', quarter: '전분기', year: '전년' }
const REASON = { 'no-current-data': '-', 'no-data': '비교 없음', 'zero-base': '비교값 0' }
const change = (c) => (!c || c.rate === null ? REASON[c?.reason] ?? '-' : `${c.rate > 0 ? '▲' : c.rate < 0 ? '▼' : ''}${Math.abs(c.rate).toFixed(1)}%`)
const changeCls = (c) => (c?.rate > 0 ? 'text-success' : c?.rate < 0 ? 'text-danger' : 'text-muted')
const COST_CLASS = { fixed: '고정비', variable: '변동비' }
const BEP_BASIS = { settings: '적용 기준', category: '항목 설정', unclassified: '미분류 → 고정비' }
const BEP_REASON = {
  'no-data': '이 기간에 확정된 데이터가 없어 계산하지 않았습니다.',
  'no-revenue': '매출이 0원이라 손익분기점을 계산할 수 없습니다.',
  'no-fixed-cost': '고정비가 0원이라 손익분기점이 없습니다 (매출이 모두 공헌이익).',
  'not-reachable': '공헌이익(매출 − 변동비)이 0 이하라 매출이 늘어도 손익분기점에 도달하지 않습니다.',
}
const AR_LABEL = { long_overdue: '장기 미수금', scheduled: '당월 수금예정' }
</script>

<template>
  <div>
    <PeriodSelector />
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="!s" class="text-muted">불러오는 중…</div>
    <template v-else>
      <p class="small text-muted">{{ s.period.label }} · 확정된 달만 집계 (확정 {{ s.confirmation.confirmed_months.length }}개월 / {{ s.period.months.length }}개월) · 간이 지표는 회계상 값과 다를 수 있습니다</p>

      <!-- ① 매출 구성 · 이익 계산 -->
      <div class="row g-3 mb-3">
        <div class="col-xl-6"><div class="card h-100"><div class="card-body">
          <h3 class="h6">매출 구성</h3>
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light"><tr class="text-nowrap"><th>항목</th><th class="text-end">금액(원)</th><th class="text-end">비율</th><th class="text-end">{{ PREV_NAME[s.period.kind] }} 대비</th><th v-if="s.changes.last_year" class="text-end">전년 동기 대비</th></tr></thead>
            <tbody>
              <tr v-for="i in s.revenue.items" :key="i.key">
                <td>{{ i.label }} 매출</td><td class="text-end">{{ i.amount.toLocaleString() }}</td><td class="text-end">{{ pctText(i.ratio) }}</td>
                <td class="text-end" :class="changeCls(s.changes.previous.revenue_items[i.key])">{{ change(s.changes.previous.revenue_items[i.key]) }}</td>
                <td v-if="s.changes.last_year" class="text-end" :class="changeCls(s.changes.last_year.revenue_items[i.key])">{{ change(s.changes.last_year.revenue_items[i.key]) }}</td>
              </tr>
              <tr class="fw-semibold"><td>합계 (총매출)</td><td class="text-end">{{ s.revenue.total.toLocaleString() }}</td><td></td>
                <td class="text-end">{{ change(s.changes.previous.revenue) }}</td><td v-if="s.changes.last_year" class="text-end">{{ change(s.changes.last_year.revenue) }}</td></tr>
            </tbody>
          </table>
        </div></div></div>
        <div class="col-xl-6"><div class="card h-100"><div class="card-body">
          <h3 class="h6">이익 계산 <span class="badge badge-soft">간이 지표</span></h3>
          <table class="table table-sm align-middle mb-1">
            <tbody>
              <tr><td>총매출</td><td class="text-end">{{ s.revenue.total.toLocaleString() }}</td></tr>
              <tr v-for="i in s.costs.items" :key="i.key"><td>(−) {{ i.label }}</td><td class="text-end">−{{ i.amount.toLocaleString() }}</td></tr>
              <tr><td>비용 합계 (매입·지출)</td><td class="text-end">−{{ s.costs.total.toLocaleString() }}</td></tr>
              <tr class="fw-semibold" :class="{ 'text-danger': s.profit.amount < 0 }"><td>간이 이익</td><td class="text-end">{{ s.profit.amount.toLocaleString() }}</td></tr>
              <tr><td>간이 이익률 (이익 ÷ 총매출)</td><td class="text-end">{{ pctText(s.profit.margin) }}</td></tr>
            </tbody>
          </table>
          <p class="small text-muted mb-0">적용 기준: 상품·원재료 매입액을 그달의 원가로 봅니다 · 공급가액(부가세 제외)</p>
        </div></div></div>
      </div>

      <!-- ② 분기별 목표 · 지출 항목 -->
      <div class="row g-3 mb-3">
        <div class="col-xl-6"><div class="card h-100"><div class="card-body">
          <h3 class="h6">{{ s.period.year }}년 분기별 목표</h3>
          <p v-if="!s.targets" class="text-muted small mb-0">{{ s.period.year }}년 목표가 설정되지 않았습니다. <RouterLink to="/management/settings">목표·항목 설정 →</RouterLink></p>
          <template v-else>
            <table class="table table-sm align-middle mb-1">
              <thead class="table-light"><tr><th>분기</th><th class="text-end">목표(원)</th><th>구분</th><th class="text-end">확정 실적(원)</th><th class="text-end">달성률</th></tr></thead>
              <tbody>
                <tr v-for="q in s.targets.quarters" :key="q.quarter" :class="{ 'text-danger': q.warn }">
                  <td>{{ q.quarter }}분기</td><td class="text-end">{{ q.target.toLocaleString() }}</td>
                  <td class="small">{{ q.source === 'input' ? '직접 입력' : '자동 배분' }}</td>
                  <!-- 확정된 달이 없으면 0.0% 대신 사실만 (대시보드·엑셀과 같은 문장) -->
                  <td v-if="q.no_confirmed_text" colspan="2" class="text-end small text-muted">{{ q.no_confirmed_text }}</td>
                  <template v-else>
                    <td class="text-end">{{ q.state === 'future' ? '-' : q.actual.toLocaleString() }}</td>
                    <td class="text-end">{{ q.state === 'future' ? '-' : pctText(q.rate) }}<span v-if="q.unconfirmed_months.length" class="badge badge-soft ms-1">{{ q.unconfirmed_months.join('·') }}월 미확정</span></td>
                  </template>
                </tr>
                <tr class="fw-semibold"><td>합계</td><td class="text-end">{{ s.targets.quarters.reduce((a, q) => a + q.target, 0).toLocaleString() }}</td><td></td>
                  <td class="text-end">{{ s.targets.annual.actual.toLocaleString() }}</td><td class="text-end">{{ pctText(s.targets.annual.rate) }}</td></tr>
              </tbody>
            </table>
            <p class="small text-muted mb-0">
              연간 경과율 {{ pctText(s.targets.annual.elapsed) }} ({{ s.targets.annual.basis_month }}월까지 확정 기준) ·
              진도 대비 {{ s.targets.annual.gap > 0 ? '▲' : s.targets.annual.gap < 0 ? '▼' : '' }}{{ Math.abs(s.targets.annual.gap).toFixed(1) }}%p
              <template v-if="s.targets.annual.excluded_months.length"> · {{ s.targets.annual.excluded_months.join('·') }}월은 미확정이라 진도 비교에서 제외</template>
            </p>
          </template>
        </div></div></div>
        <div class="col-xl-6"><div class="card h-100"><div class="card-body">
          <h3 class="h6">지출 항목</h3>
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light"><tr class="text-nowrap"><th>항목</th><th class="text-end">금액(원)</th><th class="text-end">비율</th><th class="text-end">{{ PREV_NAME[s.period.kind] }} 대비</th></tr></thead>
            <tbody>
              <template v-for="i in s.costs.items" :key="i.key">
                <tr><td>{{ i.label }}<template v-if="i.key === 'other_expense'"> ({{ s.costs.other_items.length }}개 항목)</template></td>
                  <td class="text-end">{{ i.amount.toLocaleString() }}</td><td class="text-end">{{ pctText(i.ratio) }}</td>
                  <td class="text-end" :class="changeCls(s.changes.previous.cost_items[i.key])">{{ change(s.changes.previous.cost_items[i.key]) }}</td></tr>
                <template v-if="i.key === 'other_expense'">
                  <tr v-for="o in s.costs.other_items" :key="o.key" class="small text-muted"><td class="ps-4">└ {{ o.label }}</td><td class="text-end">{{ o.amount.toLocaleString() }}</td><td class="text-end">{{ pctText(o.ratio) }}</td><td></td></tr>
                </template>
              </template>
              <tr class="fw-semibold"><td>합계</td><td class="text-end">{{ s.costs.total.toLocaleString() }}</td><td></td><td class="text-end">{{ change(s.changes.previous.costs) }}</td></tr>
            </tbody>
          </table>
        </div></div></div>
      </div>

      <!-- ③ 손익분기점 · 인당 생산성 -->
      <div id="break-even" class="row g-3 mb-3">
        <div class="col-xl-8"><div class="card h-100"><div class="card-body">
          <h3 class="h6">{{ s.period.label }} 손익분기점(BEP) 달성률 <span class="badge badge-soft">간이 지표</span></h3>
          <p v-if="s.break_even.reason" class="small mb-2" :class="s.break_even.reason === 'not-reachable' ? 'text-danger' : 'text-muted'">{{ BEP_REASON[s.break_even.reason] }}</p>
          <div v-else class="d-flex flex-wrap align-items-baseline gap-3 mb-2">
            <span class="fs-3 fw-bold" :class="s.break_even.rate < 100 ? 'text-danger' : ''">{{ pctText(s.break_even.rate) }}</span>
            <span class="small">BEP 매출 {{ won(s.break_even.bep_revenue) }} · 실제 매출 {{ won(s.break_even.revenue) }} ·
              <strong>{{ s.break_even.gap >= 0 ? `BEP 초과 ${won(s.break_even.gap)} — 흑자` : `BEP까지 남은 매출 ${won(-s.break_even.gap)}` }}</strong></span>
          </div>
          <table class="table table-sm align-middle mb-1">
            <thead class="table-light"><tr><th>항목</th><th>구분</th><th class="text-end">금액(원)</th><th>분류 근거</th></tr></thead>
            <tbody>
              <tr v-for="i in s.break_even.items" :key="i.key"><td>{{ i.label }}</td><td>{{ COST_CLASS[i.cost_class] }}</td><td class="text-end">{{ i.amount.toLocaleString() }}</td><td class="small text-muted">{{ BEP_BASIS[i.basis] }}</td></tr>
              <tr class="fw-semibold"><td>변동비 합계</td><td></td><td class="text-end">{{ s.break_even.variable_cost.toLocaleString() }}</td><td></td></tr>
              <tr class="fw-semibold"><td>고정비 합계</td><td></td><td class="text-end">{{ s.break_even.fixed_cost.toLocaleString() }}</td><td></td></tr>
            </tbody>
          </table>
          <ul v-if="!s.break_even.reason" class="small text-muted mb-1">
            <li>공헌이익 = 매출 − 변동비 = {{ won(s.break_even.contribution) }} (공헌이익률 {{ pctText(s.break_even.contribution_ratio) }})</li>
            <li>BEP 매출 = 고정비 × 매출 ÷ 공헌이익 = {{ won(s.break_even.bep_revenue) }} (원 단위 올림)</li>
            <li>달성률 = 공헌이익 ÷ 고정비 = 실제 매출 ÷ BEP 매출</li>
          </ul>
          <p v-if="s.break_even.unclassified_count" class="small text-warn mb-1">미분류 {{ s.break_even.unclassified_count }}개 항목은 고정비로 계산했습니다. <RouterLink :to="{ path: '/management/settings', query: { tab: 'categories' } }">목표·항목 설정</RouterLink>에서 고정비/변동비를 고르면 반영됩니다.</p>
          <details class="small"><summary>계산 기준</summary><ul class="mb-0 mt-1"><li v-for="b in s.break_even.applied_basis" :key="b">{{ b }}</li></ul></details>
        </div></div></div>
        <div class="col-xl-4"><div class="card h-100"><div class="card-body">
          <h3 class="h6">{{ s.period.label }} 인당 생산성</h3>
          <p v-if="s.productivity.reason === 'no-headcount'" class="small text-muted">{{ s.period.year }}년 직원 수가 없습니다. <RouterLink to="/management/settings">목표·항목 설정에서 입력 →</RouterLink></p>
          <p v-else-if="s.productivity.reason === 'no-data'" class="small text-muted">이 기간에 확정된 달이 없습니다.</p>
          <template v-else>
            <table class="table table-sm mb-1">
              <thead class="table-light"><tr><th>항목</th><th class="text-end">합계(원)</th><th class="text-end">1인당(원)</th></tr></thead>
              <tbody>
                <tr><td>매출</td><td class="text-end">{{ s.revenue.total.toLocaleString() }}</td><td class="text-end">{{ s.productivity.revenue_per_head.toLocaleString() }}</td></tr>
                <tr><td>간이 이익</td><td class="text-end">{{ s.profit.amount.toLocaleString() }}</td><td class="text-end">{{ s.productivity.profit_per_head.toLocaleString() }}</td></tr>
              </tbody>
            </table>
            <p class="small text-muted mb-0">직원 {{ s.productivity.headcount }}명 기준 (목표·항목 설정) · 확정된 달 합계 ÷ 직원 수 · 1인당 금액은 원 단위 반올림</p>
          </template>
        </div></div></div>
      </div>

      <!-- ④ 매출 구성 월별 추이 -->
      <div class="mb-3"><RevenueMixChart :points="s.trend" /></div>

      <!-- ⑤ 미수금 상세 -->
      <div id="receivables" class="card mb-3"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <h3 class="h6 mb-0">미수금<template v-if="s.receivables.month"> · {{ s.receivables.month.year }}년 {{ s.receivables.month.month }}월 경영지원 관리 외상매출금 기준</template></h3>
          <RouterLink to="/management/ledger" class="small ms-auto">경영지원 관리 →</RouterLink>
          <RouterLink to="/management/receivables" class="small">미수금 건별 기록 →</RouterLink>
        </div>
        <p v-if="!s.receivables.month" class="text-muted small mb-0">이 기간에 경영지원 관리의 외상매출금 입력이 없습니다.</p>
        <template v-else>
          <div class="row g-3">
            <div class="col-lg-4">
              <div class="small fw-semibold mb-1">상태별</div>
              <table class="table table-sm mb-0">
                <tbody>
                  <tr class="text-danger"><td>장기 미수금</td><td class="text-end">{{ s.receivables.long_overdue.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.long_overdue.count }}건</td></tr>
                  <tr><td>당월 수금예정</td><td class="text-end">{{ s.receivables.scheduled.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.scheduled.count }}건</td></tr>
                  <tr class="fw-semibold"><td>미수금 합계</td><td class="text-end">{{ s.receivables.total.toLocaleString() }}</td><td class="text-end">{{ s.receivables.count }}건</td></tr>
                  <tr class="text-muted small"><td>당월 수금 (미수금 아님)</td><td class="text-end">{{ s.receivables.collected.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.collected.count }}건</td></tr>
                </tbody>
              </table>
            </div>
            <div class="col-lg-4">
              <div class="small fw-semibold mb-1">거래처별</div>
              <table class="table table-sm mb-0">
                <tbody>
                  <tr v-for="(c, i) in s.receivables.by_customer" :key="c.customer_name"><td class="text-muted">{{ i + 1 }}</td><td>{{ c.customer_name }}</td>
                    <td class="text-end">{{ c.amount.toLocaleString() }}</td><td class="text-end">{{ pctText(s.receivables.total ? (c.amount / s.receivables.total) * 100 : null) }}</td></tr>
                </tbody>
              </table>
            </div>
            <div class="col-lg-4">
              <div class="small fw-semibold mb-1">수금 예정 (당월 수금예정 행의 예정일)</div>
              <table class="table table-sm mb-0">
                <tbody>
                  <tr :class="{ 'text-warn': s.receivables.expected.overdue.count }"><td>예정일 지남</td><td class="text-end">{{ s.receivables.expected.overdue.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.expected.overdue.count }}건</td></tr>
                  <tr v-for="m in s.receivables.expected.months" :key="`${m.year}-${m.month}`"><td>{{ m.year }}년 {{ m.month }}월</td><td class="text-end">{{ m.amount.toLocaleString() }}</td><td class="text-end">{{ m.count }}건</td></tr>
                  <tr><td>그 이후</td><td class="text-end">{{ s.receivables.expected.later.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.expected.later.count }}건</td></tr>
                  <tr><td>예정일 없음</td><td class="text-end">{{ s.receivables.expected.no_due_date.amount.toLocaleString() }}</td><td class="text-end">{{ s.receivables.expected.no_due_date.count }}건</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <details class="small mt-2">
            <summary>미수 행 전체 ({{ s.receivables.items.length }}건, 금액 큰 순)</summary>
            <table class="table table-sm mb-0 mt-1">
              <thead class="table-light"><tr><th>거래처</th><th>구분</th><th class="text-end">금액(원)</th><th>수금 예정일</th><th>적요</th></tr></thead>
              <tbody>
                <tr v-for="(i, k) in s.receivables.items" :key="k" :class="{ 'text-danger': i.status === 'long_overdue' }">
                  <td>{{ i.customer_name }}</td><td>{{ AR_LABEL[i.status] }}</td><td class="text-end">{{ i.amount.toLocaleString() }}</td>
                  <td>{{ i.due_on ?? '-' }}<span v-if="i.overdue" class="badge badge-warn ms-1">지남</span></td><td>{{ i.note }}</td>
                </tr>
              </tbody>
            </table>
          </details>
        </template>
      </div></div>

      <!-- ⑥ 자금 수지 예측 (오늘 기준) -->
      <div id="cash-forecast"><CashForecast :forecast="s.cash_forecast" /></div>
    </template>
  </div>
</template>

<style scoped>
/* 대시보드 링크로 이동했을 때 위쪽 고정 헤더에 제목이 가리지 않게 */
#break-even,
#receivables,
#cash-forecast {
  scroll-margin-top: calc(var(--header-h) + 16px);
}
</style>
