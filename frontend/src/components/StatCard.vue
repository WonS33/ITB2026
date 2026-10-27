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
      <div class="stat-title">{{ title }}</div>
      <div class="stat-value">
        <template v-if="value === null || value === undefined">-</template>
        <template v-else>{{ typeof value === 'number' ? value.toLocaleString() : value }}<small class="stat-unit">{{ unit }}</small></template>
      </div>
      <div v-if="hint" class="text-muted small">{{ hint }}</div>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.stat-title {
  font-weight: 600;
  margin-bottom: 0.35rem;
}
.stat-value {
  font-size: 1.9rem;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
}
.stat-unit {
  margin-left: 0.25rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--muted);
}
</style>
