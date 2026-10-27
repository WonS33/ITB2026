<script setup>
// 수주 내역 목록 (specs/05-production.md 7절): 올린 수주서를 납기일 기준으로 훑어본다 (대시보드 판매량과 같은 기준)
// 줄을 누르면 아래에 그 수주서의 제품 정보·비고를 펼친다. 걸러 낸 목록은 엑셀로 내려받을 수 있다.
import { reactive, ref, watch } from 'vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import ListPager from '@/components/ListPager.vue'
import { exportOrders, getOrders } from '@/api/production'
import { industryColor } from '@/charts'
import { period } from '@/period'

const filters = reactive({ q: '', industry: '' })
const query = ref('')
const page = ref(1)
const data = ref(null)
const opened = ref('') // 펼친 판매번호
const error = ref('')
const exporting = ref(false)

async function load() {
  error.value = ''
  opened.value = ''
  try {
    data.value = await getOrders(period, filters, page.value)
  } catch (e) {
    error.value = e.message
  }
}

watch([period, filters], () => (page.value === 1 ? load() : (page.value = 1)), { deep: true })
watch(page, load, { immediate: true })

async function download() {
  exporting.value = true
  error.value = ''
  try {
    await exportOrders(period, filters)
  } catch (e) {
    error.value = e.message
  } finally {
    exporting.value = false
  }
}

const toggle = (salesNo) => (opened.value = opened.value === salesNo ? '' : salesNo)
const products = (o) => o.items.map((i) => `${i.product_name} ×${i.quantity}`).join(', ') || '-'
</script>

<template>
  <div>
    <PeriodSelector />

    <div class="card mb-4"><div class="card-body">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <h2 class="h6 mb-0">
          수주 내역
          <span v-if="data" class="text-muted fw-normal">
            · {{ data.period.label }} · 납기일 기준 {{ data.counts.total.toLocaleString() }}건, 제품 {{ data.counts.quantity.toLocaleString() }}대
          </span>
        </h2>
        <button type="button" class="btn btn-outline-primary btn-sm" :disabled="exporting || !data?.total" @click="download">
          {{ exporting ? '만드는 중…' : '엑셀 내려받기' }}
        </button>
      </div>

      <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
        <form class="d-flex gap-2" @submit.prevent="filters.q = query.trim()">
          <input v-model="query" class="form-control form-control-sm" style="width: 260px" placeholder="판매번호·수주서류 번호·판매처·사업명·품명" aria-label="검색어" />
          <button class="btn btn-primary btn-sm text-nowrap">검색</button>
        </form>
        <select v-model="filters.industry" class="form-select form-select-sm w-auto" aria-label="산업 분야">
          <option value="">모든 산업 분야</option>
          <option v-for="i in data?.industries || []" :key="i" :value="i">{{ i }}</option>
        </select>
        <button v-if="filters.q || filters.industry" type="button" class="btn btn-link btn-sm" @click="Object.assign(filters, { q: '', industry: '' }); query = ''">
          조건 지우기
        </button>
      </div>

      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <template v-if="data">
        <p v-if="!data.results.length" class="text-muted small mb-0">조건에 맞는 수주서가 없습니다.</p>
        <div v-else class="table-responsive" style="max-height: 65vh">
          <table class="table table-sm table-hover small mb-0 align-middle">
            <thead class="table-light sticky-top">
              <tr>
                <th>납기일</th><th>판매번호</th><th>수주서류</th><th>수주일</th><th>산업 분야</th>
                <th>판매처</th><th>사업명</th><th>제품</th><th class="text-end">수량</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="o in data.results" :key="o.sales_no">
                <tr role="button" :class="{ 'table-primary': opened === o.sales_no }" :aria-expanded="opened === o.sales_no" @click="toggle(o.sales_no)">
                  <td class="text-nowrap">{{ o.due_date || '-' }}</td>
                  <td class="text-nowrap fw-semibold">{{ o.sales_no }}</td>
                  <td class="text-nowrap">{{ o.order_doc_no ? `#${o.order_doc_no}` : '-' }}</td>
                  <td class="text-nowrap">{{ o.order_date || '-' }}</td>
                  <td class="text-nowrap">
                    <span class="d-inline-block rounded-circle me-1 align-middle" :style="{ width: '8px', height: '8px', background: industryColor(o.industry) }"></span>{{ o.industry }}
                  </td>
                  <td>{{ o.customer || '-' }}</td>
                  <td>{{ o.project_name || '-' }}</td>
                  <td>{{ products(o) }}</td>
                  <td class="text-end">{{ o.quantity }}</td>
                </tr>
                <!-- 펼친 줄: 제품 정보 전체 + 최종발주처·사업구분 원문·납품일·비고 -->
                <tr v-if="opened === o.sales_no" class="detail-row">
                  <td colspan="9">
                    <div class="row g-2 mb-2">
                      <div class="col-md-4"><span class="text-muted">최종발주처/EPC</span> {{ o.final_orderer || '-' }}</div>
                      <div class="col-md-4"><span class="text-muted">사업구분 원문</span> {{ o.business_type_raw || '-' }}</div>
                      <div class="col-md-4"><span class="text-muted">납품일/출장일</span> {{ o.delivery_date || '-' }}</div>
                    </div>
                    <table v-if="o.items.length" class="table table-sm table-bordered bg-white mb-2">
                      <thead class="table-light"><tr><th>품명</th><th class="text-end">수량</th><th>전원</th><th>Flange</th><th>RPM/OT</th><th>스템/부시가공</th></tr></thead>
                      <tbody>
                        <tr v-for="(i, n) in o.items" :key="n">
                          <td>{{ i.product_name }}</td><td class="text-end">{{ i.quantity }}</td><td>{{ i.power || '-' }}</td>
                          <td>{{ i.flange || '-' }}</td><td>{{ i.rpm_ot || '-' }}</td><td>{{ i.stem_bush || '-' }}</td>
                        </tr>
                      </tbody>
                    </table>
                    <div v-if="o.note"><span class="text-muted">비고</span> <span style="white-space: pre-line">{{ o.note }}</span></div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <ListPager :page="data.page" :page-size="data.page_size" :total="data.total" @change="page = $event" />
        <p class="text-muted small mt-2 mb-0">줄을 누르면 제품 정보와 비고를 펼칩니다. 엑셀은 제품 1개 = 1행으로 담깁니다.</p>
      </template>
    </div></div>
  </div>
</template>

<style scoped>
.detail-row > td {
  background: #f7f8fa;
}
</style>
