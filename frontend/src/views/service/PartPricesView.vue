<script setup>
// 교체부품 단가 — 파트넘버별 5개 기준 비교 (specs/06-service.md)
// 1) 뉴토크 기준값 = 단가표 기준단가 × (1 − 할인율) + 추가단가
// 2~5) 출장지(업체)별 단가의 평균·최저·최고·최고−최저 (업체마다 가장 최근 단가 1개)
// 줄을 누르면 아래에 출장지별 단가 목록과 기준값 대비 차이를 보여 준다
// 탭 '출장지별 비교': 업체마다 기준값 대비 평균 차이율을 그래프로 (?view=companies)
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { canEdit } from '@/auth'
import { downloadPartCatalog, getPartCatalog, getPartCatalogItem, setPartCatalogItem, setPriceStandard } from '@/api/service'
import CompanyPriceCompare from '@/components/service/CompanyPriceCompare.vue'
import PriceDiffBar from '@/components/service/PriceDiffBar.vue'

const editable = canEdit('service')
const route = useRoute()
const router = useRouter()
const tab = computed(() => (route.query.view === 'companies' ? 'companies' : 'parts'))
const setTab = (view) => router.replace({ query: view === 'companies' ? { view } : {} })
const data = ref(null)
const detail = ref(null)
const error = ref('')
const filters = reactive({ q: '', category: '' })
const query = ref('')
const loading = ref(false)

async function load() {
  error.value = ''
  loading.value = true
  try {
    data.value = await getPartCatalog(filters.q, filters.category)
    // 검색 결과가 하나면 바로 상세를 연다 (파트넘버로 찾을 때)
    if (data.value.items.length === 1) open(data.value.items[0].id)
    else if (detail.value && !data.value.items.some((i) => i.id === detail.value.id)) detail.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
watch(filters, load, { deep: true })
onMounted(load)

async function open(id) {
  try {
    detail.value = await getPartCatalogItem(id)
    resetItemForm()
  } catch (e) {
    error.value = e.message
  }
}

const won = (v) => (v === null || v === undefined ? '-' : `${v.toLocaleString()}원`)
const signed = (v) => (v > 0 ? `+${v.toLocaleString()}` : v.toLocaleString())
const settingText = (rate, extra) => `할인 ${rate}% · 추가 ${extra >= 0 ? '+' : ''}${extra.toLocaleString()}원`

// ── 전체 기본값 수정 (수정 권한자) ──
const standardForm = reactive({ open: false, discount_rate: 0, extra_price: 0, low_alert_rate: 10, error: '' })
function openStandard() {
  Object.assign(standardForm, { open: true, error: '', ...{
    discount_rate: data.value.standard.default_discount_rate,
    extra_price: data.value.standard.default_extra_price,
    low_alert_rate: data.value.standard.low_alert_rate,
  } })
}
async function saveStandard() {
  standardForm.error = ''
  try {
    await setPriceStandard({ discount_rate: Number(standardForm.discount_rate), extra_price: Number(standardForm.extra_price),
                             low_alert_rate: Number(standardForm.low_alert_rate) })
    standardForm.open = false
    await load()
    if (detail.value) await open(detail.value.id)
  } catch (e) {
    standardForm.error = e.message
  }
}

// ── 부품별 할인율·추가단가 (비우면 전체 기본값) ──
const itemForm = reactive({ discount_rate: '', extra_price: '', error: '', saved: '' })
function resetItemForm() {
  const custom = detail.value?.custom
  Object.assign(itemForm, {
    discount_rate: custom ? detail.value.discount_rate : '',
    extra_price: custom ? detail.value.extra_price : '',
    error: '',
    saved: '',
  })
}
async function saveItem(useDefault = false) {
  itemForm.error = ''
  const toValue = (v) => (useDefault || v === '' || v === null ? null : Number(v))
  try {
    detail.value = await setPartCatalogItem(detail.value.id, {
      discount_rate: toValue(itemForm.discount_rate),
      extra_price: toValue(itemForm.extra_price),
    })
    resetItemForm()
    itemForm.saved = '저장했습니다.'
    await load()
  } catch (e) {
    itemForm.error = e.message
  }
}

const count = computed(() => data.value?.items.length ?? 0)

async function exportExcel() {
  try {
    await downloadPartCatalog(filters.q, filters.category)
  } catch (e) {
    error.value = e.message
  }
}

// 출장지별 비교 탭에서 파트넘버를 누르면 부품별 비교 탭으로 와서 그 부품을 연다
async function openFromCompany(id) {
  setTab('parts')
  await open(id)
}

// 부품 상세 그래프: 업체마다 가장 최근 단가(비교 기준)의 기준값 대비 차이율
const detailBars = computed(() =>
  (detail.value?.prices ?? [])
    .filter((p) => p.latest && p.diff_rate !== null)
    .sort((a, b) => b.diff_rate - a.diff_rate)
    .map((p) => ({ key: p.id, label: p.company, rate: p.diff_rate, detail: `${won(p.unit_price)} (${signed(p.diff)}원)` })))
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <a href="#" class="nav-link" :class="{ active: tab === 'parts' }" @click.prevent="setTab('parts')">부품별 비교</a>
      </li>
      <li class="nav-item">
        <a href="#" class="nav-link" :class="{ active: tab === 'companies' }" @click.prevent="setTab('companies')">출장지별 비교</a>
      </li>
    </ul>

    <CompanyPriceCompare v-if="tab === 'companies'" :categories="data?.categories || []" @open-part="openFromCompany" />

    <div v-show="tab === 'parts'" class="card mb-3"><div class="card-body">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
        <h2 class="h6 mb-0">교체부품 단가 <span class="text-muted fw-normal">· 파트넘버별 기준값과 출장지별 단가 비교</span></h2>
        <div class="d-flex gap-2">
          <button type="button" class="btn btn-outline-secondary btn-sm" :disabled="!count" @click="exportExcel">엑셀 내려받기</button>
          <RouterLink v-if="editable" to="/service/part-prices/input" class="btn btn-outline-primary btn-sm">단가 직접 입력</RouterLink>
        </div>
      </div>

      <!-- 검색: 파트넘버(하이픈 없이·숫자만도 가능) 또는 품명 -->
      <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
        <form class="d-flex gap-2" @submit.prevent="filters.q = query.trim()">
          <input v-model="query" class="form-control form-control-sm" style="width: 280px"
                 placeholder="파트넘버(예: 05-A-01, 0501) 또는 품명" aria-label="파트넘버·품명 검색" />
          <button class="btn btn-primary btn-sm text-nowrap">검색</button>
        </form>
        <select v-model="filters.category" class="form-select form-select-sm w-auto" aria-label="분류">
          <option value="">모든 분류</option>
          <option v-for="c in data?.categories || []" :key="c" :value="c">{{ c }}</option>
        </select>
        <button v-if="filters.q || filters.category" type="button" class="btn btn-link btn-sm"
                @click="Object.assign(filters, { q: '', category: '' }); query = ''">조건 지우기</button>
      </div>

      <!-- 뉴토크 기준값 계산 규칙 -->
      <div v-if="data" class="d-flex flex-wrap align-items-center gap-2 small mb-3 p-2 rounded standard">
        <span><strong>뉴토크 기준값</strong> = 단가표 기준단가 × (1 − 할인율) + 추가단가</span>
        <span class="text-muted">· 전체 기본값: {{ settingText(data.standard.default_discount_rate, data.standard.default_extra_price) }}</span>
        <span v-if="data.list_price_date" class="text-muted">· 단가표 기준일 {{ data.list_price_date }} (임시)</span>
        <span class="text-muted">· 크게 낮음 표시: 기준값보다 {{ data.standard.low_alert_rate }}% 이상 낮은 견적 (임시 기준)</span>
        <button v-if="editable && !standardForm.open" type="button" class="btn btn-link btn-sm p-0" @click="openStandard">기본값 수정</button>
        <form v-if="standardForm.open" class="d-flex flex-wrap align-items-center gap-2" @submit.prevent="saveStandard">
          <label class="d-flex align-items-center gap-1">할인율
            <input v-model="standardForm.discount_rate" type="number" min="0" max="100" step="0.01" class="form-control form-control-sm" style="width: 90px" />%
          </label>
          <label class="d-flex align-items-center gap-1">추가단가
            <input v-model="standardForm.extra_price" type="number" step="1" class="form-control form-control-sm" style="width: 120px" />원
          </label>
          <label class="d-flex align-items-center gap-1">크게 낮음 기준
            <input v-model="standardForm.low_alert_rate" type="number" min="0" max="100" step="0.1" class="form-control form-control-sm" style="width: 80px" />%
          </label>
          <button class="btn btn-primary btn-sm">저장</button>
          <button type="button" class="btn btn-outline-secondary btn-sm" @click="standardForm.open = false">취소</button>
          <span v-if="standardForm.error" class="text-danger">{{ standardForm.error }}</span>
        </form>
      </div>

      <template v-if="data">
        <p v-if="!count" class="text-muted small mb-0">
          {{ filters.q || filters.category ? '조건에 맞는 부품이 없습니다.' : '단가표가 없습니다. 관리자가 단가표를 넣어야 합니다.' }}
        </p>
        <div v-else class="table-responsive" style="max-height: 60vh">
          <table class="table table-sm table-hover small mb-0 align-middle">
            <thead class="table-light sticky-top">
              <tr>
                <th>파트넘버</th>
                <th>품명</th>
                <th>적용 모델</th>
                <th class="text-end col-standard">뉴토크 기준값</th>
                <th class="text-end">평균</th>
                <th class="text-end">최저</th>
                <th class="text-end">최고</th>
                <th class="text-end">최고−최저</th>
                <th class="text-end">출장지</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="i in data.items" :key="i.id" role="button" :class="{ 'table-primary': detail?.id === i.id }" @click="open(i.id)">
                <td class="text-nowrap fw-semibold">{{ i.part_no }}</td>
                <td>{{ i.name }}</td>
                <td class="text-muted">{{ i.applies_to || '-' }}</td>
                <td class="text-end text-nowrap fw-semibold col-standard">
                  {{ won(i.standard_price) }}
                  <span v-if="i.custom" class="badge bg-light text-dark border ms-1" title="이 부품만 할인율·추가단가를 따로 정함">별도</span>
                </td>
                <td class="text-end text-nowrap">{{ won(i.stats.average) }}</td>
                <td class="text-end text-nowrap">{{ won(i.stats.min) }}</td>
                <td class="text-end text-nowrap">{{ won(i.stats.max) }}</td>
                <td class="text-end text-nowrap">{{ won(i.stats.range) }}</td>
                <td class="text-end text-nowrap text-muted">{{ i.stats.count }}곳</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-muted small mt-2 mb-0">
          {{ count }}개 부품. 평균·최저·최고는 출장지(업체)마다 가장 최근 단가 1개로 계산합니다(적용 예정 단가 제외).
          단가표 기준단가가 "-"인 부품은 기준값이 비어 있습니다. 줄을 누르면 출장지별 단가가 아래에 나옵니다.
        </p>
      </template>
      <p v-else-if="loading" class="text-muted small mb-0">불러오는 중…</p>
    </div></div>

    <!-- 부품 상세: 출장지별 단가 -->
    <div v-if="detail && tab === 'parts'" class="card mb-3"><div class="card-body">
      <h2 class="h6 mb-1">{{ detail.part_no }} {{ detail.name }} <span class="text-muted fw-normal small">· {{ detail.category }} · {{ detail.applies_to || '적용 모델 없음' }}</span></h2>
      <div class="d-flex flex-wrap gap-4 small mb-3">
        <span>단가표 기준단가 <strong>{{ won(detail.list_price) }}</strong><span v-if="detail.list_price_date" class="text-muted"> ({{ detail.list_price_date }} 기준)</span></span>
        <span>{{ settingText(detail.discount_rate, detail.extra_price) }}<span class="text-muted">{{ detail.custom ? ' (이 부품 별도)' : ' (전체 기본값)' }}</span></span>
        <span>뉴토크 기준값 <strong>{{ won(detail.standard_price) }}</strong></span>
      </div>

      <!-- 부품별 할인율·추가단가 (수정 권한자) -->
      <form v-if="editable" class="d-flex flex-wrap align-items-center gap-2 small mb-3" @submit.prevent="saveItem()">
        <span class="text-muted">이 부품만 따로:</span>
        <label class="d-flex align-items-center gap-1">할인율
          <input v-model="itemForm.discount_rate" type="number" min="0" max="100" step="0.01" class="form-control form-control-sm" style="width: 90px" placeholder="기본값" />%
        </label>
        <label class="d-flex align-items-center gap-1">추가단가
          <input v-model="itemForm.extra_price" type="number" step="1" class="form-control form-control-sm" style="width: 120px" placeholder="기본값" />원
        </label>
        <button class="btn btn-primary btn-sm">저장</button>
        <button v-if="detail.custom" type="button" class="btn btn-outline-secondary btn-sm" @click="saveItem(true)">전체 기본값으로</button>
        <span v-if="itemForm.error" class="text-danger">{{ itemForm.error }}</span>
        <span v-if="itemForm.saved" class="text-success">{{ itemForm.saved }}</span>
      </form>

      <!-- 단가표 개정 이력: 예전 견적은 그 당시 단가표 기준값과 비교한다 -->
      <details v-if="detail.revisions.length" class="small mb-3">
        <summary class="text-muted">단가표 개정 이력 {{ detail.revisions.length }}건</summary>
        <table class="table table-sm small mb-0 mt-1 w-auto">
          <thead><tr><th>단가표 기준일</th><th class="text-end">기준단가</th><th class="text-end">뉴토크 기준값</th></tr></thead>
          <tbody>
            <tr v-for="r in detail.revisions" :key="r.effective_date">
              <td>{{ r.effective_date }}</td><td class="text-end">{{ won(r.list_price) }}</td><td class="text-end">{{ won(r.standard_price) }}</td>
            </tr>
          </tbody>
        </table>
      </details>

      <!-- 5개 기준 요약 -->
      <div class="row g-2 mb-3 text-center small">
        <div v-for="[label, value] in [['뉴토크 기준값', detail.standard_price], ['평균', detail.stats.average], ['최저', detail.stats.min], ['최고', detail.stats.max], ['최고−최저', detail.stats.range]]"
             :key="label" class="col">
          <div class="border rounded py-2" :class="{ 'stat-standard': label === '뉴토크 기준값' }">
            <div class="text-muted">{{ label }}</div>
            <div class="fw-semibold">{{ won(value) }}</div>
          </div>
        </div>
      </div>

      <!-- 출장지별 단가 그래프 (비교 기준 단가만) -->
      <div v-if="detailBars.length" class="mb-3">
        <div class="small fw-semibold mb-1">출장지별 단가 · 뉴토크 기준값 대비</div>
        <PriceDiffBar :items="detailBars" />
      </div>

      <p v-if="!detail.prices.length" class="text-muted small mb-0">아직 출장지별 단가가 없습니다. 견적서 업로드나 단가 직접 입력으로 쌓입니다.</p>
      <div v-else class="table-responsive">
        <table class="table table-sm small mb-0 align-top">
          <thead>
            <tr>
              <th>출장지(업체)</th><th>적용 시작일</th><th class="text-end">단가</th>
              <th class="text-end" title="견적 적용 시작일에 쓰이던 단가표로 계산한 뉴토크 기준값">당시 기준값</th><th class="text-end">기준값 대비</th>
              <th>출처</th><th>사업명</th><th>비고</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in detail.prices" :key="p.id" :class="{ 'text-muted': !p.latest }">
              <td>
                {{ p.company }}
                <span v-if="p.latest" class="badge bg-light text-dark border ms-1" title="평균·최저·최고 계산에 쓰인 단가">비교 기준</span>
              </td>
              <td class="text-nowrap">{{ p.effective_date }} <span v-if="p.upcoming" class="badge bg-light text-dark border">예정</span></td>
              <td class="text-end text-nowrap">{{ won(p.unit_price) }}</td>
              <td class="text-end text-nowrap text-muted">{{ won(p.base_price) }}</td>
              <!-- 차이는 색만으로 구분하지 않고 +/− 기호와 숫자로 -->
              <td class="text-end text-nowrap">
                <template v-if="p.diff !== null">{{ signed(p.diff) }}원 <span class="text-muted">({{ p.diff_rate > 0 ? '+' : '' }}{{ p.diff_rate }}%)</span></template>
                <template v-else>-</template>
                <span v-if="p.low" class="badge badge-low ms-1" :title="`기준값보다 ${detail.low_alert_rate}% 이상 낮음 (할인 과다 점검)`">크게 낮음</span>
              </td>
              <td class="text-nowrap">{{ p.source }}<span v-if="p.quote_no" class="text-muted"> {{ p.quote_no }}</span></td>
              <td>{{ p.project || '-' }}</td>
              <td style="white-space: pre-line">{{ p.note || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-muted small mt-2 mb-0">기준값 대비는 견적 적용 시작일에 쓰이던 단가표(당시 기준값)로 계산합니다. "크게 낮음"은 기준값보다 {{ detail.low_alert_rate }}% 이상 낮은 견적입니다.
        흐린 줄은 같은 업체의 이전 단가(또는 적용 예정)라 평균·최저·최고 계산에서 빠집니다. 견적 단가는 출장 거리·작업 강도에 따라 달라질 수 있어 사업명·비고를 함께 보여 줍니다.</p>
    </div></div>
  </div>
</template>

<style scoped>
/* 뉴토크 기준값을 맨 앞 기준으로 눈에 띄게 (옅은 바탕) */
.col-standard,
.stat-standard {
  background: #f4f6f9;
}
.standard {
  background: #f4f6f9;
}
</style>
