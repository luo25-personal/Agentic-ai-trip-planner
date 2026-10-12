<script setup>
import { addDays, shortDate } from '../utils.js'

defineProps({ weather: { type: Object, required: true } })
</script>

<template>
  <section class="weather" aria-label="天氣預報">
    <p v-if="!weather.available" class="muted">{{ weather.message }}</p>
    <template v-else>
      <!-- 標示資料來源和範圍：16 天內是 API 預報，更遠的日期由 AI 用網路搜尋往年平均 -->
      <p class="source muted">
        資料來源：Open-Meteo 天氣預報 API（只提供今天起 16 天內<span v-if="weather.forecastUntil">，到 {{ shortDate(weather.forecastUntil) }}</span>）
      </p>
      <ul>
        <li v-for="d in weather.days" :key="d.date">
          <div class="date">{{ shortDate(d.date) }}</div>
          <div class="desc">{{ d.weather }}</div>
          <div class="temp">{{ Math.round(d.max) }}° / {{ Math.round(d.min) }}°</div>
          <div class="rain muted">降雨 {{ d.rain ?? '—' }}%</div>
        </li>
      </ul>
      <p v-if="weather.note && weather.forecastUntil" class="note muted">
        {{ shortDate(addDays(weather.forecastUntil, 1)) }} 之後超過 16 天，天氣預報 API 還查不到
      </p>
    </template>
  </section>
</template>

<style scoped>
.weather {
  margin: 12px 0;
}
.source,
.note {
  margin: 0 0 6px;
  font-size: 0.8rem;
}
.note {
  margin: 6px 0 0;
}
ul {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  list-style: none;
  margin: 0;
  padding: 0 0 4px;
}
li {
  flex: 0 0 auto;
  min-width: 92px;
  padding: 8px 12px;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  font-variant-numeric: tabular-nums;
}
.date {
  font-size: 0.8rem;
  color: var(--muted);
}
.desc {
  font-weight: 700;
}
.temp {
  font-size: 0.9rem;
}
.rain {
  font-size: 0.75rem;
}
</style>
