<script setup>
import { ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import ManualSearch from './components/ManualSearch.vue'
import TripPlanner from './components/TripPlanner.vue'
import SiteFooter from './components/SiteFooter.vue'
import { trip } from './trip.js'

// 三個分頁：和 AI 聊聊（主要）／行程規劃／自己搜尋飯店。用 v-show 切換，切換時不會清掉對話或搜尋結果
const mode = ref('agent')
</script>

<template>
  <div class="wrap" :class="{ wide: mode === 'trip' }">
    <header class="site">
      <strong>Agentic AI Trip Planner</strong>
      <nav class="tabs" aria-label="模式">
        <button type="button" :aria-pressed="mode === 'agent'" @click="mode = 'agent'">和 AI 聊聊</button>
        <button type="button" :aria-pressed="mode === 'trip'" @click="mode = 'trip'">
          行程規劃<span v-if="trip.items.length" class="badge">{{ trip.items.length }}</span>
        </button>
        <button type="button" :aria-pressed="mode === 'manual'" @click="mode = 'manual'">自己搜尋飯店</button>
      </nav>
    </header>

    <ChatPanel v-show="mode === 'agent'" />
    <TripPlanner v-show="mode === 'trip'" :active="mode === 'trip'" @go-search="mode = 'agent'" />
    <ManualSearch v-show="mode === 'manual'" />

    <SiteFooter />
  </div>
</template>

<style scoped>
header.site {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0 0;
  font-size: 0.9rem;
}
.tabs {
  display: flex;
  gap: 4px;
}
.tabs button {
  font: inherit;
  color: var(--muted);
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 4px 8px;
  cursor: pointer;
}
.tabs button[aria-pressed='true'] {
  color: var(--ink);
  border-bottom-color: var(--line);
  font-weight: 700;
}
.badge {
  display: inline-block;
  min-width: 18px;
  margin-left: 4px;
  padding: 0 5px;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  color: var(--bg);
  background: var(--price);
  border-radius: 9px;
}
</style>
