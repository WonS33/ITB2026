<script setup>
// 금액 입력칸: 숫자만, 자동 콤마(1,234,567), 최대 15자리. 값은 숫자(원), 빈칸은 null
// (조원 저장소 entry/money-input.ts 규칙을 옮김)
import { computed, nextTick } from 'vue'

const MAX_DIGITS = 15
const model = defineModel({ type: Number, default: null })
defineProps({ id: String, disabled: Boolean, invalid: Boolean })

const shown = computed(() => (model.value === null ? '' : model.value.toLocaleString('ko-KR')))

function onInput(e) {
  const el = e.target
  // 커서 앞에 있던 숫자 개수 → 콤마를 다시 넣은 뒤에도 같은 숫자 뒤에 커서를 둔다
  const digitsBefore = el.value.slice(0, el.selectionStart).replace(/\D/g, '').length
  const digits = el.value.replace(/\D/g, '').replace(/^0+(?=\d)/, '').slice(0, MAX_DIGITS)
  model.value = digits === '' ? null : Number(digits)
  el.value = shown.value
  nextTick(() => {
    let seen = 0
    let pos = digitsBefore === 0 ? 0 : el.value.length
    for (let i = 0; i < el.value.length && digitsBefore > 0; i++) {
      if (/\d/.test(el.value[i])) seen++
      if (seen === digitsBefore) {
        pos = i + 1
        break
      }
    }
    el.setSelectionRange(pos, pos)
  })
}
</script>

<template>
  <div class="input-group">
    <input :id="id" type="text" inputmode="numeric" autocomplete="off" class="form-control text-end"
           :class="{ 'is-invalid': invalid }" :value="shown" :disabled="disabled" placeholder="0" @input="onInput" />
    <span class="input-group-text">원</span>
  </div>
</template>
