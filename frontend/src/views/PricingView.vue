<script setup>
// 제품 단가·원가 — 대표·관리자·경영지원팀만 (라우터 meta.fullAccess + 백엔드 API 권한)
// 1) 제품 단가표: 모델별 원재료 → 판매가 → 특별할인가 단계별 금액 (기업 계산표 재현)
// 2) 시뮬레이션: 환율·마진·옵션·원재료 기준을 바꿔 다시 계산 (저장하지 않음)
// 3) 커미션·이익: 계산표의 판매금액 기준 표 + 판매금액을 넣어 계산
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { calcCommission, getProductPrices } from '@/api/pricing'

const data = ref(null)
const error = ref('')
const series = ref('')
const opened = ref('') // 계산 과정을 펼친 모델
const sim = reactive({ exchange_rate: '', margin: '', option: '', base: 'assembly' })

async function load() {
  error.value = ''
  try {
    data.value = await getProductPrices(sim)
  } catch (e) {
    error.value = e.message
  }
}
onMounted(load)
// 숫자를 입력하는 동안 매번 부르지 않도록 잠깐 기다렸다가 다시 계산
let timer
watch(sim, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
}, { deep: true })
const resetSim = () => Object.assign(sim, { exchange_rate: '', margin: '', option: '', base: 'assembly' })

const models = computed(() => (data.value?.models ?? []).filter((m) => !series.value || m.series === series.value))
const won = (v) => (v === null || v === undefined ? '-' : `${Math.round(v).toLocaleString()}원`)
const signed = (v) => (v > 0 ? `▲ ${v.toLocaleString()}` : v < 0 ? `▼ ${(-v).toLocaleString()}` : '–')
const pct = (v) => `${v}%`

// 계산 과정 설명 (모델 줄을 누르면 펼침)
function explain(m) {
  const s = data.value.setting
  const r = data.value.simulation
  const option = data.value.options.find((o) => o.name === r.option)
  return [
    ['원화 환산', `${m.usd.toLocaleString()} USD × 환율 ${r.exchange_rate.toLocaleString()}`, m.steps.krw],
    ['옵션 반영', option ? `+ ${option.name} ${option.price_usd} USD × 환율` : '옵션 없음', m.steps.with_option],
    ['통관', `× ${s.customs_factor}`, m.steps.customs],
    ['원가(판관비 반영)', `× (1 + ${pct(s.sga_rate)})`, m.steps.cost],
    ['마진 반영', `÷ ${r.margin}`, m.steps.margin_price],
    ['판매가', `${s.price_round_unit.toLocaleString()}원 단위 올림`, m.steps.sale_price],
    ['특별할인가', `× (1 − ${pct(s.special_discount_rate)}), ${s.price_round_unit.toLocaleString()}원 단위 올림`, m.steps.special_price],
  ]
}

// 커미션 계산기
const calc = reactive({ model: '', sale_amount: '', result: null, error: '' })
async function runCalc() {
  calc.error = ''
  calc.result = null
  try {
    calc.result = await calcCommission(calc.model, calc.sale_amount)
  } catch (e) {
    calc.error = e.message
  }
}
</script>

<template>
  <div class="pb-5">
    <h1 class="page-title mb-1">제품 단가·원가</h1>
    <p class="text-muted small mb-4">대표·관리자·경영지원팀만 볼 수 있는 대외비 자료입니다. 화면을 캡처하거나 외부로 보내지 마세요.</p>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <!-- 기준값 -->
      <div class="card mb-3"><div class="card-body small">
        <h2 class="h6">가격 계산 기준값 <span class="text-muted fw-normal">· {{ data.setting.effective_date }} 적용 (임시 기준일)</span></h2>
        <div class="d-flex flex-wrap gap-4">
          <span>환율 <strong>{{ data.setting.exchange_rate.toLocaleString() }}원/USD</strong></span>
          <span>통관 배수 <strong>× {{ data.setting.customs_factor }}</strong></span>
          <span>판관비 <strong>{{ pct(data.setting.sga_rate) }}</strong></span>
          <span>마진 <strong>÷ {{ data.setting.margin }}</strong></span>
          <span>특별할인 <strong>{{ pct(data.setting.special_discount_rate) }}</strong></span>
          <span>커미션 <strong>{{ pct(data.setting.commission_rate) }}</strong> ({{ data.setting.commission_unit.toLocaleString() }}원 미만 버림)</span>
        </div>
      </div></div>

      <!-- 시뮬레이션 -->
      <div class="card mb-3" :class="{ 'border-warning': data.simulation.active }"><div class="card-body small">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <h2 class="h6 mb-0">가격 시뮬레이션</h2>
          <span v-if="data.simulation.active" class="badge bg-warning text-dark">시뮬레이션 중 — 저장되지 않음</span>
          <button v-if="data.simulation.active" type="button" class="btn btn-link btn-sm p-0" @click="resetSim">기준값으로 되돌리기</button>
        </div>
        <div class="d-flex flex-wrap align-items-end gap-3">
          <label class="d-flex flex-column">환율(원/USD)
            <input v-model="sim.exchange_rate" type="number" min="1" step="1" class="form-control form-control-sm" style="width: 130px"
                   :placeholder="String(data.setting.exchange_rate)" />
          </label>
          <label class="d-flex flex-column">마진 값(나누는 수)
            <select v-model="sim.margin" class="form-select form-select-sm" style="width: 130px">
              <option value="">기준 {{ data.setting.margin }}</option>
              <option v-for="m in data.margin_choices" :key="m" :value="m">{{ m }}</option>
            </select>
          </label>
          <label class="d-flex flex-column">옵션
            <select v-model="sim.option" class="form-select form-select-sm" style="width: 150px">
              <option value="">옵션 없음</option>
              <option v-for="o in data.options" :key="o.name" :value="o.name">{{ o.name }} (+{{ o.price_usd }} USD)</option>
            </select>
          </label>
          <div class="d-flex flex-column">원재료 기준
            <div class="btn-group btn-group-sm" role="group" aria-label="원재료 기준">
              <button v-for="[v, label] in [['assembly', 'Assembly'], ['complete', 'Complete']]" :key="v" type="button" class="btn"
                      :class="sim.base === v ? 'btn-secondary' : 'btn-outline-secondary'" :aria-pressed="sim.base === v" @click="sim.base = v">{{ label }}</button>
            </div>
          </div>
        </div>
        <p class="text-muted mt-2 mb-0">값을 바꾸면 아래 단가표가 바로 다시 계산되고 "기준 대비" 열에 판매가 차이가 나옵니다. 옵션은 USD로 원재료에 더한다고 가정했습니다(확인 필요).</p>
      </div></div>

      <!-- 제품 단가표 -->
      <div class="card mb-3"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
          <h2 class="h6 mb-0">제품 단가표 <span class="text-muted fw-normal small">· {{ models.length }}개 모델, 줄을 누르면 계산 과정</span></h2>
          <div class="btn-group btn-group-sm" role="group" aria-label="시리즈">
            <button v-for="s in ['', ...data.series]" :key="s" type="button" class="btn"
                    :class="series === s ? 'btn-secondary' : 'btn-outline-secondary'" @click="series = s">{{ s || '전체' }}</button>
          </div>
        </div>
        <div class="table-responsive">
          <table class="table table-sm table-hover small mb-0 align-middle">
            <thead class="table-light">
              <tr>
                <th>모델</th>
                <th class="text-end">원재료(USD)</th>
                <th class="text-end">원화(옵션 포함)</th>
                <th class="text-end">통관</th>
                <th class="text-end">원가</th>
                <th class="text-end">마진 반영</th>
                <th class="text-end">판매가</th>
                <th class="text-end">특별할인가</th>
                <th v-if="data.simulation.active" class="text-end">기준 대비</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="m in models" :key="m.model_name">
                <tr role="button" :class="{ 'table-primary': opened === m.model_name }" @click="opened = opened === m.model_name ? '' : m.model_name">
                  <td class="fw-semibold text-nowrap">{{ m.model_name }}</td>
                  <template v-if="m.steps">
                    <td class="text-end">{{ m.usd.toLocaleString() }}</td>
                    <td class="text-end text-nowrap">{{ won(m.steps.with_option) }}</td>
                    <td class="text-end text-nowrap">{{ won(m.steps.customs) }}</td>
                    <td class="text-end text-nowrap">{{ won(m.steps.cost) }}</td>
                    <td class="text-end text-nowrap">{{ won(m.steps.margin_price) }}</td>
                    <td class="text-end text-nowrap fw-semibold">{{ won(m.steps.sale_price) }}</td>
                    <td class="text-end text-nowrap">{{ won(m.steps.special_price) }}</td>
                    <td v-if="data.simulation.active" class="text-end text-nowrap" :class="{ 'text-muted': !m.change }">{{ signed(m.change) }}</td>
                  </template>
                  <td v-else :colspan="data.simulation.active ? 8 : 7" class="text-muted">Complete 원재료 가격이 없어 계산할 수 없습니다.</td>
                </tr>
                <tr v-if="opened === m.model_name && m.steps" class="detail-row">
                  <td :colspan="data.simulation.active ? 9 : 8">
                    <ol class="mb-0 small ps-3">
                      <li v-for="[label, how, value] in explain(m)" :key="label">
                        {{ label }}: <span class="text-muted">{{ how }}</span> = <strong>{{ won(value) }}</strong>
                      </li>
                    </ol>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <p class="text-muted small mt-2 mb-0">
          원가 = 통관 후 금액에 판관비를 더한 값, 마진 반영 = 원가 ÷ 마진 값. 중간 금액은 원 단위 반올림으로 보여 주고, 판매가·특별할인가는 계산표와 같이 천원 단위로 올립니다.
          가져올 때 계산표의 모든 금액과 다시 계산한 금액이 같은지 확인했습니다.
        </p>
      </div></div>

      <!-- 커미션·이익 -->
      <div class="card mb-3"><div class="card-body">
        <h2 class="h6">커미션·이익 <span class="text-muted fw-normal small">· 현재 기준값, 계산표에 판매금액이 있는 모델</span></h2>
        <div class="table-responsive">
          <table class="table table-sm small mb-3 align-middle">
            <thead class="table-light">
              <tr>
                <th>모델</th><th class="text-end">판매금액</th><th class="text-end">원가(마진 반영)</th><th class="text-end">이익</th>
                <th class="text-end">커미션</th><th class="text-end">커미션 차감 이익</th><th class="text-end">마진율 <span class="badge bg-light text-dark border">제안</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in data.commissions" :key="c.model_name">
                <td class="fw-semibold">{{ c.model_name }}</td>
                <td class="text-end">{{ won(c.sale_amount) }}</td>
                <td class="text-end">{{ won(c.supply_price) }}</td>
                <td class="text-end">{{ won(c.profit) }}</td>
                <td class="text-end">{{ won(c.commission) }}</td>
                <td class="text-end fw-semibold">{{ won(c.net_profit) }}</td>
                <td class="text-end">{{ c.margin_rate }}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 판매금액을 넣어 계산 -->
        <form class="d-flex flex-wrap align-items-end gap-2 small" @submit.prevent="runCalc">
          <label class="d-flex flex-column">모델
            <select v-model="calc.model" class="form-select form-select-sm" style="width: 140px" required>
              <option value="">선택</option>
              <option v-for="m in data.models" :key="m.model_name" :value="m.model_name">{{ m.model_name }}</option>
            </select>
          </label>
          <label class="d-flex flex-column">판매금액(원)
            <input v-model="calc.sale_amount" type="number" min="1" step="1" class="form-control form-control-sm" style="width: 160px" required />
          </label>
          <button class="btn btn-primary btn-sm">계산</button>
          <span v-if="calc.error" class="text-danger">{{ calc.error }}</span>
        </form>
        <div v-if="calc.result" class="d-flex flex-wrap gap-4 small mt-2 p-2 rounded calc-result">
          <span>이익 <strong>{{ won(calc.result.profit) }}</strong></span>
          <span>커미션 <strong>{{ won(calc.result.commission) }}</strong></span>
          <span>커미션 차감 이익 <strong>{{ won(calc.result.net_profit) }}</strong></span>
          <span>마진율 <strong>{{ calc.result.margin_rate }}%</strong></span>
        </div>
        <p class="text-muted small mt-2 mb-0">
          이익 = 판매금액 − 원가(마진 반영), 커미션 = 판매금액 × {{ pct(data.setting.commission_rate) }}({{ data.setting.commission_unit.toLocaleString() }}원 미만 버림),
          마진율 = 커미션 차감 이익 ÷ 판매금액 (계산표에 빈칸이라 임시 정의 — 확인 필요).
        </p>
      </div></div>
    </template>
  </div>
</template>

<style scoped>
.detail-row > td,
.calc-result {
  background: #f7f8fa;
}
</style>
