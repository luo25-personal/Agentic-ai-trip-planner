<script setup>
import { computed } from 'vue'
import { unitLabel, yen } from '../utils.js'

const props = defineProps({
  plans: { type: Array, required: true },
  adults: { type: Number, required: true },
  nights: { type: Number, required: true },
})

const nightPrefix = computed(() => (props.nights > 1 ? '第一晚' : ''))
</script>

<template>
  <table>
    <thead>
      <tr>
        <th>房型與方案</th>
        <th class="num">{{ nightPrefix }}價格</th>
        <th class="num hide-sm">{{ adults }} 人合計</th>
        <th><span class="sr-only">訂房連結</span></th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="p in plans" :key="`${p.planId}-${p.roomName}`">
        <td>
          <div class="jp">{{ p.roomName }}</div>
          <div class="plan-name jp muted">
            {{ p.planName }}
            <span v-if="p.withBreakfast" class="meal">含早餐</span>
            <span v-if="p.withDinner" class="meal">含晚餐</span>
          </div>
        </td>
        <td class="num">{{ unitLabel(p) }} {{ yen(p.firstNightCharge) }}</td>
        <td class="num hide-sm">{{ yen(p.firstNightTotal) }}</td>
        <td><a :href="p.reserveUrl" target="_blank" rel="noopener">到樂天訂房</a></td>
      </tr>
    </tbody>
  </table>
  <p v-if="nights > 1" class="note muted">
    樂天只提供第一晚的價格，{{ nights }} 晚的總價請以樂天訂房頁面為準。列出的方案整段住宿都有空房。
  </p>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}
th {
  text-align: left;
  font-weight: 500;
  font-size: 0.8rem;
  color: var(--muted);
  padding: 4px 8px 4px 0;
  border-bottom: 1px solid var(--rule);
}
td {
  padding: 10px 8px 10px 0;
  border-bottom: 1px dashed var(--rule);
  vertical-align: top;
}
.num {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.plan-name {
  font-size: 0.85rem;
}
.meal {
  display: inline-block;
  margin-left: 6px;
  padding: 0 6px;
  font-size: 0.75rem;
  border: 1px solid var(--rule);
  border-radius: 3px;
}
a {
  color: var(--line);
  font-weight: 500;
  white-space: nowrap;
}
.note {
  margin-top: 8px;
  font-size: 0.8rem;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

@media (max-width: 600px) {
  .hide-sm {
    display: none;
  }
}
</style>
