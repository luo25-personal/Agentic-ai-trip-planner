<script setup>
import { watch } from 'vue'
import { STATIONS } from '../stations.js'
import { addDays, isoDate } from '../utils.js'

// v-model 綁定父元件的查詢條件物件
const form = defineModel({ type: Object, required: true })
defineProps({ loading: Boolean })
const emit = defineEmits(['search'])

const today = isoDate()

// 入住日改到退房日之後時，自動把退房日往後推一天
watch(
  () => form.value.checkin,
  (checkin) => {
    if (form.value.checkout <= checkin) form.value.checkout = addDays(checkin, 1)
  },
)
</script>

<template>
  <form class="search" @submit.prevent="emit('search')">
    <label>
      車站
      <select v-model="form.station">
        <option v-for="s in STATIONS" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </label>
    <label>
      入住日
      <input v-model="form.checkin" type="date" :min="today" required />
    </label>
    <label>
      退房日
      <input v-model="form.checkout" type="date" :min="form.checkin" required />
    </label>
    <label>
      大人
      <select v-model.number="form.adults">
        <option v-for="n in 6" :key="n" :value="n">{{ n }} 位</option>
      </select>
    </label>
    <label>
      範圍
      <select v-model.number="form.radius">
        <option :value="0.5">0.5 km</option>
        <option :value="1">1 km</option>
        <option :value="2">2 km</option>
        <option :value="3">3 km</option>
      </select>
    </label>
    <label class="check">
      <input v-model="form.kinen" type="checkbox" />
      只要禁菸房
    </label>
    <button class="submit" type="submit" :disabled="loading">
      {{ loading ? '查詢中…' : '查詢空房' }}
    </button>
  </form>
</template>

<style scoped>
.search {
  display: grid;
  gap: 12px 16px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  align-items: end;
}
label {
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
  color: var(--muted);
}
select,
input {
  font: inherit;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  padding: 8px 10px;
  min-height: 42px;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  color: var(--ink);
  font-size: 0.95rem;
}
.check input {
  width: 18px;
  height: 18px;
  min-height: auto;
  accent-color: var(--line);
}
.submit {
  font: inherit;
  font-weight: 700;
  color: var(--line-ink);
  background: var(--line);
  border: 0;
  border-radius: var(--radius);
  padding: 0 20px;
  min-height: 42px;
  cursor: pointer;
}
.submit:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
