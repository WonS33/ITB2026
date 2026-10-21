<script setup>
// 기간 안의 출장보고서 목록 → 행을 누르면 상세(고장·작업 내용 포함)
import { ref, watch } from 'vue'
import { getTripReport, getTripReports } from '@/api/service'
import { period } from '@/period'

const reports = ref([])
const detail = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  detail.value = null
  try {
    reports.value = (await getTripReports(period)).results
  } catch (e) {
    error.value = e.message
  }
}

async function open(id) {
  try {
    detail.value = await getTripReport(id)
  } catch (e) {
    error.value = e.message
  }
}

defineExpose({ load })
watch(period, load, { deep: true, immediate: true })
</script>

<template>
  <div class="card mb-4">
    <div class="card-body">
      <h2 class="h6">출장보고서 목록 <span class="text-muted fw-normal">· {{ reports.length }}건</span></h2>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <p v-if="!reports.length" class="text-muted small mb-0">이 기간의 출장보고서가 없습니다.</p>
      <div v-else class="table-responsive" style="max-height: 60vh">
        <table class="table table-sm table-hover small mb-0">
          <thead class="table-light sticky-top">
            <tr><th>출장일</th><th>요청처</th><th>시·도</th><th>비용</th><th>작업</th><th>모델</th><th>작성자</th></tr>
          </thead>
          <tbody>
            <tr
              v-for="r in reports"
              :key="r.id"
              role="button"
              :class="{ 'table-primary': detail && detail.id === r.id }"
              @click="open(r.id)"
            >
              <td class="text-nowrap">{{ r.start_date }}<template v-if="r.end_date && r.end_date !== r.start_date"> ~ {{ r.end_date.slice(5) }}</template></td>
              <td>{{ r.requester }}</td>
              <td class="text-nowrap">{{ r.region }} {{ r.district }}</td>
              <td>{{ r.paid_type }}</td>
              <td>{{ r.work_type || '-' }}</td>
              <td>{{ r.models.join(', ') || '-' }}</td>
              <td class="text-nowrap">{{ r.author }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="detail" class="border rounded p-3 mt-3 small">
        <h3 class="h6">{{ detail.start_date }} · {{ detail.requester }} ({{ [detail.region, detail.district].filter(Boolean).join(' ') }})</h3>
        <div class="row g-2 mb-2">
          <div class="col-md-6"><span class="text-muted">출장 목적</span> {{ detail.purpose || '-' }}</div>
          <div class="col-md-3"><span class="text-muted">비용청구</span> {{ detail.paid_type }}</div>
          <div class="col-md-3"><span class="text-muted">작업 구분</span> {{ detail.work_type || '-' }}</div>
          <div class="col-md-6"><span class="text-muted">작성자</span> {{ detail.author }} · <span class="text-muted">동행자</span> {{ detail.companions.join(', ') || '-' }}</div>
          <div class="col-md-6"><span class="text-muted">교체 부품</span> {{ detail.parts.join(', ') || '-' }}</div>
        </div>
        <table v-if="detail.products.length" class="table table-sm table-bordered mb-2">
          <thead class="table-light"><tr><th>모델명</th><th>사양</th><th>일련번호(원문)</th><th>수량</th></tr></thead>
          <tbody>
            <tr v-for="(p, i) in detail.products" :key="i">
              <td>{{ p.model_name }}</td><td>{{ p.spec || '-' }}</td><td>{{ p.serial_no_raw || '-' }}</td><td>{{ p.quantity }}</td>
            </tr>
          </tbody>
        </table>
        <div class="row g-2">
          <div class="col-md-4"><div class="text-muted">고장 내용</div><div style="white-space: pre-line">{{ detail.fault_description || '-' }}</div></div>
          <div class="col-md-4"><div class="text-muted">작업 내용</div><div style="white-space: pre-line">{{ detail.work_description || '-' }}</div></div>
          <div class="col-md-4"><div class="text-muted">작업 결과</div><div style="white-space: pre-line">{{ detail.work_result || '-' }}</div></div>
        </div>
      </div>
    </div>
  </div>
</template>
