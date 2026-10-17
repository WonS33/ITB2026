<script setup>
// 한국 지도(제주 포함): 시·도 경계 위에 출장지를 점으로 표시. 점 크기 = 출장 횟수
// Leaflet + 시·도 경계 GeoJSON(통계청 2013, 간소화). 배경 지도 타일 없이 경계선만 그려 외부 서버가 필요 없다.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import provinces from '@/assets/geo/skorea_provinces.json'
import { SERIES_COLORS } from '@/charts'
import { REGION_ALIASES, REGION_POINTS } from '@/regions'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name: 시·도, quantity: 출장 횟수 }]
})

const el = ref(null)
let map = null
let markers = null

const regionName = (feature) => REGION_ALIASES[feature.properties.name] || feature.properties.name

function drawMarkers() {
  if (!map) return
  markers.clearLayers()
  const max = Math.max(1, ...props.items.map((i) => i.quantity))
  for (const item of props.items) {
    const point = REGION_POINTS[item.name]
    if (!point || !item.quantity) continue
    // 원의 넓이가 횟수에 비례하도록 반지름은 제곱근으로 (최소 6px)
    const radius = 6 + 18 * Math.sqrt(item.quantity / max)
    L.circleMarker(point, {
      radius,
      color: '#ffffff', // 점이 겹칠 때 구분되도록 흰 테두리
      weight: 2,
      fillColor: SERIES_COLORS[0],
      fillOpacity: 0.85,
    })
      .bindTooltip(`${item.name} ${item.quantity}회`, { direction: 'top' })
      .addTo(markers)
  }
}

onMounted(() => {
  map = L.map(el.value, {
    zoomControl: true,
    scrollWheelZoom: false, // 화면을 내릴 때 지도가 확대되지 않게
    zoomSnap: 0.25, // 확대 단계를 잘게 나눠 지도가 칸을 꽉 채우게
    attributionControl: true,
  })
  const outline = L.geoJSON(provinces, {
    style: { color: '#ffffff', weight: 1, fillColor: '#e3e2de', fillOpacity: 1 },
    onEachFeature: (feature, layer) => layer.bindTooltip(regionName(feature), { sticky: true }),
  }).addTo(map)
  map.attributionControl.setPrefix(false).addAttribution('시·도 경계: 통계청(2013)')
  map.fitBounds(outline.getBounds(), { padding: [10, 10] })
  markers = L.layerGroup().addTo(map)
  drawMarkers()
})

onBeforeUnmount(() => map?.remove())
watch(() => props.items, drawMarkers, { deep: true })
</script>

<template>
  <div ref="el" class="korea-map" role="img" aria-label="시·도별 출장 횟수 지도"></div>
</template>

<style scoped>
.korea-map {
  height: 520px;
  background: #ffffff;
  border-radius: 0.25rem;
}
</style>
