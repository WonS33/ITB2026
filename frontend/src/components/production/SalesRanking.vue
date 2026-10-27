<script setup>
// 판매 순위 표: 이름 · 수량 막대 · 수량(비중) · 비교 기간 대비 증감
// 줄을 누르면 select(이름)을 알린다 → 판매 실적 화면이 그 이름으로 다른 순위를 좁힌다(교차 필터)
import { computed } from 'vue'
import { percent } from '@/charts'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity, previous, change }] (많은 순서)
  total: { type: Number, required: true },
  selected: { type: String, default: '' }, // 지금 걸러 보는 이름
  colorOf: { type: Function, default: null }, // 이름별 고정 색 (없으면 중립 회청색)
  limit: { type: Number, default: 10 },
  compareLabel: { type: String, default: '' }, // 비교 기간 이름 (없으면 증감 열 숨김)
})
const emit = defineEmits(['select'])

const shown = computed(() => props.items.slice(0, props.limit))
const max = computed(() => Math.max(1, ...shown.value.map((i) => i.quantity)))
// 증감은 색만으로 구분하지 않도록 ▲▼ 기호와 +/− 숫자를 함께
const changeText = (c) => (c > 0 ? `▲ ${c}` : c < 0 ? `▼ ${-c}` : '–')
</script>

<template>
  <div>
    <p v-if="!items.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <template v-else>
      <table class="table table-sm table-hover small align-middle mb-0">
        <thead>
          <tr>
            <th>이름</th>
            <th style="width: 34%">판매량</th>
            <th class="text-end">대수</th>
            <th v-if="compareLabel" class="text-end text-nowrap" :title="`${compareLabel} 대비`">증감</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="i in shown"
            :key="i.name"
            role="button"
            :class="{ 'table-active fw-semibold': i.name === selected }"
            :aria-pressed="i.name === selected"
            :title="i.name === selected ? '다시 누르면 걸러내기 해제' : '누르면 이 항목으로 다른 순위를 좁혀 봄'"
            @click="emit('select', i.name)"
          >
            <td class="text-break">
              <span v-if="colorOf" class="d-inline-block rounded-circle me-1 align-middle" :style="{ width: '8px', height: '8px', background: colorOf(i.name) }"></span>
              {{ i.name }}
            </td>
            <td>
              <div class="bar" :style="{ width: `${(i.quantity / max) * 100}%`, background: colorOf ? colorOf(i.name) : '#9aa9bd' }"></div>
            </td>
            <td class="text-end text-nowrap">{{ i.quantity.toLocaleString() }} <span class="text-muted">({{ percent(i.quantity, total) }}%)</span></td>
            <td v-if="compareLabel" class="text-end text-nowrap" :class="{ 'text-muted': !i.change }">{{ changeText(i.change) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="items.length > limit" class="text-muted small mb-0 mt-1">상위 {{ limit }}개만 표시 (전체 {{ items.length }}개)</p>
    </template>
  </div>
</template>

<style scoped>
.bar {
  height: 10px;
  min-width: 2px;
  border-radius: 0 4px 4px 0;
}
</style>
