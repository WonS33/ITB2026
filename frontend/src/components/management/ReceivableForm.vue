<script setup>
// 미수금 등록·수정·수금 처리 폼 (모달). mode: create / edit / collect
// 날짜 규칙: 발생일은 오늘 이후 불가, 수금 예정일은 발생일 이후, 수금일은 오늘 이후 불가·발생일 이후 (서버에서도 다시 확인)
import { computed, reactive, ref } from 'vue'
import { createReceivable, receivableAction, updateReceivable } from '@/api/management'
import MoneyInput from '@/components/MoneyInput.vue'
import { won } from '@/money'

const props = defineProps({
  mode: { type: String, required: true },
  row: { type: Object, default: null },
  today: { type: String, required: true }, // YYYY-MM-DD
  customerNames: { type: Array, default: () => [] },
})
const emit = defineEmits(['done', 'close'])

const form = reactive({
  customer_name: props.row?.customer_name ?? '',
  occurred_on: props.row?.occurred_on ?? props.today,
  amount: props.row?.amount ?? null,
  due_on: props.row?.due_on ?? '',
  collected_on: props.mode === 'collect' ? props.today : props.row?.collected_on ?? '',
  note: props.row?.note ?? '',
})
const submitted = ref(false)
const saving = ref(false)
const error = ref('')
const conflict = ref(false)
const collected = computed(() => props.mode === 'edit' && props.row?.is_collected)

// 저장을 한 번 누른 뒤부터 오류를 보인다
const errors = computed(() => {
  const e = {}
  if (props.mode !== 'collect') {
    if (!form.customer_name.trim()) e.customer_name = '거래처를 입력하세요.'
    if (!form.amount) e.amount = '금액을 입력하세요.'
    if (!form.occurred_on) e.occurred_on = '발생일을 입력하세요.'
    else if (form.occurred_on > props.today) e.occurred_on = '발생일은 오늘 이후로 입력할 수 없습니다.'
    if (form.due_on && form.occurred_on && form.due_on < form.occurred_on) e.due_on = '수금 예정일은 발생일보다 이를 수 없습니다.'
  }
  if (props.mode === 'collect' || collected.value) {
    if (!form.collected_on) e.collected_on = '수금일을 입력하세요.'
    else if (form.collected_on > props.today) e.collected_on = '미래 날짜로 수금 처리할 수 없습니다.'
    else if (form.collected_on < form.occurred_on) e.collected_on = '수금일은 발생일보다 이를 수 없습니다.'
  }
  return e
})
const shown = computed(() => (submitted.value ? errors.value : {}))

async function submit() {
  submitted.value = true
  if (Object.keys(errors.value).length) return
  saving.value = true
  error.value = ''
  try {
    const fields = {
      customer_name: form.customer_name,
      occurred_on: form.occurred_on,
      amount: form.amount,
      due_on: form.due_on || null,
      note: form.note,
    }
    let res
    if (props.mode === 'create') res = await createReceivable(fields)
    else if (props.mode === 'edit') {
      res = await updateReceivable(props.row.id, {
        ...fields,
        collected_on: collected.value ? form.collected_on : null,
        expected_updated_at: props.row.updated_at,
      })
    } else {
      res = await receivableAction(props.row.id, 'collect', { collected_on: form.collected_on, expected_updated_at: props.row.updated_at })
    }
    emit('done', res.message)
  } catch (e) {
    error.value = e.message
    conflict.value = e.status === 409
  } finally {
    saving.value = false
  }
}

const TITLES = { create: '미수금 등록', edit: '미수금 수정', collect: '수금 처리' }
</script>

<template>
  <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="rcv-form-title">
    <div class="modal-dialog modal-dialog-centered">
      <form class="modal-content" novalidate @submit.prevent="submit">
        <div class="modal-header">
          <h2 id="rcv-form-title" class="modal-title h5">{{ TITLES[mode] }}</h2>
          <button type="button" class="btn-close" aria-label="닫기" @click="emit('close')"></button>
        </div>
        <div class="modal-body">
          <!-- 수금 처리: 건 정보 + 수금일만 -->
          <template v-if="mode === 'collect'">
            <dl class="row small mb-3">
              <dt class="col-3 text-muted fw-normal">거래처</dt><dd class="col-9 mb-1">{{ row.customer_name }}</dd>
              <dt class="col-3 text-muted fw-normal">금액</dt><dd class="col-9 mb-1">{{ won(row.amount) }}</dd>
              <dt class="col-3 text-muted fw-normal">발생일</dt><dd class="col-9 mb-0">{{ row.occurred_on }}</dd>
            </dl>
          </template>
          <template v-else>
            <div class="mb-3">
              <label for="rcv-customer" class="form-label">거래처 <span class="text-danger">*</span></label>
              <input id="rcv-customer" v-model="form.customer_name" class="form-control" :class="{ 'is-invalid': shown.customer_name }"
                     list="rcv-customer-names" autocomplete="off" maxlength="60" placeholder="기존 거래처는 입력하면 목록이 나옵니다" />
              <datalist id="rcv-customer-names"><option v-for="n in customerNames" :key="n" :value="n" /></datalist>
              <div class="invalid-feedback">{{ shown.customer_name }}</div>
            </div>
            <div class="row g-3 mb-3">
              <div class="col-sm-6">
                <label for="rcv-occurred" class="form-label">발생일 <span class="text-danger">*</span></label>
                <input id="rcv-occurred" v-model="form.occurred_on" type="date" :max="today" class="form-control" :class="{ 'is-invalid': shown.occurred_on }" />
                <div class="invalid-feedback">{{ shown.occurred_on }}</div>
              </div>
              <div class="col-sm-6">
                <label for="rcv-amount" class="form-label">금액 <span class="text-danger">*</span></label>
                <MoneyInput id="rcv-amount" v-model="form.amount" :invalid="!!shown.amount" />
                <div v-if="shown.amount" class="text-danger small mt-1">{{ shown.amount }}</div>
              </div>
              <div class="col-sm-6">
                <label for="rcv-due" class="form-label">수금 예정일</label>
                <input id="rcv-due" v-model="form.due_on" type="date" :min="form.occurred_on" class="form-control" :class="{ 'is-invalid': shown.due_on }" />
                <div class="invalid-feedback">{{ shown.due_on }}</div>
              </div>
            </div>
            <div class="mb-2">
              <label for="rcv-note" class="form-label">비고</label>
              <textarea id="rcv-note" v-model="form.note" rows="2" maxlength="200" class="form-control"></textarea>
            </div>
          </template>
          <div v-if="mode === 'collect' || collected" class="mb-2">
            <label for="rcv-collected" class="form-label">수금일 <span class="text-danger">*</span></label>
            <input id="rcv-collected" v-model="form.collected_on" type="date" :min="form.occurred_on" :max="today" class="form-control" :class="{ 'is-invalid': shown.collected_on }" />
            <div class="invalid-feedback">{{ shown.collected_on }}</div>
            <div v-if="mode === 'collect'" class="form-text">부분 수금은 지원하지 않습니다. 나눠 받으면 받은 금액만큼 수금 처리하고, 남은 금액은 새 건으로 등록하세요.</div>
          </div>
          <div v-if="error" class="alert alert-danger py-2 mt-2 mb-0">{{ error }}<template v-if="conflict"> 창을 닫고 목록을 다시 불러오세요.</template></div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" @click="emit('close')">취소</button>
          <button type="submit" class="btn btn-primary" :disabled="saving">{{ saving ? '저장 중…' : { create: '등록', edit: '수정 저장', collect: '수금 처리' }[mode] }}</button>
        </div>
      </form>
    </div>
  </div>
  <div class="modal-backdrop show"></div>
</template>
