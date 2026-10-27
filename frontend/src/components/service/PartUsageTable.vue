<script setup>
// 교체 부품 순위: 표 안에 사용 횟수 막대 + 현재 단가·직전 대비 증감
// 부품이 많고 이름이 길어 순위는 가로 막대가 가장 정확하고, 단가를 옆에 두면 "많이 쓰이고 비싼 부품"이 한눈에 보인다
import { computed } from 'vue'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity, current_price, change, change_rate }] (많은 순서)
  limit: { type: Number, default: 10 },
})

const shown = computed(() => props.items.slice(0, props.limit))
const max = computed(() => Math.max(1, ...shown.value.map((i) => i.quantity)))
const won = (v) => (v === null || v === undefined ? '-' : `${v.toLocaleString()}원`)
function changeText(i) {
  if (i.change === null || i.change === undefined) return ''
  const sign = i.change > 0 ? '+' : ''
  return `${sign}${i.change_rate ?? 0}%`
}
</script>

<template>
  <div>
    <p v-if="!items.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <template v-else>
      <table class="table table-sm small align-middle mb-0">
        <thead>
          <tr><th>부품명</th><th style="width: 38%">사용 횟수</th><th class="text-end">현재 단가</th></tr>
        </thead>
        <tbody>
          <tr v-for="i in shown" :key="i.name">
            <td class="text-break">{{ i.name }}</td>
            <td>
              <div class="d-flex align-items-center gap-2">
                <div class="usage-bar" :style="{ width: `${(i.quantity / max) * 100}%` }"></div>
                <span class="text-nowrap">{{ i.quantity }}회</span>
              </div>
            </td>
            <td class="text-end text-nowrap">
              {{ won(i.current_price) }}
              <!-- 증감은 색만으로 구분하지 않고 +/- 기호를 함께 표시 -->
              <div v-if="changeText(i)" :class="i.change > 0 ? 'price-up' : i.change < 0 ? 'price-down' : 'text-muted'" style="font-size: 0.75rem">
                직전 대비 {{ changeText(i) }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="text-muted small mb-0 mt-1">
        사용 횟수는 보고서에 수량이 없어 1회씩 셈.
        <template v-if="items.length > limit">상위 {{ limit }}개만 표시 (전체 {{ items.length }}개). </template>
        단가가 없으면 "-"
      </p>
    </template>
  </div>
</template>

<style scoped>
/* 단가 증감: 오르면 빨강, 내리면 파랑 (테마의 primary는 주황이라 직접 지정) */
.price-up {
  color: #c0392b;
}
.price-down {
  color: #2563a8;
}
/* 사용 횟수 막대: 유상·무상 색과 헷갈리지 않게 중립 회청색 */
.usage-bar {
  height: 10px;
  min-width: 2px;
  background: #9aa9bd;
  border-radius: 0 4px 4px 0;
}
</style>
