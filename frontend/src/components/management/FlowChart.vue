<script setup>
// 매출·매입·지출 월별 추이 (조원 저장소 flow-chart 를 옮김)
// 위: 매출·매입·지출 합계 막대 / 아래: 간이 이익률 선 — 두 그래프가 같은 가로축(월)을 쓴다 (세로축 2개짜리 그래프는 쓰지 않음)
// 임시저장 달은 흐리게 + 아래에 "미확정", 데이터 없는 달·마감 전 달은 빈칸 (0으로 그리지 않음)
import { computed } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import { GRID_COLOR, SERIES_COLORS } from '@/charts'
import { pctText, won, wonShort } from '@/money'

const props = defineProps({
  points: { type: Array, required: true }, // [{ year, month, status, revenue, costs, profit, margin }]
  highlight: { type: Array, default: () => [] }, // 지금 보고 있는 기간의 달 [{year, month}]
})

const REVENUE = SERIES_COLORS[0]
const COSTS = SERIES_COLORS[1]
const fade = (hex) => `${hex}59` // 35% 불투명 (임시저장 달)
// 두 그래프의 세로축 폭을 같게 → 같은 달이 위아래로 정확히 겹친다
const Y_AXIS_WIDTH = 72
const fixWidth = (axis) => { axis.width = Y_AXIS_WIDTH }
const isDraft = (p) => p.status === 'draft'
const selected = (p) => props.highlight.some((h) => h.year === p.year && h.month === p.month)

const labels = computed(() =>
  props.points.map((p) => {
    const name = p.month === 1 || p === props.points[0] ? `${String(p.year).slice(2)}년 ${p.month}월` : `${p.month}월`
    return isDraft(p) ? [name, '미확정'] : name
  }),
)

// 지금 기간의 달 뒤에 옅은 회색 띠
const band = {
  id: 'periodBand',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const step = scales.x.width / props.points.length
    ctx.save()
    ctx.fillStyle = '#f1f0ec'
    props.points.forEach((p, i) => {
      if (selected(p)) ctx.fillRect(scales.x.left + step * i, chartArea.top, step, chartArea.bottom - chartArea.top)
    })
    ctx.restore()
  },
}

const barData = computed(() => ({
  labels: labels.value,
  datasets: [
    { label: '매출', data: props.points.map((p) => p.revenue), color: REVENUE },
    { label: '매입·지출', data: props.points.map((p) => p.costs), color: COSTS },
  ].map((d) => ({
    label: d.label,
    data: d.data,
    backgroundColor: props.points.map((p) => (isDraft(p) ? fade(d.color) : d.color)),
    borderRadius: { topLeft: 4, topRight: 4 },
    borderSkipped: false,
    maxBarThickness: 22,
    categoryPercentage: 0.7,
    barPercentage: 0.9,
  })),
}))
const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${ctx.raw === null ? '입력 없음' : won(ctx.raw)}`,
        footer: (items) => (isDraft(props.points[items[0].dataIndex]) ? '임시저장 (확정 전 — 합계 제외)' : ''),
      },
    },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true, grid: { color: GRID_COLOR }, ticks: { callback: (v) => wonShort(v) }, afterFit: fixWidth },
  },
}

const lineData = computed(() => ({
  labels: labels.value,
  datasets: [{
    label: '간이 이익률',
    data: props.points.map((p) => p.margin),
    borderColor: '#52514e',
    backgroundColor: '#52514e',
    borderWidth: 2,
    pointRadius: 4,
    pointBackgroundColor: props.points.map((p) => (isDraft(p) ? '#ffffff' : '#52514e')),
    pointBorderColor: '#52514e',
    spanGaps: false,
  }],
}))
const lineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx) => `간이 이익률 ${pctText(ctx.raw)}` } },
  },
  scales: {
    x: { offset: true, grid: { display: false }, ticks: { display: false } }, // 위 막대와 같은 칸 가운데에 점
    y: { grid: { color: GRID_COLOR }, ticks: { callback: (v) => `${v}%` }, afterFit: fixWidth },
  },
}
</script>

<template>
  <div class="card">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
        <h3 class="h6 mb-0">매출·매입·지출 추이 <small class="text-muted fw-normal">(최근 12개월)</small></h3>
        <span class="small"><span class="swatch" :style="{ background: REVENUE }"></span>매출</span>
        <span class="small"><span class="swatch" :style="{ background: COSTS }"></span>매입·지출 합계</span>
        <span class="small text-muted">흐린 막대 = 임시저장(확정 전)</span>
      </div>
      <div style="height: 240px"><Bar :data="barData" :options="barOptions" :plugins="[band]" /></div>
      <div class="small text-muted mt-2">간이 이익률 (빈 점 = 임시저장)</div>
      <div style="height: 110px"><Line :data="lineData" :options="lineOptions" :plugins="[band]" /></div>
      <details class="small mt-2">
        <summary>표로 보기</summary>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead class="table-light"><tr><th>월</th><th>상태</th><th class="text-end">매출</th><th class="text-end">매입·지출</th><th class="text-end">간이 이익</th><th class="text-end">이익률</th></tr></thead>
            <tbody>
              <tr v-for="p in points" :key="`${p.year}-${p.month}`">
                <td>{{ p.year }}-{{ String(p.month).padStart(2, '0') }}</td>
                <td>{{ { confirmed: '확정', draft: '임시저장', missing: '입력 없음', pending: '마감 전' }[p.status] }}</td>
                <td class="text-end">{{ p.revenue === null ? '-' : won(p.revenue) }}</td>
                <td class="text-end">{{ p.costs === null ? '-' : won(p.costs) }}</td>
                <td class="text-end">{{ p.profit === null ? '-' : won(p.profit) }}</td>
                <td class="text-end">{{ pctText(p.margin) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </div>
  </div>
</template>

<style scoped>
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
</style>
