<script setup>
// 서비스팀 대시보드: 출장 횟수·유상 비율·월별 추이·지도·순위
import { computed, ref, watch } from 'vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import RankingBar from '@/components/RankingBar.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import StatCard from '@/components/StatCard.vue'
import KoreaMap from '@/components/service/KoreaMap.vue'
import MonthlyTrend from '@/components/service/MonthlyTrend.vue'
import { paidColor, percent } from '@/charts'
import { period } from '@/period'
import { getServiceDashboard } from '@/api/service'

const data = ref(null)
const error = ref('')
// 지역 단위: 시·도별 / 시·군별 (지도와 지역 순위 막대가 함께 바뀜)
const LEVELS = [{ key: 'region', label: '시·도별' }, { key: 'district', label: '시·군별' }]
const level = ref('region')

async function load() {
  error.value = ''
  try {
    data.value = await getServiceDashboard(period)
  } catch (e) {
    error.value = e.message
  }
}

const s = computed(() => data.value?.service)
const regionItems = computed(() => (level.value === 'region' ? s.value.by_region : s.value.by_district))

const paidRate = computed(() => {
  const paid = s.value?.paid.find((p) => p.name === '유상')?.quantity ?? 0
  return s.value?.trip_count ? percent(paid, s.value.trip_count) : null
})

watch(period, load, { deep: true, immediate: true })
</script>

<template>
  <div>
    <PeriodSelector />

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <h2 class="h6 mb-3">{{ data.period.label }} 출장 실적</h2>
      <div class="row g-3 mb-3">
        <div class="col-6 col-lg-3">
          <StatCard title="출장 횟수" :value="s.trip_count" unit="회" hint="출장 시작일 기준, 여러 날 출장도 1회" />
        </div>
        <div class="col-6 col-lg-3">
          <StatCard title="유상 비율" :value="paidRate" unit="%" hint="비용청구 유무 기준" />
        </div>
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <div class="text-muted small mb-1">{{ period.year }}년 월별 출장 횟수 <span class="ms-1">(진한 막대: 선택한 기간)</span></div>
            <MonthlyTrend :monthly="s.monthly" :highlight="data.period.months" />
          </div></div>
        </div>
      </div>

      <div class="row g-3 mb-4">
        <div class="col-lg-6">
          <div class="card h-100"><div class="card-body">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
              <h3 class="h6 mb-0">출장지 지도 <span class="text-muted fw-normal small">· 점이 클수록 출장이 많음 (점에 마우스를 올리면 횟수)</span></h3>
              <div class="btn-group btn-group-sm" role="group" aria-label="지역 단위">
                <button
                  v-for="l in LEVELS"
                  :key="l.key"
                  type="button"
                  class="btn"
                  :class="level === l.key ? 'btn-primary' : 'btn-outline-primary'"
                  :aria-pressed="level === l.key"
                  @click="level = l.key"
                >{{ l.label }}</button>
              </div>
            </div>
            <KoreaMap :items="regionItems" :small="level === 'district'" />
            <p v-if="level === 'district'" class="text-muted small mt-2 mb-0">특별·광역시·세종시는 시 전체를 점 하나로 표시합니다.</p>
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card mb-3"><div class="card-body">
            <h3 class="h6">유상·무상 비율</h3>
            <ShareDoughnut :items="s.paid" :total="s.trip_count" :color-of="paidColor" name-header="구분" unit="회" />
          </div></div>
          <div class="card"><div class="card-body">
            <h3 class="h6">지역별 출장 순위 <span class="text-muted fw-normal small">· {{ level === 'region' ? '시·도별' : '시·군별' }}</span></h3>
            <RankingBar :items="regionItems" :total="s.trip_count" unit="회" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">교체 부품 순위 <RouterLink to="/service/part-prices" class="small fw-normal ms-1">단가 보기</RouterLink></h3>
            <RankingBar :items="s.by_part" :total="s.by_part.reduce((a, b) => a + b.quantity, 0)" unit="회" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">A/S 제품 모델 순위</h3>
            <RankingBar :items="s.by_model" :total="s.by_model.reduce((a, b) => a + b.quantity, 0)" unit="대" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">출장 담당자 순위</h3>
            <RankingBar :items="s.by_person" :total="s.trip_count" unit="회" />
            <p class="text-muted small mb-0 mt-1">작성자+동행자, 보고서 1건당 1인 1회 (비중 = 전체 출장 대비 참여율)</p>
          </div></div>
        </div>
      </div>
    </template>

  </div>
</template>
