<script setup>
// 3~6개월 자금 수지 예측 (조원 저장소 cash-forecast-section 을 옮김) — 오늘 기준, 위에서 고른 기간과 무관
// 막대: 수입·지출을 예정(진한 색) + 추정(흐린 색)으로 쌓음. 표: 월별 예정·추정·순수지·누적·예상 잔액. 3개월 / 6개월 전환
// 예측값은 실제값과 구분해 "예측"으로 표시한다 (CLAUDE.md 6절)
import { computed, ref } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, SERIES_COLORS } from '@/charts'
import { won, wonShort } from '@/money'

const props = defineProps({ forecast: { type: Object, required: true } })
const count = ref(3)
const INFLOW = SERIES_COLORS[0]
const OUTFLOW = SERIES_COLORS[1]
const f = computed(() => props.forecast)
const months = computed(() => f.value.months.slice(0, count.value))
const label = (m) => `${m.month}월`

const data = computed(() => ({
  labels: months.value.map(label),
  datasets: [
    { label: '수입 예정', key: 'inflow_planned', color: INFLOW, stack: 'in' },
    { label: '수입 추정', key: 'inflow_estimated', color: `${INFLOW}66`, stack: 'in' },
    { label: '지출 예정', key: 'outflow_planned', color: OUTFLOW, stack: 'out' },
    { label: '지출 추정', key: 'outflow_estimated', color: `${OUTFLOW}66`, stack: 'out' },
  ].map((d) => ({
    label: d.label,
    data: months.value.map((m) => m[d.key] ?? 0),
    backgroundColor: d.color,
    borderColor: '#ffffff',
    borderWidth: { top: 2 },
    stack: d.stack,
    maxBarThickness: 28,
  })),
}))
const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${won(ctx.raw)}` } } },
  scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: GRID_COLOR }, ticks: { callback: (v) => wonShort(v) } } },
}
// 예상 잔액이 0보다 작아지는 첫 달
const firstShort = computed(() => months.value.find((m) => m.balance !== null && m.balance < 0))
const ym = (x) => `${x.year}년 ${x.month}월`
const notes = computed(() => {
  const n = f.value.notes
  const lines = []
  if (n.carried_inflow.count) lines.push(`수금 예정일이 없거나 지난 ${n.carried_inflow.count}건(${won(n.carried_inflow.amount)})은 첫 달에 넣었습니다.`)
  if (n.long_overdue.count) lines.push(`장기 미수금 ${n.long_overdue.count}건(${won(n.long_overdue.amount)})은 들어올 돈에 넣지 않았습니다.`)
  if (n.past_outflow.count) lines.push(`지급 예정 달이 이미 지난 ${n.past_outflow.count}건(${won(n.past_outflow.amount)})은 이미 나간 돈으로 봤습니다.`)
  if (n.beyond_inflow.count || n.beyond_outflow.count) lines.push(`6개월 뒤로 예정된 돈은 빠져 있습니다 (들어올 ${won(n.beyond_inflow.amount)} · 나갈 ${won(n.beyond_outflow.amount)}).`)
  const o = f.value.opening
  lines.push(o
    ? `예상 잔액은 ${ym(o)} 말 통장 잔액 기준입니다.${o.gap_months ? ` 그 뒤 ${o.gap_months}개월(이번 달까지)의 입출금은 반영되지 않았습니다.` : ''}`
    : "월간 입력에 '월말 통장 잔액'을 넣으면 예상 잔액까지 보여 드립니다.")
  return lines
})
</script>

<template>
  <div class="card"><div class="card-body">
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <h3 class="h6 mb-0">{{ count }}개월 자금 수지 예측 <span class="badge badge-warn">예측</span></h3>
      <div class="btn-group btn-group-sm ms-auto" role="group" aria-label="예측 기간">
        <button v-for="n in [3, 6]" :key="n" type="button" class="btn" :class="count === n ? 'btn-secondary' : 'btn-outline-secondary'" @click="count = n">{{ n }}개월</button>
      </div>
    </div>
    <p class="small text-muted mb-2">
      {{ f.as_of }} 기준 · {{ f.ledger_month ? `경영지원 관리 ${ym(f.ledger_month)}` : '경영지원 관리 입력 없음' }} ·
      {{ f.average ? `추정 = 확정 ${f.average.months.map((m) => `${m.month}월`).join('·')} 평균` : '확정된 달이 없어 추정하지 않음' }}
    </p>
    <div v-if="firstShort" class="alert alert-danger py-2 small">{{ firstShort.month }}월 말 예상 잔액이 {{ won(firstShort.balance) }}으로 부족해질 수 있습니다.</div>
    <div class="d-flex flex-wrap gap-3 small mb-1">
      <span><span class="swatch" :style="{ background: INFLOW }"></span>수입 예정</span>
      <span><span class="swatch" :style="{ background: `${INFLOW}66` }"></span>수입 추정</span>
      <span><span class="swatch" :style="{ background: OUTFLOW }"></span>지출 예정</span>
      <span><span class="swatch" :style="{ background: `${OUTFLOW}66` }"></span>지출 추정</span>
    </div>
    <div style="height: 220px"><Bar :data="data" :options="options" /></div>
    <div class="table-responsive mt-2">
      <table class="table table-sm small mb-1">
        <thead class="table-light"><tr class="text-nowrap"><th>월</th><th class="text-end">수금 예정</th><th class="text-end">수금 추정</th><th class="text-end">지급 예정</th><th class="text-end">지출 추정</th><th class="text-end">순수지</th><th class="text-end">누적</th><th class="text-end">예상 잔액</th></tr></thead>
        <tbody>
          <tr v-for="m in months" :key="`${m.year}-${m.month}`">
            <td class="text-nowrap">{{ ym(m) }}</td>
            <td class="text-end">{{ m.inflow_planned.toLocaleString() }}</td>
            <td class="text-end">{{ m.inflow_estimated === null ? '-' : m.inflow_estimated.toLocaleString() }}</td>
            <td class="text-end">{{ m.outflow_planned.toLocaleString() }}</td>
            <td class="text-end">{{ m.outflow_estimated === null ? '-' : m.outflow_estimated.toLocaleString() }}</td>
            <td class="text-end" :class="{ 'text-danger': m.net < 0 }">{{ m.net.toLocaleString() }}</td>
            <td class="text-end" :class="{ 'text-danger': m.cumulative < 0 }">{{ m.cumulative.toLocaleString() }}</td>
            <td class="text-end" :class="{ 'text-danger': m.balance !== null && m.balance < 0 }">{{ m.balance === null ? '-' : m.balance.toLocaleString() }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="small text-muted mb-1">단위: 원 · 부가세 포함 · 추정(-)은 계산하지 않은 달<template v-if="f.opening"> · 시작 잔액 {{ ym(f.opening) }} 말 {{ won(f.opening.amount) }}</template></p>
    <ul class="small text-muted mb-1"><li v-for="n in notes" :key="n">{{ n }}</li></ul>
    <details class="small"><summary>계산 기준</summary><ul class="mb-0 mt-1"><li v-for="b in f.basis" :key="b">{{ b }}</li></ul></details>
  </div></div>
</template>

<style scoped>
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
</style>
