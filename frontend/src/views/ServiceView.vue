<script setup>
import { computed, ref, watch } from 'vue'
import FileUpload from '@/components/FileUpload.vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import RankingBar from '@/components/RankingBar.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import StatCard from '@/components/StatCard.vue'
import KoreaMap from '@/components/service/KoreaMap.vue'
import MonthlyTrend from '@/components/service/MonthlyTrend.vue'
import TripReportList from '@/components/service/TripReportList.vue'
import { canEdit } from '@/auth'
import { paidColor, percent } from '@/charts'
import { period } from '@/period'
import { getServiceDashboard } from '@/api/service'

const data = ref(null)
const error = ref('')
const list = ref(null)

async function load() {
  error.value = ''
  try {
    data.value = await getServiceDashboard(period)
  } catch (e) {
    error.value = e.message
  }
}

function onSaved() {
  load()
  list.value?.load()
}

const s = computed(() => data.value?.service)
const paidRate = computed(() => {
  const paid = s.value?.paid.find((p) => p.name === '유상')?.quantity ?? 0
  return s.value?.trip_count ? percent(paid, s.value.trip_count) : null
})

watch(period, load, { deep: true, immediate: true })
</script>

<template>
  <div>
    <div class="d-flex align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0">서비스팀</h1>
      <span v-if="canEdit('service')" class="badge bg-primary">열람·수정</span>
      <span v-else class="badge bg-secondary">열람만</span>
    </div>
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
            <h3 class="h6">출장지 지도 <span class="text-muted fw-normal small">· 점이 클수록 출장이 많음 (점에 마우스를 올리면 횟수)</span></h3>
            <KoreaMap :items="s.by_region" />
          </div></div>
        </div>
        <div class="col-lg-6">
          <div class="card mb-3"><div class="card-body">
            <h3 class="h6">유상·무상 비율</h3>
            <ShareDoughnut :items="s.paid" :total="s.trip_count" :color-of="paidColor" name-header="구분" unit="회" />
          </div></div>
          <div class="card"><div class="card-body">
            <h3 class="h6">지역별 출장 순위</h3>
            <RankingBar :items="s.by_region" :total="s.trip_count" unit="회" />
          </div></div>
        </div>
        <div class="col-lg-4">
          <div class="card h-100"><div class="card-body">
            <h3 class="h6">교체 부품 순위</h3>
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
      <p class="text-muted small">※ 교체 부품 단가는 단가 출처(견적서·부품 단가표 등)를 기업에 확인한 뒤 추가합니다.</p>
    </template>

    <TripReportList ref="list" />

    <!-- 업로드는 서비스팀 수정 권한자에게만 보인다 (백엔드 API에서도 권한을 다시 확인함) -->
    <FileUpload
      v-if="canEdit('service')"
      kind="trip_report_pdf"
      title="출장보고서 PDF 업로드"
      accept=".pdf"
      help="출장보고서 PDF(1쪽 = 1건)를 올리면 보고서 1건을 1행으로 보여줍니다. 시·도는 처음 보는 요청처일 때 직접 고르면 다음부터 자동으로 채워집니다. 잘린 부품명·요청처(…)는 전체 이름으로 고친 뒤 저장하세요."
      @saved="onSaved"
    />
  </div>
</template>
