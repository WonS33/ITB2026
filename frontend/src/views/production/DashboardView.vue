<script setup>
// 생산팀 대시보드: 납기 임박(오늘 기준) + 생산 실적(목표 대비·비교) + 납기·출고 + 판매 실적
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PeriodSelector from '@/components/PeriodSelector.vue'
import DueSoon from '@/components/production/DueSoon.vue'
import DeliveryStatus from '@/components/production/DeliveryStatus.vue'
import SalesSection from '@/components/production/SalesSection.vue'
import AchievementRing from '@/components/production/AchievementRing.vue'
import ProductionBars from '@/components/production/ProductionBars.vue'
import YearProgress from '@/components/production/YearProgress.vue'
import TargetForm from '@/components/production/TargetForm.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import { OTHER_COLOR, SERIES_COLORS } from '@/charts'
import { period } from '@/period'
import { getDashboard } from '@/api/production'

const data = ref(null)
const error = ref('')

// 비교 기간 (판매 실적과 같은 규칙) + 겹쳐 보기 — 고른 값은 이 브라우저에 기억 (개인 편의용)
const COMPARES = [
  { value: 'none', label: '비교 안 함' },
  { value: 'previous', label: '직전 기간' },
  { value: 'last_year', label: '전년 동기' },
]
const STORAGE_KEY = 'production.dashboard.view'
function loadView() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return {
      compare: COMPARES.some((c) => c.value === saved.compare) ? saved.compare : 'none',
      showOrders: saved.showOrders !== false, // 처음에는 수주량 선을 보여 줌
    }
  } catch {
    return { compare: 'none', showOrders: true }
  }
}
const view = ref(loadView())
watch(
  view,
  () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(view.value))
    } catch {
      // 저장이 막힌 브라우저에서도 화면은 그대로 동작
    }
  },
  { deep: true },
)

async function load() {
  error.value = ''
  try {
    data.value = await getDashboard(period, view.value.compare)
  } catch (e) {
    error.value = e.message
  }
}

// 모델 색: 전체 모델명 목록(가나다순)의 순서로 고정 → 기간이 바뀌어도 같은 모델은 같은 색
function modelColor(name) {
  const i = data.value?.model_names.indexOf(name) ?? -1
  return i === -1 || i >= SERIES_COLORS.length ? OTHER_COLOR : SERIES_COLORS[i]
}
// 생산량 막대: 월별(1~12월) / 분기별(1~4분기) 전환
// 분기 목표 = 연간 목표 ÷ 4 (= 연간 ÷ 12 × 3, 당월·분기 목표와 같은 임시 기준)
const BAR_UNITS = [
  { value: 'month', label: '월별' },
  { value: 'quarter', label: '분기별' },
]
const barUnit = ref('month')
const bars = computed(() => {
  const months = data.value.monthly.months
  const selected = data.value.period.months
  // 진행 중: 올해의 이번 달 / 이번 분기
  const now = new Date()
  const thisYear = Number(data.value.period.start.slice(0, 4)) === now.getFullYear()
  const thisMonth = now.getMonth() + 1
  if (barUnit.value === 'month') {
    return months.map((m) => ({
      value: m.month,
      label: `${m.month}월`,
      actual: m.actual,
      orders: m.orders,
      lastYear: m.last_year,
      selected: selected.includes(m.month),
      inProgress: thisYear && m.month === thisMonth,
    }))
  }
  return [1, 2, 3, 4].map((q) => {
    const qMonths = [q * 3 - 2, q * 3 - 1, q * 3]
    const sum = (key) => months.filter((m) => qMonths.includes(m.month)).reduce((total, m) => total + (m[key] ?? 0), 0)
    return {
      value: q,
      label: `${q}분기`,
      actual: sum('actual'),
      orders: sum('orders'),
      lastYear: sum('last_year'),
      selected: qMonths.some((m) => selected.includes(m)),
      inProgress: thisYear && qMonths.includes(thisMonth),
    }
  })
})
const barTarget = computed(() => {
  if (barUnit.value === 'month') return data.value.monthly.monthly_target
  const annual = data.value.production.annual_target
  return annual ? Math.round((annual / 4) * 10) / 10 : null
})
const barTargetName = computed(() => (barUnit.value === 'month' ? '월 목표' : '분기 목표'))

// 숫자의 근거 보기: 월 막대 → 그 달 제조내역, 분기 막대 → 그 분기 제조내역, 모델 → 그 모델로 걸러진 제조내역 (기간 선택은 화면 전체가 같이 씀)
const router = useRouter()
function openMonth(month) {
  Object.assign(period, { kind: 'month', month })
  router.push('/production/records')
}
function openQuarter(quarter) {
  Object.assign(period, { kind: 'quarter', quarter })
  router.push('/production/records')
}
const openBar = (value) => (barUnit.value === 'month' ? openMonth(value) : openQuarter(value))
const openModel = (model) => router.push({ path: '/production/records', query: { model } })

const total = (items) => items.reduce((sum, i) => sum + i.quantity, 0)

const showLastYear = computed(() => view.value.compare !== 'none')
// 선택한 기간에 오늘이 들어 있으면 아직 진행 중 → 끝난 비교 기간보다 낮게 나오는 것이 당연함을 알린다
const periodInProgress = computed(() => {
  const d = new Date() // 한국 시간 기준 날짜 (toISOString은 UTC라 새벽에 하루 전 날짜가 됨)
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return data.value.period.start <= today && today <= data.value.period.end
})
const signed = (n) => (n > 0 ? `▲ ${n}` : n < 0 ? `▼ ${-n}` : '변동 없음')

// 기간·비교 기간을 바꾸면 다시 불러온다
watch([period, () => view.value.compare], load, { deep: true, immediate: true })
</script>

<template>
  <div>
    <!-- 납기 임박은 기간 선택과 관계없이 오늘 기준이라 기간 선택보다 위에 둔다 -->
    <DueSoon />
    <PeriodSelector />

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <!-- 생산 실적: 생산량·기간 목표·달성률·부족치를 한 카드에서 (달성률 도넛 + 세부 수치) -->
      <div class="card mb-4"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <h3 class="h6 mb-0">{{ data.period.label }} 생산 실적</h3>
          <div class="d-flex flex-wrap align-items-center gap-3">
            <label class="d-flex align-items-center gap-1 small">
              <span class="text-muted text-nowrap">비교</span>
              <select v-model="view.compare" class="form-select form-select-sm w-auto">
                <option v-for="c in COMPARES" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </label>
            <!-- 연간 목표: 모두 볼 수 있고, 수정 권한자에게만 [목표 수정] 버튼이 보인다 -->
            <TargetForm :year="period.year" @saved="load" />
          </div>
        </div>
        <div class="row g-4 align-items-center">
          <div class="col-xl-5">
            <AchievementRing :production="data.production" />
            <!-- 비교 기간 대비 생산량 (증감은 ▲▼ 기호와 숫자로) -->
            <p v-if="data.compare" class="small mt-3 mb-0">
              {{ data.compare.label }} {{ data.compare.actual.toLocaleString() }}대 대비
              <strong>{{ signed(data.compare.change) }}대</strong>
              <span v-if="data.compare.change_rate !== null" class="text-muted">
                ({{ data.compare.change_rate > 0 ? '+' : '' }}{{ data.compare.change_rate }}%)
              </span>
              <span v-if="periodInProgress" class="d-block text-muted">이번 기간은 아직 진행 중이라 끝난 기간보다 적게 보일 수 있습니다.</span>
            </p>
          </div>
          <div class="col-xl-7">
            <div class="d-flex flex-wrap align-items-center gap-3 small mb-1">
              <div class="btn-group btn-group-sm" role="group" aria-label="막대 단위">
                <button
                  v-for="u in BAR_UNITS"
                  :key="u.value"
                  type="button"
                  class="btn"
                  :class="barUnit === u.value ? 'btn-secondary' : 'btn-outline-secondary'"
                  :aria-pressed="barUnit === u.value"
                  @click="barUnit = u.value"
                >{{ u.label }}</button>
              </div>
              <span class="text-muted">{{ period.year }}년 · 선택한 기간은 진하게, 누르면 목록</span>
              <span><span class="d-inline-block rounded-1 me-1 align-middle legend-box"></span>생산량</span>
              <span v-if="barTarget !== null"><span class="d-inline-block me-1 align-middle legend-line"></span>{{ barTargetName }} {{ barTarget }}대</span>
              <span v-if="showLastYear"><span class="d-inline-block rounded-1 me-1 align-middle legend-ghost"></span>전년 같은 {{ barUnit === 'month' ? '달' : '분기' }}</span>
              <label class="d-flex align-items-center gap-1 mb-0">
                <input v-model="view.showOrders" type="checkbox" class="form-check-input mt-0" />
                <span class="d-inline-block align-middle legend-orders"></span>수주량
              </label>
            </div>
            <ProductionBars
              :bars="bars"
              :target="barTarget"
              :target-name="barTargetName"
              :unit-name="barUnit === 'month' ? '달' : '분기'"
              :show-orders="view.showOrders"
              :show-last-year="showLastYear"
              @select="openBar"
            />
          </div>
        </div>
        <p v-if="data.production.annual_target === null" class="text-muted small mt-3 mb-0">
          연간 목표 생산량이 없어 달성률·부족치를 계산할 수 없습니다.
        </p>
        <p class="text-muted small mt-2 mb-0">
          ※ 당월·분기 목표는 "연간 목표 ÷ 12 × 개월 수"로 나눈 임시 기준입니다 (기업 확인 필요).
          수주량 = 그 달 납기일인 수주서 제품 수량(판매 실적 기본 기준). 일련번호로 잇지 않고 월 합계만 비교합니다.
        </p>

        <hr class="my-3" />
        <div class="row g-4">
          <!-- 연간 진행은 선택한 기간과 관계없이 그 연도 전체 기준 -->
          <div class="col-lg-6">
            <YearProgress :progress="data.year_progress" />
          </div>
          <div class="col-lg-6">
            <h3 class="h6 mb-2">{{ data.period.label }} 모델별 생산 <span class="text-muted fw-normal small">· 제조내역 모델명 기준, 누르면 그 모델 목록</span></h3>
            <ShareDoughnut :items="data.by_model" :total="total(data.by_model)" :color-of="modelColor" name-header="모델" :size="140" clickable @select="openModel" />
          </div>
        </div>
      </div></div>

      <DeliveryStatus :delivery="data.delivery" :unshipped="data.unshipped" :label="data.period.label" />

      <SalesSection />
    </template>
  </div>
</template>

<style scoped>
.legend-box {
  width: 10px;
  height: 10px;
  background: #4a7fc1;
}
.legend-ghost {
  width: 10px;
  height: 10px;
  border: 1.5px dashed #8a8f98;
}
.legend-orders {
  width: 16px;
  border-top: 2px solid #c26a1f;
}
.legend-line {
  width: 18px;
  border-top: 2px dashed #52514e;
}
</style>
