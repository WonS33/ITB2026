<script setup>
// 서비스팀 대시보드: 출장 실적(횟수·유상/무상·월별 추이를 한 영역에) · 지도 · 순위 · 담당자 비중
import { computed, ref, watch } from 'vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import RankingBar from '@/components/RankingBar.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import KoreaMap from '@/components/service/KoreaMap.vue'
import MonthlyTrend from '@/components/service/MonthlyTrend.vue'
import PaidSplitBar from '@/components/service/PaidSplitBar.vue'
import PartUsageTable from '@/components/service/PartUsageTable.vue'
import { OTHER_COLOR, paidColor, SERIES_COLORS } from '@/charts'
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

// 범례에 쓰는 유상·무상 이름
const paidSplit = [{ name: '유상' }, { name: '무상' }]

// 출장 담당자 비중 도넛: 상위 5명 + 나머지는 "기타"로 묶는다 (조각이 너무 많으면 읽기 어려움)
const PERSON_TOP = 5
const personItems = computed(() => {
  const list = s.value.by_person
  const top = list.slice(0, PERSON_TOP)
  const rest = list.slice(PERSON_TOP).reduce((sum, p) => sum + p.quantity, 0)
  return rest ? [...top, { name: '기타', quantity: rest }] : top
})
// 비중의 분모 = 전체 참여 횟수 (한 출장에 여러 명이 가므로 출장 횟수보다 크다)
const personTotal = computed(() => s.value.by_person.reduce((sum, p) => sum + p.quantity, 0))
// 색은 순위가 아니라 이름에 붙인다: 상위 5명을 이름순으로 정렬해 팔레트 순서대로 (기타는 회색)
// 유상·무상 색과 겹치지 않는 팔레트 색만 쓰고, 초록 두 개가 이웃하지 않게 순서를 정했다
// (검증 도구 전체 쌍 검사: 4색 통과, 5색은 흰 틈 + 이름·횟수 표와 함께일 때 허용 범위)
const PERSON_COLORS = [SERIES_COLORS[2], SERIES_COLORS[3], SERIES_COLORS[6], SERIES_COLORS[4], SERIES_COLORS[5]]
const personColor = (name) => {
  if (name === '기타') return OTHER_COLOR
  const names = personItems.value.filter((p) => p.name !== '기타').map((p) => p.name).sort((a, b) => a.localeCompare(b, 'ko'))
  return PERSON_COLORS[names.indexOf(name)] ?? OTHER_COLOR
}

watch(period, load, { deep: true, immediate: true })
</script>

<template>
  <div>
    <PeriodSelector />

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <!-- 출장 실적: 출장 횟수·유상/무상 비율·월별 추이를 한 영역에서 -->
      <div class="card mb-3"><div class="card-body">
        <div class="row g-4 align-items-center">
          <div class="col-lg-3">
            <h2 class="h6 mb-2">{{ data.period.label }} 출장 실적</h2>
            <div class="display-6 fw-semibold lh-1">{{ s.trip_count.toLocaleString() }}<span class="fs-6 fw-normal ms-1">회</span></div>
            <div class="text-muted small mb-3">출장 시작일 기준, 여러 날 출장도 1회</div>
            <!-- 유상·무상 비율 도넛 (월별 막대와 같은 색) + 횟수·비중 표 -->
            <ShareDoughnut :items="s.paid" :total="s.trip_count" :color-of="paidColor" name-header="구분" unit="회" :size="140" />
          </div>
          <div class="col-lg-9">
            <div class="d-flex flex-wrap align-items-center gap-3 small mb-1">
              <span class="text-muted">{{ period.year }}년 월별 출장 횟수 (선택한 기간은 진하게, 나머지 달은 흐리게)</span>
              <span v-for="p in paidSplit" :key="p.name">
                <span class="d-inline-block rounded-1 me-1 align-middle" :style="{ width: '10px', height: '10px', background: paidColor(p.name) }"></span>{{ p.name }}
              </span>
            </div>
            <MonthlyTrend :monthly="s.monthly" :highlight="data.period.months" />
          </div>
        </div>
      </div></div>

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
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">지역별 출장 순위 <span class="text-muted fw-normal small">· {{ level === 'region' ? '시·도별' : '시·군별' }}</span></h3>
            <RankingBar :items="regionItems" :total="s.trip_count" unit="회" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">교체 부품 순위 <RouterLink to="/service/part-prices" class="small fw-normal ms-1">단가 보기</RouterLink></h3>
            <PartUsageTable :items="s.by_part" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">A/S 제품 모델 순위 <span class="text-muted fw-normal small">· 유상·무상</span></h3>
            <PaidSplitBar :items="s.by_model" unit="대" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">출장 담당자 비중</h3>
            <ShareDoughnut :items="personItems" :total="personTotal" :color-of="personColor" name-header="담당자" unit="회" />
            <p class="text-muted small mb-0 mt-2">
              작성자+동행자를 보고서 1건당 1인 1회로 셈. 비중 = 전체 참여 {{ personTotal }}회 중 차지하는 몫
              <template v-if="s.by_person.length > PERSON_TOP"> · 6위부터는 "기타"로 묶음</template>
            </p>
          </div></div>
        </div>
      </div>
    </template>

  </div>
</template>
