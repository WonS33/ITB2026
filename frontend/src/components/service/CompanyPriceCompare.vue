<script setup>
// 출장지(업체)별 비교: 업체마다 뉴토크 기준값 대비 평균 몇 % 비싸게/싸게 받았는지 막대로 보고,
// 막대(또는 표 줄)를 누르면 그 업체가 견적한 부품별 차이를 아래에 보여 준다
import { computed, ref, watch } from 'vue'
import { downloadCompanyComparison, getCompanyComparison } from '@/api/service'
import PriceDiffBar from './PriceDiffBar.vue'

defineProps({
  categories: { type: Array, default: () => [] },
})
const emit = defineEmits(['open-part'])

const category = ref('')
const data = ref(null)
const selected = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    data.value = await getCompanyComparison(category.value)
    if (!data.value.companies.some((c) => c.company === selected.value)) selected.value = null
  } catch (e) {
    error.value = e.message
  }
}
watch(category, load, { immediate: true })

const won = (v) => `${v.toLocaleString()}원`
const signed = (v) => (v > 0 ? `+${v.toLocaleString()}` : v.toLocaleString())
const signedRate = (r) => `${r > 0 ? '+' : ''}${r}%`

const companyBars = computed(() =>
  (data.value?.companies ?? []).map((c) => ({
    key: c.company,
    label: c.company,
    rate: c.average_rate,
    detail: `부품 ${c.count}개 평균 (비쌈 ${c.above} · 쌈 ${c.below})`,
  })))
const current = computed(() => data.value?.companies.find((c) => c.company === selected.value) ?? null)
const partBars = computed(() =>
  (current.value?.parts ?? []).map((p) => ({
    key: p.id,
    label: `${p.part_no} ${p.name}`,
    rate: p.diff_rate,
    detail: `${won(p.unit_price)} (당시 기준값 ${won(p.base_price)})${p.low ? ' · 크게 낮음' : ''}`,
  })))
async function exportExcel() {
  try {
    await downloadCompanyComparison(category.value)
  } catch (e) {
    error.value = e.message
  }
}
const toggle = (company) => (selected.value = selected.value === company ? null : company)
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="card mb-3"><div class="card-body">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
        <h2 class="h6 mb-0">출장지별 단가 비교 <span class="text-muted fw-normal">· 뉴토크 기준값 대비 평균 차이율</span></h2>
        <div class="d-flex gap-2">
          <select v-model="category" class="form-select form-select-sm w-auto" aria-label="분류">
            <option value="">모든 분류</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
          <button type="button" class="btn btn-outline-secondary btn-sm text-nowrap" :disabled="!data?.companies.length" @click="exportExcel">엑셀 내려받기</button>
        </div>
      </div>

      <!-- 할인 과다 점검: 기준값보다 크게 낮은 견적 수 -->
      <div v-if="data?.low_count" class="alert alert-light border small py-2 mb-2">
        <span class="badge badge-low me-1">크게 낮음</span>
        뉴토크 기준값보다 <strong>{{ data.low_alert_rate }}% 이상 낮은</strong> 견적이 <strong>{{ data.low_count }}건</strong> 있습니다.
        업체를 눌러 어떤 부품인지 확인하세요. (기준 {{ data.low_alert_rate }}%는 임시값 — 부품 단가 화면 "기본값 수정"에서 바꿀 수 있음)
      </div>

      <template v-if="data">
        <p v-if="!data.companies.length" class="text-muted small mb-0">비교할 출장지 단가가 없습니다. 견적서 업로드나 단가 직접 입력으로 쌓입니다.</p>
        <template v-else>
          <PriceDiffBar :items="companyBars" :selected="selected" @select="toggle" />
          <div class="table-responsive mt-3">
            <table class="table table-sm table-hover small mb-0 align-middle">
              <thead class="table-light">
                <tr>
                  <th>출장지(업체)</th><th class="text-end">비교 부품</th><th class="text-end">평균 차이율</th>
                  <th class="text-end">최저</th><th class="text-end">최고</th><th class="text-end">비쌈 · 쌈</th><th class="text-end">크게 낮음</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in data.companies" :key="c.company" role="button"
                    :class="{ 'table-primary': selected === c.company }" @click="toggle(c.company)">
                  <td class="fw-semibold">{{ c.company }}</td>
                  <td class="text-end">{{ c.count }}개</td>
                  <td class="text-end fw-semibold">{{ signedRate(c.average_rate) }}</td>
                  <td class="text-end">{{ signedRate(c.min_rate) }}</td>
                  <td class="text-end">{{ signedRate(c.max_rate) }}</td>
                  <td class="text-end text-muted">{{ c.above }} · {{ c.below }}</td>
                  <td class="text-end"><span v-if="c.low" class="badge badge-low">{{ c.low }}건</span><span v-else class="text-muted">-</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="text-muted small mt-2 mb-0">
            차이율 = (업체 단가 − 견적 당시 뉴토크 기준값) ÷ 당시 기준값. 부품마다 그 업체의 가장 최근 단가 1개만 쓰고,
            평균은 부품마다 같은 무게로 계산합니다(비싼 부품이 평균을 끌지 않게). 기준값이 없는 부품은 빠집니다.
            견적 단가는 출장 거리·작업 강도에 따라 달라질 수 있어 참고용입니다. 막대나 줄을 누르면 부품별 차이가 나옵니다.
          </p>
        </template>
      </template>
    </div></div>

    <!-- 고른 업체의 부품별 차이 -->
    <div v-if="current" class="card mb-3"><div class="card-body">
      <h2 class="h6 mb-2">{{ current.company }} <span class="text-muted fw-normal small">· 부품 {{ current.count }}개, 평균 {{ signedRate(current.average_rate) }}</span></h2>
      <PriceDiffBar :items="partBars" />
      <div class="table-responsive mt-3">
        <table class="table table-sm small mb-0 align-middle">
          <thead>
            <tr>
              <th>파트넘버</th><th>품명</th><th class="text-end" title="견적 적용 시작일에 쓰이던 단가표로 계산한 뉴토크 기준값">당시 기준값</th><th class="text-end">업체 단가</th>
              <th class="text-end">기준값 대비</th><th>적용 시작일</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in current.parts" :key="p.id">
              <td class="text-nowrap fw-semibold">
                <a href="#" @click.prevent="emit('open-part', p.id)" title="부품별 비교에서 이 부품 열기">{{ p.part_no }}</a>
              </td>
              <td>{{ p.name }}</td>
              <td class="text-end text-nowrap">{{ won(p.base_price) }}</td>
              <td class="text-end text-nowrap">{{ won(p.unit_price) }}</td>
              <td class="text-end text-nowrap">
                {{ signed(p.diff) }}원 <span class="text-muted">({{ signedRate(p.diff_rate) }})</span>
                <span v-if="p.low" class="badge badge-low ms-1">크게 낮음</span>
              </td>
              <td class="text-nowrap">{{ p.effective_date }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div></div>
  </div>
</template>
