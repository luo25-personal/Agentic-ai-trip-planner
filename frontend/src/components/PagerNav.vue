<script setup>
defineProps({
  page: { type: Number, required: true },
  pageCount: { type: Number, required: true },
  disabled: Boolean,
})
const emit = defineEmits(['change'])
</script>

<template>
  <nav v-if="pageCount > 1" class="pager" aria-label="分頁">
    <button type="button" :disabled="page <= 1 || disabled" @click="emit('change', page - 1)">上一頁</button>
    <span>第 {{ page }} / {{ pageCount }} 頁</span>
    <button type="button" :disabled="page >= pageCount || disabled" @click="emit('change', page + 1)">下一頁</button>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: -24px 0 40px;
}
button {
  font: inherit;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  padding: 6px 14px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
