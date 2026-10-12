<script setup>
// 行程地圖：Leaflet（地圖程式）＋ OpenStreetMap（地圖圖資），都免費、不用金鑰。
// 住宿標「宿」；景點依清單順序標號，並用虛線連起來表示順序（不是實際的交通路線）。
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const props = defineProps({
  items: { type: Array, required: true },
  active: { type: Boolean, default: true }, // tab 切回來時要重算地圖大小
})

const el = ref(null)
let map = null
let layer = null

const JAPAN_CENTER = [36.2, 138.25]

function numberIcon(n, type) {
  return L.divIcon({
    className: '',
    html: `<span class="pin pin-${type}">${n}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

function draw() {
  if (!map) return
  layer.clearLayers()
  const points = props.items.filter((i) => Number.isFinite(i.lat) && Number.isFinite(i.lng))
  if (!points.length) {
    map.setView(JAPAN_CENTER, 5)
    return
  }
  const latlngs = points.map((p) => [p.lat, p.lng])
  // 住宿標「宿」（順序由日期決定，不編號）；景點照順序編號，虛線只連景點
  let n = 0
  points.forEach((p) => {
    const label = p.type === 'hotel' ? '宿' : ++n
    const marker = L.marker([p.lat, p.lng], { icon: numberIcon(label, p.type), title: p.name })
    marker.bindTooltip(p.name) // bindTooltip 會把文字當純文字處理
    layer.addLayer(marker)
  })
  const spotLine = points.filter((p) => p.type !== 'hotel').map((p) => [p.lat, p.lng])
  if (spotLine.length > 1) {
    layer.addLayer(L.polyline(spotLine, { color: '#1f7a5c', weight: 3, dashArray: '6 6', opacity: 0.8 }))
  }
  map.fitBounds(L.latLngBounds(latlngs).pad(0.25), { maxZoom: 15 })
}

onMounted(() => {
  map = L.map(el.value, { scrollWheelZoom: false })
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map)
  layer = L.layerGroup().addTo(map)
  draw()
})

onBeforeUnmount(() => map?.remove())

watch(() => props.items, draw, { deep: true })
watch(
  () => props.active,
  async (active) => {
    if (!active || !map) return
    await nextTick()
    map.invalidateSize() // 隱藏時地圖量不到大小，切回來要重新計算
    draw()
  },
)
</script>

<template>
  <div ref="el" class="map" role="region" aria-label="行程地圖"></div>
</template>

<style scoped>
.map {
  height: 100%; /* 高度由外層決定 */
  min-height: 280px;
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  z-index: 0; /* 避免地圖蓋住其他元素 */
}
.map :deep(.pin) {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #fff;
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}
.map :deep(.pin-hotel) {
  background: #b26b00;
}
.map :deep(.pin-spot) {
  background: #1f7a5c;
}
</style>
