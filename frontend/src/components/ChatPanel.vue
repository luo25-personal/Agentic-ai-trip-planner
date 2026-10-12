<script setup>
import { nextTick, ref } from 'vue'
import ChatMessage from './ChatMessage.vue'
import { chat } from '../api.js'

// 範例的日期從今天往後算，才不會過期；也用「月/日」寫法，AI 才不會反問日期
const md = (days) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
const EXAMPLES = [
  `${md(10)} 去青森住一晚，2 個大人，想住車站附近的禁菸房，順便看天氣`,
  `${md(30)} 去京都兩天一夜，2 個人，推薦景點，也找車站附近的住宿`,
]
const MAX_TEXT = 500

const messages = ref([]) // { role: 'user' | 'model', text, steps?, hotels?, weather? }
const input = ref('')
const loading = ref(false)
const error = ref('')
const listEnd = ref(null)

async function send(text = input.value) {
  text = text.trim()
  if (!text || loading.value) return
  error.value = ''
  messages.value.push({ role: 'user', text })
  input.value = ''
  loading.value = true
  await scrollToEnd()
  try {
    // 只把文字傳給後端；飯店、天氣等資料留在前端顯示就好
    const history = messages.value.map((m) => ({ role: m.role, text: m.text }))
    const result = await chat(history)
    messages.value.push({ role: 'model', text: result.reply, ...result })
  } catch (e) {
    // 失敗時把剛才的提問放回輸入框，方便重送
    messages.value.pop()
    input.value = text
    error.value = e.message
  } finally {
    loading.value = false
    await scrollToEnd()
  }
}

function reset() {
  messages.value = []
  error.value = ''
}

async function scrollToEnd() {
  await nextTick()
  listEnd.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

function onKeydown(e) {
  // Enter 送出，Shift+Enter 換行；輸入法選字中不送出
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <section class="chat">
    <ol class="messages" v-if="messages.length">
      <ChatMessage v-for="(m, i) in messages" :key="i" :message="m" />
      <li v-if="loading" class="thinking muted" aria-live="polite">AI 正在查資料…</li>
      <li ref="listEnd" class="end"></li>
    </ol>

    <form class="ask" @submit.prevent="send()">
      <label for="ask-input" class="question jp">{{ messages.length ? '還想知道什麼？' : '這趟要去日本哪裡？' }}</label>
      <textarea
        id="ask-input"
        v-model="input"
        rows="3"
        :maxlength="MAX_TEXT"
        placeholder="例如：11/20 去青森兩天，2 人，想住車站附近的禁菸房"
        @keydown="onKeydown"
      ></textarea>
      <div class="band">
        <span>輸入內容會交給 Google Gemini 處理，請勿輸入個人資料</span>
        <span class="actions">
          <button v-if="messages.length" type="button" class="ghost" :disabled="loading" @click="reset">重新開始</button>
          <button type="submit" class="send" :disabled="loading || !input.trim()">
            {{ loading ? '查詢中…' : '送出' }}
          </button>
        </span>
      </div>
    </form>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div v-if="!messages.length" class="examples">
      <p class="muted">試試看：</p>
      <button v-for="ex in EXAMPLES" :key="ex" type="button" :disabled="loading" @click="send(ex)">{{ ex }}</button>
    </div>
  </section>
</template>

<style scoped>
.messages {
  margin: 0;
  padding: 0;
}
.thinking {
  list-style: none;
  margin: 8px 0 24px;
}
.end {
  list-style: none;
}

.ask {
  margin: 24px 0 12px;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  overflow: hidden;
}
.question {
  display: block;
  padding: 20px 20px 4px;
  font-size: clamp(1.6rem, 6vw, 2.4rem);
  font-weight: 900;
  letter-spacing: 0.04em;
  line-height: 1.2;
}
textarea {
  display: block;
  width: 100%;
  padding: 8px 20px 16px;
  border: 0;
  resize: vertical;
  font: inherit;
  font-size: 1.05rem;
  color: var(--ink);
  background: transparent;
}
textarea:focus-visible {
  outline: none;
}
.ask:focus-within {
  border-color: var(--line);
}
.band {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 8px 20px;
  background: var(--line);
  color: var(--line-ink);
  font-size: 0.8rem;
}
.actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.band button {
  font: inherit;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: var(--radius);
  padding: 6px 18px;
  cursor: pointer;
}
.send {
  background: var(--line-ink);
  color: var(--line);
  border: 0;
}
.ghost {
  background: none;
  color: var(--line-ink);
  border: 1px solid currentColor;
}
.band button:disabled {
  opacity: 0.6;
  cursor: default;
}
.band button:focus-visible {
  outline-color: var(--line-ink);
}

.error {
  color: var(--error);
}
.examples {
  display: grid;
  gap: 8px;
  margin-bottom: 32px;
}
.examples p {
  margin: 0;
  font-size: 0.85rem;
}
.examples button {
  text-align: left;
  font: inherit;
  font-size: 0.95rem;
  color: var(--ink);
  background: none;
  border: 1px dashed var(--rule);
  border-radius: var(--radius);
  padding: 10px 14px;
  cursor: pointer;
}
.examples button:hover {
  border-color: var(--line);
}
</style>
