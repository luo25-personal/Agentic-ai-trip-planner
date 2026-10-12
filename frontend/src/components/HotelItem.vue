<script setup>
import { computed, ref } from 'vue'
import PlanTable from './PlanTable.vue'
import { searchPlans } from '../api.js'
import { hasItem, hotelToItem, toggleItem } from '../trip.js'
import { unitLabel, yen } from '../utils.js'

const props = defineProps({
  hotel: { type: Object, required: true },
  query: { type: Object, required: true },
})

const open = ref(false)
const plans = ref(null) // 載入過就保留，再次展開不用重打 API
const loading = ref(false)
const error = ref('')

const added = computed(() => hasItem(`hotel-${props.hotel.hotelNo}`))
const toggleTrip = () => toggleItem(hotelToItem(props.hotel, props.query))

const nightPrefix = computed(() => (props.query.nights > 1 ? '第一晚 ' : ''))

async function toggle() {
  open.value = !open.value
  if (!open.value || plans.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await searchPlans(props.hotel.hotelNo, props.query)
    plans.value = data.plans
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <li class="hotel">
    <div class="row">
      <img v-if="hotel.thumbnailUrl" class="thumb" :src="hotel.thumbnailUrl" alt="" loading="lazy" />
      <div v-else class="thumb"></div>

      <div>
        <h2 class="name jp">{{ hotel.name }}</h2>
        <div class="meta muted">
          <span v-if="hotel.nearestStation">最近車站：{{ hotel.nearestStation }}</span>
          <span v-if="hotel.reviewAverage">　評分 {{ hotel.reviewAverage }}（{{ hotel.reviewCount }} 則）</span>
        </div>
      </div>

      <div v-if="hotel.cheapestPlan" class="price">
        <div class="label muted">{{ nightPrefix }}{{ unitLabel(hotel.cheapestPlan) }}</div>
        <div class="num">{{ yen(hotel.cheapestPlan.firstNightCharge) }} 起</div>
        <div class="buttons">
          <button class="toggle" type="button" :aria-expanded="open" @click="toggle">
            {{ open ? '收起房型' : '查看房型' }}
          </button>
          <button class="trip" :class="{ added }" type="button" :aria-pressed="added" @click="toggleTrip">
            {{ added ? '✓ 已加入行程' : '＋ 加入行程' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="open" class="plans">
      <p v-if="loading" class="muted">載入房型中…</p>
      <p v-else-if="error" class="error">{{ error }}</p>
      <p v-else-if="plans && !plans.length" class="muted">這間飯店目前沒有符合條件的方案。</p>
      <PlanTable v-else-if="plans" :plans="plans" :adults="query.adults" :nights="query.nights" />
    </div>
  </li>
</template>

<style scoped>
.hotel {
  border-bottom: 1px solid var(--rule);
}
.row {
  display: grid;
  grid-template-columns: 96px 1fr auto;
  gap: 16px;
  padding: 16px 0;
  align-items: start;
}
.thumb {
  width: 96px;
  height: 72px;
  object-fit: cover;
  border-radius: 4px;
  background: var(--rule);
}
.name {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.35;
}
.meta {
  margin-top: 4px;
  font-size: 0.85rem;
}
.price {
  text-align: right;
  white-space: nowrap;
}
.label {
  font-size: 0.8rem;
}
.num {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--price);
  font-variant-numeric: tabular-nums;
}
.toggle {
  margin-top: 6px;
  font: inherit;
  font-size: 0.9rem;
  color: var(--line);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 12px;
  cursor: pointer;
}
.buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 6px;
}
.buttons .toggle {
  margin-top: 0;
}
.trip {
  font: inherit;
  font-size: 0.9rem;
  color: var(--price);
  background: none;
  border: 1px solid var(--price);
  border-radius: var(--radius);
  padding: 4px 12px;
  cursor: pointer;
}
.trip.added {
  color: var(--bg);
  background: var(--price);
}
.plans {
  margin: 0 0 16px 112px;
}
.error {
  color: var(--error);
}

@media (max-width: 600px) {
  .row {
    grid-template-columns: 72px 1fr;
  }
  .thumb {
    width: 72px;
    height: 56px;
  }
  .price {
    grid-column: 2;
    text-align: left;
  }
  .buttons {
    justify-content: flex-start;
  }
  .plans {
    margin-left: 0;
  }
}
</style>
