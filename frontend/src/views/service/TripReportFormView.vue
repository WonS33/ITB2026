<script setup>
// 출장보고서 직접 입력 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
// 검사·중복 기준은 PDF 업로드와 같다 (backend/service/trip_input.py). 구역 순서는 출장보고서 양식을 따른다.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { createTripReport, getPartPrices, getRequesterRegions } from '@/api/service'
import { refreshYearRange } from '@/period'

const PAID_TYPES = ['유상', '무상']

function emptyForm() {
  return {
    start_date: '', end_date: '', extra_trip: '', requester_type: '', requester: '', region: '', district: '',
    author: '', work_type: '', purpose: '', paid_type: '',
    fault_description: '', work_description: '', work_result: '',
    companions: [''],
    products: [{ model_name: '', spec: '', serial_no_raw: '', quantity: '1' }],
    parts: [''],
  }
}

const form = reactive(emptyForm())
const errors = ref({})
const duplicate = ref(null) // 409 응답: 같은 시작일·요청처 보고서 목록
const allowDuplicate = ref(false)
const saved = ref(null) // 방금 저장한 보고서
const submitting = ref(false)
const dirty = ref(false) // 저장하지 않은 입력이 있는지

// 선택 목록·추천 목록 (요청처 대응표, 시·도·시·군, 이미 쓰인 부품명)
const regions = ref([])
const districts = ref({})
const knownRequesters = ref({}) // 요청처 → { region, district }
const partNames = ref([])
const loadError = ref('')

onMounted(async () => {
  try {
    const [map, prices] = await Promise.all([getRequesterRegions(), getPartPrices()])
    regions.value = map.regions
    districts.value = map.districts
    knownRequesters.value = Object.fromEntries(map.results.map((r) => [r.requester, r]))
    partNames.value = prices.part_names
  } catch (e) {
    loadError.value = e.message
  }
})

const districtOptions = computed(() => districts.value[form.region] || [])
const remembered = computed(() => knownRequesters.value[form.requester.trim()])

// 아는 요청처를 고르면 시·도·시·군을 자동으로 채운다
function onRequesterChange() {
  if (remembered.value) {
    form.region = remembered.value.region
    form.district = remembered.value.district
  }
}
// 시·도를 바꿔서 기존 시·군이 새 목록에 없으면 비운다
function onRegionChange() {
  if (!districtOptions.value.includes(form.district)) form.district = ''
}

// 출장 시작일·요청처를 고치면 중복 경고는 다시 확인해야 하므로 지운다
watch(() => [form.start_date, form.requester], () => (duplicate.value = null))

const addRow = (key, row) => form[key].push(row)
function removeRow(key, index, blank) {
  form[key].splice(index, 1)
  if (!form[key].length) form[key].push(blank)
}

async function submit() {
  errors.value = {}
  saved.value = null
  submitting.value = true
  try {
    const report = await createTripReport({ ...form, allow_duplicate: duplicate.value ? allowDuplicate.value : false })
    saved.value = report
    refreshYearRange() // 이전 연도 보고서를 입력했으면 기간 선택 연도 목록에 반영
    Object.assign(form, emptyForm())
    duplicate.value = null
    allowDuplicate.value = false
    dirty.value = false
    if (!knownRequesters.value[report.requester]) {
      knownRequesters.value[report.requester] = { region: report.region, district: report.district }
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    if (e.status === 409) {
      duplicate.value = e.data
      allowDuplicate.value = false
    } else {
      errors.value = e.data && typeof e.data === 'object' ? e.data : { detail: e.message }
    }
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  if (dirty.value && !confirm('입력한 내용을 모두 지울까요?')) return
  Object.assign(form, emptyForm())
  errors.value = {}
  duplicate.value = null
  dirty.value = false
}

// 저장하지 않은 입력이 있으면 화면을 떠날 때 한 번 묻는다
onBeforeRouteLeave(() => !dirty.value || confirm('저장하지 않은 입력이 있습니다. 화면을 떠날까요?'))
const beforeUnload = (e) => {
  if (dirty.value) e.preventDefault()
}
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

const invalid = (key) => ({ 'is-invalid': errors.value[key] })
</script>

<template>
  <div>
    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>
    <div v-if="saved" class="alert alert-success d-flex flex-wrap align-items-center gap-2">
      <span>{{ saved.start_date }} · {{ saved.requester }} 출장보고서를 저장했습니다.</span>
      <RouterLink to="/service/reports" class="alert-link">목록에서 보기</RouterLink>
      <span class="text-muted small">아래에서 다음 보고서를 이어서 입력할 수 있습니다.</span>
    </div>

    <form class="card" novalidate @submit.prevent="submit" @input="dirty = true" @change="dirty = true">
      <div class="card-body">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-1">
          <h2 class="h6 mb-0">출장보고서 직접 입력</h2>
          <span class="text-muted small"><span class="text-danger">*</span> 필수</span>
        </div>
        <p class="text-muted small">PDF가 없는 출장보고서를 입력합니다. 검사 규칙과 중복 기준(출장 시작일 + 요청처)은 PDF 업로드와 같습니다.</p>

        <!-- 출장정보 -->
        <h3 class="form-section">출장정보</h3>
        <div class="row g-2 mb-3">
          <div class="col-6 col-md-3">
            <label class="form-label" for="start">출장 시작일 <span class="text-danger">*</span></label>
            <input id="start" v-model="form.start_date" type="date" class="form-control form-control-sm" :class="invalid('start_date')" />
            <div class="invalid-feedback">{{ errors.start_date }}</div>
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label" for="end">출장 종료일</label>
            <input id="end" v-model="form.end_date" type="date" class="form-control form-control-sm" :class="invalid('end_date')" />
            <div class="invalid-feedback">{{ errors.end_date }}</div>
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label" for="extra">추가 출장</label>
            <input id="extra" v-model="form.extra_trip" class="form-control form-control-sm" placeholder="예: 없음" :class="invalid('extra_trip')" />
            <div class="invalid-feedback">{{ errors.extra_trip }}</div>
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label" for="author">작성자 <span class="text-danger">*</span></label>
            <input id="author" v-model="form.author" class="form-control form-control-sm" placeholder="예: 홍길동 대리" :class="invalid('author')" />
            <div class="invalid-feedback">{{ errors.author }}</div>
          </div>

          <div class="col-md-3">
            <label class="form-label" for="reqtype">요청처 구분</label>
            <input id="reqtype" v-model="form.requester_type" class="form-control form-control-sm" placeholder="예: 검색 불가" :class="invalid('requester_type')" />
            <div class="invalid-feedback">{{ errors.requester_type }}</div>
          </div>
          <div class="col-md-3">
            <label class="form-label" for="requester">요청처 <span class="text-danger">*</span></label>
            <input id="requester" v-model="form.requester" list="requester-list" class="form-control form-control-sm"
                   :class="invalid('requester')" @change="onRequesterChange" />
            <datalist id="requester-list">
              <option v-for="name in Object.keys(knownRequesters)" :key="name" :value="name" />
            </datalist>
            <div class="invalid-feedback">{{ errors.requester }}</div>
            <div v-if="remembered" class="form-text">등록된 요청처 — 지역을 자동으로 채웠습니다.</div>
            <div v-else-if="form.requester.trim()" class="form-text">새 요청처 — 저장하면 고른 지역을 기억합니다.</div>
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label" for="region">시·도 <span class="text-danger">*</span></label>
            <select id="region" v-model="form.region" class="form-select form-select-sm" :class="invalid('region')" @change="onRegionChange">
              <option value="">선택</option>
              <option v-for="name in regions" :key="name" :value="name">{{ name }}</option>
            </select>
            <div class="invalid-feedback">{{ errors.region }}</div>
          </div>
          <div class="col-6 col-md-3">
            <label class="form-label" for="district">시·군 <span v-if="districtOptions.length" class="text-danger">*</span></label>
            <select id="district" v-model="form.district" class="form-select form-select-sm" :class="invalid('district')"
                    :disabled="!districtOptions.length">
              <option value="">{{ districtOptions.length ? '선택' : form.region ? '없음 (시 전체)' : '시·도 먼저 선택' }}</option>
              <option v-for="name in districtOptions" :key="name" :value="name">{{ name }}</option>
            </select>
            <div class="invalid-feedback">{{ errors.district }}</div>
          </div>

          <div class="col-12">
            <label class="form-label">동행자</label>
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <div v-for="(name, i) in form.companions" :key="i" class="input-group input-group-sm" style="width: 13rem">
                <input v-model="form.companions[i]" class="form-control" :aria-label="`동행자 ${i + 1}`" placeholder="이름" />
                <button type="button" class="btn btn-outline-secondary" :aria-label="`동행자 ${i + 1} 삭제`" @click="removeRow('companions', i, '')">×</button>
              </div>
              <button type="button" class="btn btn-outline-primary btn-sm" @click="addRow('companions', '')">+ 동행자</button>
            </div>
            <div v-if="errors.companions" class="text-danger small mt-1">{{ errors.companions }}</div>
          </div>
        </div>

        <!-- 작업 개요 -->
        <h3 class="form-section">작업 개요</h3>
        <div class="row g-2 mb-3">
          <div class="col-md-3">
            <label class="form-label" for="worktype">작업 구분</label>
            <input id="worktype" v-model="form.work_type" class="form-control form-control-sm" placeholder="예: 수리" :class="invalid('work_type')" />
            <div class="invalid-feedback">{{ errors.work_type }}</div>
          </div>
          <div class="col-md-9">
            <label class="form-label" for="purpose">출장 목적</label>
            <input id="purpose" v-model="form.purpose" class="form-control form-control-sm" :class="invalid('purpose')" />
            <div class="invalid-feedback">{{ errors.purpose }}</div>
          </div>
        </div>

        <!-- 제품 목록 -->
        <h3 class="form-section">제품 목록</h3>
        <div class="table-responsive mb-1">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr class="small text-muted"><th>모델명</th><th>사양</th><th>일련번호</th><th style="width: 6rem">수량</th><th style="width: 3rem"></th></tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in form.products" :key="i">
                <td><input v-model="p.model_name" class="form-control form-control-sm" :aria-label="`제품 ${i + 1} 모델명`" placeholder="예: AVA03" /></td>
                <td><input v-model="p.spec" class="form-control form-control-sm" :aria-label="`제품 ${i + 1} 사양`" placeholder="예: 380V/3Ph/60Hz" /></td>
                <td><input v-model="p.serial_no_raw" class="form-control form-control-sm" :aria-label="`제품 ${i + 1} 일련번호`" /></td>
                <td><input v-model="p.quantity" type="number" min="1" step="1" class="form-control form-control-sm" :aria-label="`제품 ${i + 1} 수량`" /></td>
                <td>
                  <button type="button" class="btn btn-outline-secondary btn-sm" :aria-label="`제품 ${i + 1} 삭제`"
                          @click="removeRow('products', i, { model_name: '', spec: '', serial_no_raw: '', quantity: '1' })">×</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="errors.products" class="text-danger small mb-1">{{ errors.products }}</div>
        <button type="button" class="btn btn-outline-primary btn-sm mb-3"
                @click="addRow('products', { model_name: '', spec: '', serial_no_raw: '', quantity: '1' })">+ 제품</button>
        <p class="text-muted small mt-n2">모델명을 비운 줄은 저장하지 않습니다.</p>

        <!-- 수리 내역 -->
        <h3 class="form-section">수리 내역</h3>
        <div class="row g-2 mb-2">
          <div class="col-md-4">
            <label class="form-label" for="fault">고장 내용</label>
            <textarea id="fault" v-model="form.fault_description" rows="4" class="form-control form-control-sm"></textarea>
          </div>
          <div class="col-md-4">
            <label class="form-label" for="work">작업 내용</label>
            <textarea id="work" v-model="form.work_description" rows="4" class="form-control form-control-sm"></textarea>
          </div>
          <div class="col-md-4">
            <label class="form-label" for="result">작업 결과</label>
            <textarea id="result" v-model="form.work_result" rows="4" class="form-control form-control-sm"></textarea>
          </div>
        </div>
        <label class="form-label">교체 부품 <span class="text-muted small fw-normal">· 추천 목록의 이름을 쓰면 부품 단가와 연결됩니다</span></label>
        <div class="d-flex flex-wrap gap-2 align-items-center mb-1">
          <div v-for="(name, i) in form.parts" :key="i" class="input-group input-group-sm" style="width: 17rem">
            <input v-model="form.parts[i]" list="part-list" class="form-control" :aria-label="`교체 부품 ${i + 1}`" placeholder="부품명" />
            <button type="button" class="btn btn-outline-secondary" :aria-label="`교체 부품 ${i + 1} 삭제`" @click="removeRow('parts', i, '')">×</button>
          </div>
          <button type="button" class="btn btn-outline-primary btn-sm" @click="addRow('parts', '')">+ 부품</button>
        </div>
        <datalist id="part-list">
          <option v-for="name in partNames" :key="name" :value="name" />
        </datalist>
        <div v-if="errors.parts" class="text-danger small">{{ errors.parts }}</div>

        <!-- 비고 -->
        <h3 class="form-section mt-3">비고</h3>
        <fieldset class="mb-3">
          <legend class="form-label fs-6">비용청구 유무 <span class="text-danger">*</span></legend>
          <div class="d-flex gap-3">
            <div v-for="t in PAID_TYPES" :key="t" class="form-check">
              <input :id="`paid-${t}`" v-model="form.paid_type" class="form-check-input" :class="invalid('paid_type')" type="radio" :value="t" />
              <label class="form-check-label" :for="`paid-${t}`">{{ t }}</label>
            </div>
          </div>
          <div v-if="errors.paid_type" class="text-danger small">{{ errors.paid_type }}</div>
        </fieldset>

        <!-- 중복 의심: 같은 시작일·요청처 보고서가 이미 있음 -->
        <div v-if="duplicate" class="alert alert-warning">
          <div class="mb-1">{{ duplicate.detail }}</div>
          <ul class="small mb-2">
            <li v-for="r in duplicate.existing" :key="r.id">{{ r.start_date }} · {{ r.requester }} · 작성자 {{ r.author }}</li>
          </ul>
          <div class="form-check">
            <input id="allow-dup" v-model="allowDuplicate" type="checkbox" class="form-check-input" />
            <label for="allow-dup" class="form-check-label">중복 아님 — 같은 곳에 실제로 한 번 더 간 출장입니다</label>
          </div>
        </div>

        <div v-if="errors.detail" class="alert alert-danger py-2">{{ errors.detail }}</div>
        <div v-if="Object.keys(errors).length && !errors.detail" class="text-danger small mb-2">빨간 칸을 고친 뒤 다시 저장해 주세요.</div>
        <div class="d-flex gap-2">
          <button class="btn btn-primary" :disabled="submitting || (duplicate && !allowDuplicate)">저장</button>
          <button type="button" class="btn btn-outline-secondary" @click="resetForm">입력 지우기</button>
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.form-section {
  font-size: 0.9rem;
  font-weight: 700;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 0.25rem;
  margin-bottom: 0.75rem;
}
.form-label {
  font-size: 0.85rem;
  margin-bottom: 0.2rem;
}
</style>
