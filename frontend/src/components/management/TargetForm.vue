<script setup>
// 연간 목표 + 분기 목표(선택, 비우면 자동 배분) + 직원 수(선택). 빈 분기 자동 배분을 바로 미리 보여 주고, 합계가 안 맞으면 저장 전에 묻는다
// (조원 저장소 settings/target-form.tsx 를 옮김)
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getTarget, saveTarget } from '@/api/management'
import MoneyInput from '@/components/MoneyInput.vue'
import { TARGET_WARNINGS, allocateQuarterTargets } from '@/targets'

const thisYear = new Date().getFullYear()
const years = Array.from({ length: 6 }, (_, i) => thisYear + 1 - i) // 내년 목표도 미리 세울 수 있게
const year = ref(thisYear)
const data = ref(null)
const form = reactive({ annual: null, quarters: [null, null, null, null], headcount: '' })
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const conflict = ref(false)
const confirmWarning = ref(false)

const won = (v) => `${(v ?? 0).toLocaleString('ko-KR')}원`
const headcountValue = computed(() => (form.headcount === '' ? null : Number(form.headcount)))

function fill(d) {
  data.value = d
  form.annual = d.target_amount
  form.quarters = [...d.quarters]
  form.headcount = d.headcount === null ? '' : String(d.headcount)
}

const dirty = computed(() => {
  const d = data.value
  if (!d) return false
  return form.annual !== d.target_amount || form.quarters.some((q, i) => q !== d.quarters[i]) || headcountValue.value !== d.headcount
})

// 빈 분기 자동 배분 미리보기
const preview = computed(() => (form.annual > 0 ? allocateQuarterTargets(form.annual, form.quarters) : null))
const previewSum = computed(() => (preview.value ? preview.value.quarters.reduce((a, b) => a + b, 0) : 0))

async function load() {
  loading.value = true
  error.value = ''
  conflict.value = false
  try {
    fill(await getTarget(year.value))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function changeYear(y) {
  if (dirty.value && !window.confirm('저장하지 않은 변경이 있습니다. 다른 연도로 옮길까요?')) return
  year.value = y
  message.value = ''
  load()
}

function onHeadcount(e) {
  form.headcount = e.target.value.replace(/\D/g, '').slice(0, 4)
  e.target.value = form.headcount
}

function onSave() {
  if (preview.value?.warning) confirmWarning.value = true // 분기 합계가 안 맞으면 한 번 묻는다
  else save()
}

async function save() {
  confirmWarning.value = false
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const res = await saveTarget(year.value, {
      target_amount: form.annual ?? 0,
      quarters: form.quarters,
      headcount: headcountValue.value,
      expected_updated_at: data.value.updated_at,
    })
    fill(res)
    message.value = res.message
  } catch (e) {
    error.value = e.message
    conflict.value = e.status === 409
  } finally {
    saving.value = false
  }
}

onBeforeRouteLeave(() => !dirty.value || window.confirm('저장하지 않은 변경이 있습니다. 화면을 떠날까요?'))
const beforeUnload = (e) => { if (dirty.value) e.preventDefault() }
onMounted(() => { window.addEventListener('beforeunload', beforeUnload); load() })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<template>
  <div class="card">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
        <h2 class="h6 mb-0">{{ year }}년 목표</h2>
        <span v-if="data" class="text-muted small">({{ data.updated_at ? '설정됨' : '아직 설정되지 않음' }})</span>
        <select class="form-select form-select-sm w-auto ms-auto" aria-label="연도" :value="year" @change="changeYear(Number($event.target.value))">
          <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
        </select>
      </div>

      <div v-if="loading && !data" class="text-muted">불러오는 중…</div>
      <template v-else-if="data">
        <div class="row g-3 mb-3" style="max-width: 40rem">
          <div class="col-sm-7">
            <label for="target-annual" class="form-label mb-1">연간 목표매출액 <span class="text-danger small">(필수)</span></label>
            <MoneyInput id="target-annual" v-model="form.annual" />
          </div>
          <div class="col-sm-5">
            <label for="target-headcount" class="form-label mb-1">직원 수 <span class="text-muted small">(선택)</span></label>
            <div class="input-group">
              <input id="target-headcount" class="form-control text-end" inputmode="numeric" autocomplete="off"
                     :value="form.headcount" placeholder="선택" @input="onHeadcount" />
              <span class="input-group-text">명</span>
            </div>
          </div>
          <div class="col-12 form-text mt-1">직원 수는 인당 생산성(매출 ÷ 인원)에 씁니다. 비우면 표시하지 않습니다.</div>
        </div>

        <h3 class="h6 mb-1">분기 목표 <span class="text-muted small fw-normal">(선택 — 비우면 자동 배분)</span></h3>
        <div class="row g-2">
          <div v-for="(q, i) in form.quarters" :key="i" class="col-sm-6 col-xl-3">
            <div class="border rounded-3 p-2 h-100">
              <label :for="`target-q${i + 1}`" class="form-label small mb-1">{{ i + 1 }}분기</label>
              <MoneyInput :id="`target-q${i + 1}`" v-model="form.quarters[i]" />
              <div class="small mt-1">
                <template v-if="!preview"><span class="text-muted">연간 목표를 먼저 입력하세요</span></template>
                <template v-else-if="q === null"><span class="text-muted">자동 배분 {{ won(preview.quarters[i]) }}</span></template>
                <template v-else>직접 입력</template>
              </div>
            </div>
          </div>
        </div>
        <p class="form-text">빈 분기 = (연간 − 입력한 분기 합) ÷ 빈 분기 수, 나누어떨어지지 않는 원 단위는 마지막 빈 분기에 더합니다.</p>

        <div v-if="preview" class="alert py-2" :class="preview.warning ? 'alert-warning' : 'alert-light border'" role="status">
          분기 합계 <strong>{{ won(previewSum) }}</strong>
          <template v-if="preview.warning"> · {{ TARGET_WARNINGS[preview.warning] }}</template>
          <template v-else> = 연간 목표</template>
        </div>

        <div v-if="error" class="alert alert-danger py-2 d-flex align-items-center gap-2">
          <span>{{ error }}</span>
          <button v-if="conflict" type="button" class="btn btn-sm btn-outline-danger ms-auto" @click="load">최신 값 다시 불러오기</button>
        </div>
        <div v-if="message" class="alert alert-success py-2">{{ message }}</div>

        <div class="d-flex align-items-center gap-3">
          <button type="button" class="btn btn-primary" :disabled="saving || !dirty || !(form.annual > 0)" @click="onSave">
            {{ saving ? '저장 중…' : '저장' }}
          </button>
          <small v-if="dirty" class="text-warning-emphasis">저장하지 않은 변경 있음</small>
          <small v-if="data.updated_by" class="text-muted ms-auto">
            마지막 저장: {{ data.updated_by }} · {{ new Date(data.updated_at).toLocaleString('ko-KR') }}
          </small>
        </div>
      </template>
    </div>

    <!-- 분기 합계가 안 맞을 때 확인창 -->
    <template v-if="confirmWarning">
      <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="target-warn-title">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h2 id="target-warn-title" class="modal-title h5">분기 목표를 확인하세요</h2>
              <button type="button" class="btn-close" aria-label="닫기" @click="confirmWarning = false"></button>
            </div>
            <div class="modal-body">{{ TARGET_WARNINGS[preview.warning] }} 그대로 저장할까요?</div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline-secondary" @click="confirmWarning = false">돌아가기</button>
              <button type="button" class="btn btn-primary" @click="save">그대로 저장</button>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-backdrop show"></div>
    </template>
  </div>
</template>
