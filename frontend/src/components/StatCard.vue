<script setup>
// 숫자 카드: 제목 + 큰 숫자 + 단위 + 보조 설명
defineProps({
  title: { type: String, required: true },
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <div class="text-muted small">{{ title }}</div>
      <div class="fs-3 fw-semibold">
        <template v-if="value === null || value === undefined">-</template>
        <template v-else>{{ typeof value === 'number' ? value.toLocaleString() : value }}<small class="fs-6 ms-1">{{ unit }}</small></template>
      </div>
      <div v-if="hint" class="text-muted small">{{ hint }}</div>
      <slot />
    </div>
  </div>
</template>
