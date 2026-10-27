<script setup>
// 당월 납기 캘린더: 날짜 칸에 수주번호(PO)별 납기 대수 표시, 날짜를 누르면 상세
// 라이브러리 없이 Bootstrap 표로 만든다 (specs/01-architecture.md 결정)
// 처리 상태(출고일 기준)를 색·기호로 구분: 앞으로 처리할 건은 진하게, 출고 완료 건은 흐리게
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getDueCalendar } from '@/api/production'
import { DUE_STATUS, DUE_STATUS_ORDER, statusKey } from '@/dueStatus'

const route = useRoute()
const today = new Date()
// 대시보드 '납기 임박'에서 날짜를 누르고 들어오면 그 달·날짜를 바로 연다
const year = ref(Number(route.query.year) || today.getFullYear())
const month = ref(Number(route.query.month) || today.getMonth() + 1)
const days = ref({}) // 'YYYY-MM-DD' → orders
const selected = ref(null)
const error = ref('')
const hideDone = ref(false) // 출고 완료 건 숨기기
let openDate = route.query.date || null

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
    // 칸 안에서는 처리할 건(납기 지남 → 출고 전 → 일부 출고)을 먼저, 출고 완료를 나중에
    const rank = (o) => DUE_STATUS_ORDER.indexOf(statusKey(o))
    days.value = Object.fromEntries(data.days.map((d) => [d.date, [...d.orders].sort((a, b) => rank(a) - rank(b))]))
    if (openDate && days.value[openDate]) selected.value = openDate
    openDate = null
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
// 상태별 수주 건수 (범례에 함께 표시)
const counts = computed(() => {
  const c = Object.fromEntries(DUE_STATUS_ORDER.map((k) => [k, 0]))
  for (const o of Object.values(days.value).flat()) c[statusKey(o)] += 1
  return c
})
const shown = (key) => (days.value[key] || []).filter((o) => !hideDone.value || o.status !== 'done')
const meta = (o) => DUE_STATUS[statusKey(o)]

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
      <!-- 범례: 상태별 색·기호와 이달 건수 -->
      <div class="d-flex flex-wrap align-items-center gap-2 small mb-2">
        <span v-for="k in DUE_STATUS_ORDER" :key="k" class="badge" :class="DUE_STATUS[k].cls">
          {{ DUE_STATUS[k].icon }} {{ DUE_STATUS[k].label }} {{ counts[k] }}건
        </span>
        <div class="form-check form-switch ms-auto mb-0">
          <input id="hide-done" v-model="hideDone" class="form-check-input" type="checkbox" />
          <label class="form-check-label" for="hide-done">출고 완료 건 숨기기</label>
        </div>
      </div>
      <p class="text-muted small mb-2">처리 상태는 제조내역의 출고일로 판단합니다. 모든 대수에 출고일이 있으면 출고 완료입니다.</p>
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
                <template v-if="shown(dateKey(d)).length">
                  <div
                    v-for="o in shown(dateKey(d)).slice(0, MAX_BADGES)"
                    :key="o.po_no"
                    class="badge d-block text-start text-truncate mb-1"
                    :class="meta(o).cls"
                    :title="`${orderLabel(o)} ${o.quantity}대 — ${meta(o).label} (출고 ${o.shipped}/${o.quantity})`"
                  >
                    {{ meta(o).icon }} {{ orderLabel(o) }} ×{{ o.quantity }}
                  </div>
                  <div v-if="shown(dateKey(d)).length > MAX_BADGES" class="text-muted">
                    +{{ shown(dateKey(d)).length - MAX_BADGES }}건
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
            <tr><th>상태</th><th>수주번호</th><th>판매처</th><th>사업명</th><th>출고 / 대수</th><th>일련번호</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in days[selected]" :key="o.po_no" :class="{ 'text-muted': o.status === 'done' }">
              <td class="text-nowrap"><span class="badge" :class="meta(o).cls">{{ meta(o).icon }} {{ meta(o).label }}</span></td>
              <td class="text-nowrap">{{ orderLabel(o) }}</td>
              <td>{{ o.customers.join(', ') || '-' }}</td>
              <td>{{ o.projects.join(', ') || '-' }}</td>
              <td class="text-end text-nowrap">{{ o.shipped }} / {{ o.quantity }}</td>
              <td>{{ o.serials.join(', ') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="text-muted small mb-0">납기가 있는 날짜를 누르면 수주번호·판매처·사업명을 볼 수 있습니다.</p>
    </div>
  </div>
</template>
