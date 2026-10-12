<script setup>
// 仿日本車站站名牌：顯示目前選擇的車站與查詢條件
defineProps({
  station: { type: Object, required: true },
  radius: { type: Number, required: true },
  checkin: { type: String, required: true },
  nights: { type: Number, required: true },
})
</script>

<template>
  <section class="sign jp" aria-label="目前選擇的車站">
    <div class="body">
      <div class="name">{{ station.name }}</div>
      <div class="roman">{{ station.roman }}</div>
    </div>
    <div class="band">
      <span>半徑 {{ radius }} km</span>
      <span>{{ checkin }} 起 {{ nights }} 晚</span>
    </div>
  </section>
</template>

<style scoped>
.sign {
  margin: 24px 0 28px;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  overflow: hidden;
}
.body {
  padding: 22px 24px 14px;
  text-align: center;
}
.name {
  font-size: clamp(3rem, 12vw, 5.5rem);
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.08em;
}
.roman {
  margin-top: 8px;
  font-size: 1.1rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.band {
  display: flex;
  justify-content: space-between;
  padding: 6px 16px;
  background: var(--line);
  color: var(--line-ink);
  font-size: 0.9rem;
  font-weight: 500;
}
</style>
