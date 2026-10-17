<script setup>
// 당월 납기 캘린더: 날짜 칸에 수주번호(PO)별 납기 대수 표시, 날짜를 누르면 상세
// 라이브러리 없이 Bootstrap 표로 만든다 (specs/01-architecture.md 결정)
import { computed, ref, watch } from 'vue'
import { getDueCalendar } from '@/api/production'

const today = new Date()
const year = ref(today.getFullYear())
const month = ref(today.getMonth() + 1)
const days = ref({}) // 'YYYY-MM-DD' → orders
const selected = ref(null)
const error = ref('')

const MAX_BADGES = 3 // 칸 하나에 보여줄 수주번호 수 (나머지는 "+n")
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

const pad = (n) => String(n).padStart(2, '0')
const dateKey = (d) => `${year.value}-${pad(month.value)}-${pad(d)}`
const todayKey = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`

// 달력 칸: 첫 주 앞쪽 빈칸 + 1일~말일, 7칸씩 끊어 주 단위로
const weeks = computed(() => {
  const first = new Date(year.value, month.value - 1, 1).getDay()
  const last = new Date(year.value, month.value, 0).getDate()
  const cells = [...Array(first).fill(null), ...Array.from({ length: last }, (_, i) => i + 1)]
  while (cells.length % 7) cells.push(null)
  return Array.from({ length: cells.length / 7 }, (_, w) => cells.slice(w * 7, w * 7 + 7))
})

async function load() {
  error.value = ''
  selected.value = null
  try {
    const data = await getDueCalendar(year.value, month.value)
    days.value = Object.fromEntries(data.days.map((d) => [d.date, d.orders]))
  } catch (e) {
    error.value = e.message
  }
}

function move(step) {
  const d = new Date(year.value, month.value - 1 + step, 1)
  year.value = d.getFullYear()
  month.value = d.getMonth() + 1
}

const orderLabel = (o) => (o.po_no ? `#${o.po_no}` : '수주번호 없음')
const totalUnits = computed(() =>
  Object.values(days.value).flat().reduce((sum, o) => sum + o.quantity, 0),
)

watch([year, month], load, { immediate: true })
</script>

<template>
  <div class="card mb-4">
    <div class="card-body">
      <div class="d-flex align-items-center gap-2 mb-2">
        <h2 class="h6 mb-0 me-2">납기 캘린더</h2>
        <button class="btn btn-outline-secondary btn-sm" aria-label="이전 달" @click="move(-1)">◀</button>
        <strong>{{ year }}년 {{ month }}월</strong>
        <button class="btn btn-outline-secondary btn-sm" aria-label="다음 달" @click="move(1)">▶</button>
        <span class="text-muted small ms-2">납기 {{ totalUnits }}대</span>
      </div>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

      <table class="table table-bordered table-sm small mb-2" style="table-layout: fixed">
        <thead class="table-light">
          <tr>
            <th v-for="(w, i) in WEEKDAYS" :key="w" class="text-center" :class="{ 'text-danger': i === 0, 'text-primary': i === 6 }">{{ w }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(week, wi) in weeks" :key="wi">
            <td
              v-for="(d, di) in week"
              :key="di"
              style="height: 5.5rem; vertical-align: top"
              :class="{
                'bg-light': !d,
                'table-primary': d && selected === dateKey(d),
              }"
              :role="d && days[dateKey(d)] ? 'button' : null"
              @click="d && days[dateKey(d)] && (selected = dateKey(d))"
            >
              <template v-if="d">
                <div :class="{ 'fw-bold text-decoration-underline': dateKey(d) === todayKey }">{{ d }}</div>
                <template v-if="days[dateKey(d)]">
                  <div
                    v-for="o in days[dateKey(d)].slice(0, MAX_BADGES)"
                    :key="o.po_no"
                    class="badge bg-primary d-block text-start text-truncate mb-1"
                  >
                    {{ orderLabel(o) }} ×{{ o.quantity }}
                  </div>
                  <div v-if="days[dateKey(d)].length > MAX_BADGES" class="text-muted">
                    +{{ days[dateKey(d)].length - MAX_BADGES }}건
                  </div>
                </template>
              </template>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="selected">
        <h3 class="h6">{{ selected }} 납기</h3>
        <table class="table table-sm table-bordered small mb-0">
          <thead class="table-light">
            <tr><th>수주번호</th><th>판매처</th><th>사업명</th><th>대수</th><th>일련번호</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in days[selected]" :key="o.po_no">
              <td class="text-nowrap">{{ orderLabel(o) }}</td>
              <td>{{ o.customers.join(', ') || '-' }}</td>
              <td>{{ o.projects.join(', ') || '-' }}</td>
              <td class="text-end">{{ o.quantity }}</td>
              <td>{{ o.serials.join(', ') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="text-muted small mb-0">납기가 있는 날짜를 누르면 수주번호·판매처·사업명을 볼 수 있습니다.</p>
    </div>
  </div>
</template>
