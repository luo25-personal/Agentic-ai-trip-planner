<script setup>
// 手動搜尋：自己選車站和日期查空房（不經過 AI）
import { computed, reactive, ref } from 'vue'
import StationSign from './StationSign.vue'
import SearchForm from './SearchForm.vue'
import HotelList from './HotelList.vue'
import PagerNav from './PagerNav.vue'
import { searchHotels } from '../api.js'
import { findStation } from '../stations.js'
import { addDays, isoDate, nightsBetween } from '../utils.js'

const checkin = addDays(isoDate(), 14)
const form = reactive({
  station: 'aomori',
  checkin,
  checkout: addDays(checkin, 1),
  adults: 2,
  radius: 1,
  kinen: true,
})

const station = computed(() => findStation(form.station))
const nights = computed(() => nightsBetween(form.checkin, form.checkout))

// 查詢結果
const hotels = ref([])
const page = ref(1)
const pageCount = ref(0)
const total = ref(0)
const loading = ref(false)
const error = ref('')
const searched = ref(false)
// 最近一次成功查詢的條件；展開房型時沿用，避免使用者改了表單但還沒重新查詢造成不一致
const lastQuery = ref(null)

const statusText = computed(() => {
  if (error.value) return error.value
  if (loading.value) return '查詢中…'
  if (!searched.value) return '選擇車站和日期，查詢附近有空房的飯店。'
  if (!total.value) return '這個條件下沒有空房。試試擴大範圍、換日期或取消禁菸條件。'
  return `找到 ${total.value} 間有空房的飯店。`
})

async function search(targetPage = 1) {
  if (nights.value < 1) {
    error.value = '退房日必須晚於入住日'
    return
  }
  const query = {
    checkin: form.checkin,
    checkout: form.checkout,
    adults: form.adults,
    kinen: form.kinen,
    radius: form.radius,
    lat: station.value.lat,
    lng: station.value.lng,
    nights: nights.value,
  }
  loading.value = true
  error.value = ''
  try {
    const data = await searchHotels({ ...query, page: targetPage })
    hotels.value = data.hotels
    page.value = data.page
    pageCount.value = data.pageCount
    total.value = data.total
    lastQuery.value = query
    searched.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>

    <StationSign :station="station" :radius="form.radius" :checkin="form.checkin" :nights="nights" />

    <SearchForm v-model="form" :loading="loading" @search="search(1)" />

    <p class="status" :class="{ error }" aria-live="polite">{{ statusText }}</p>

    <HotelList v-if="hotels.length" :hotels="hotels" :query="lastQuery" />

    <PagerNav
      :page="page"
      :page-count="pageCount"
      :disabled="loading"
      @change="search"
    />
  </div>
</template>

<style scoped>
.status {
  margin: 28px 0 8px;
  color: var(--muted);
}
.status.error {
  color: var(--error);
}
</style>
