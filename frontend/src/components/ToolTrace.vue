<script setup>
// 顯示 Agent 這次用了哪些工具，讓使用者看得到 AI 是怎麼查到資料的
import { shortDate } from '../utils.js'

defineProps({ steps: { type: Array, required: true } })

function describe(step) {
  const a = step.args || {}
  if (step.tool === 'find_place') return `找地點「${a.name}」`
  if (step.tool === 'search_hotels') {
    const smoke = a.non_smoking ? '・禁菸' : ''
    return `查空房 ${shortDate(a.checkin)}–${shortDate(a.checkout)}・${a.adults} 人${smoke}`
  }
  if (step.tool === 'show_spots') return `標示景點 ${(a.spots || []).length} 個`
  if (step.tool === 'get_weather') return `查天氣 ${shortDate(a.start_date)}–${shortDate(a.end_date)}`
  if (step.search) return `搜尋網路「${a.query ?? ''}」`
  return `工具 ${step.tool}` // AI 偶爾會呼叫不存在的工具，照實顯示名稱

}
</script>

<template>
  <ol class="trace" aria-label="AI 使用的工具">
    <li v-for="(s, i) in steps" :key="i" :class="{ failed: !s.ok }">
      {{ describe(s) }}<span v-if="!s.ok">（失敗）</span>
    </li>
  </ol>
</template>

<style scoped>
.trace {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  font-size: 0.8rem;
}
li {
  padding: 2px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 12%, transparent);
  color: var(--line);
}
li.failed {
  background: color-mix(in srgb, var(--error) 12%, transparent);
  color: var(--error);
}
</style>
