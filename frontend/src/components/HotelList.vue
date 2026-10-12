<script setup>
import HotelItem from './HotelItem.vue'

defineProps({
  hotels: { type: Array, required: true },
  query: { type: Object, required: true }, // 查詢這份清單時用的條件
})
</script>

<template>
  <ol class="hotels">
    <!-- key 包含查詢條件，換條件重新查詢時，展開狀態與房型資料會重置 -->
    <HotelItem
      v-for="h in hotels"
      :key="`${h.hotelNo}-${query.checkin}-${query.checkout}-${query.adults}-${query.kinen}`"
      :hotel="h"
      :query="query"
    />
  </ol>
</template>

<style scoped>
.hotels {
  list-style: none;
  margin: 0 0 40px;
  padding: 0;
  border-top: 2px solid var(--ink);
}
</style>
