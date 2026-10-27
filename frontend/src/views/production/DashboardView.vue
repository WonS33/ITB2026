<script setup>
// 생산팀 대시보드: 납기 임박(오늘 기준) + 생산 실적(목표 대비) + 판매 실적
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PeriodSelector from '@/components/PeriodSelector.vue'
import DueSoon from '@/components/production/DueSoon.vue'
import SalesSection from '@/components/production/SalesSection.vue'
import AchievementRing from '@/components/production/AchievementRing.vue'
import MonthlyProduction from '@/components/production/MonthlyProduction.vue'
import YearProgress from '@/components/production/YearProgress.vue'
import TargetForm from '@/components/production/TargetForm.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import { OTHER_COLOR, SERIES_COLORS } from '@/charts'
import { period } from '@/period'
import { getDashboard } from '@/api/production'

const data = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    data.value = await getDashboard(period)
  } catch (e) {
    error.value = e.message
  }
}

// 모델 색: 전체 모델명 목록(가나다순)의 순서로 고정 → 기간이 바뀌어도 같은 모델은 같은 색
function modelColor(name) {
  const i = data.value?.model_names.indexOf(name) ?? -1
  return i === -1 || i >= SERIES_COLORS.length ? OTHER_COLOR : SERIES_COLORS[i]
}
// 숫자의 근거 보기: 월 막대 → 그 달 제조내역, 모델 → 그 모델로 걸러진 제조내역 (기간 선택은 화면 전체가 같이 씀)
const router = useRouter()
function openMonth(month) {
  Object.assign(period, { kind: 'month', month })
  router.push('/production/records')
}
const openModel = (model) => router.push({ path: '/production/records', query: { model } })

const total = (items) => items.reduce((sum, i) => sum + i.quantity, 0)

// 기간을 바꾸면 다시 불러온다
watch(period, load, { deep: true, immediate: true })
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
          <!-- 연간 목표: 모두 볼 수 있고, 수정 권한자에게만 [목표 수정] 버튼이 보인다 -->
          <TargetForm :year="period.year" @saved="load" />
        </div>
        <div class="row g-4 align-items-center">
          <div class="col-xl-5">
            <AchievementRing :production="data.production" />
          </div>
          <div class="col-xl-7">
            <div class="d-flex flex-wrap align-items-center gap-3 small mb-1">
              <span class="text-muted">{{ period.year }}년 월별 생산량 (선택한 기간은 진하게, 막대를 누르면 그 달 목록)</span>
              <span><span class="d-inline-block rounded-1 me-1 align-middle legend-box"></span>생산량</span>
              <span v-if="data.monthly.monthly_target !== null"><span class="d-inline-block me-1 align-middle legend-line"></span>월 목표 {{ data.monthly.monthly_target }}대</span>
            </div>
            <MonthlyProduction :months="data.monthly.months" :monthly-target="data.monthly.monthly_target" :highlight="data.period.months" @select="openMonth" />
          </div>
        </div>
        <p v-if="data.production.annual_target === null" class="text-muted small mt-3 mb-0">
          연간 목표 생산량이 없어 달성률·부족치를 계산할 수 없습니다.
        </p>
        <p class="text-muted small mt-2 mb-0">
          ※ 당월·분기 목표는 "연간 목표 ÷ 12 × 개월 수"로 나눈 임시 기준입니다 (기업 확인 필요).
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

      <SalesSection :sales="data.sales" :label="data.period.label" />
    </template>
  </div>
</template>

<style scoped>
.legend-box {
  width: 10px;
  height: 10px;
  background: #4a7fc1;
}
.legend-line {
  width: 18px;
  border-top: 2px dashed #52514e;
}
</style>
