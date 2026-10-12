<script setup>
// 「行程規劃」tab（草稿版面）：
//   桌機：左 2/3 地圖、右 1/3 文字行程，底下是跟 AI 討論的聊天區
//   手機：地圖 → 行程 → 聊天 由上往下排
// 聊天區連到後端的「行程 Agent」（/api/trip-chat），每次都把目前的行程清單一起送過去。
// AI 建議新順序時，訊息下方會出現「套用這個順序」按鈕，由使用者決定要不要套用。
import { computed, nextTick, ref } from 'vue'
import TripMap from './TripMap.vue'
import TripGuide from './TripGuide.vue'
import { printGuidebook, shareText } from '../guidebook.js'
import { generateGuidebook, tripChat } from '../api.js'
import {
  applyOrder,
  clearTrip,
  directionsUrl,
  hotelsOf,
  isCurrentOrder,
  itemsForAgent,
  orderedItems,
  spotsOf,
  moveItem,
  removeItem,
  sameOrderSet,
  trip,
} from '../trip.js'
import { renderReply, shortDate } from '../utils.js'

defineProps({ active: Boolean })
const emit = defineEmits(['go-search'])

// 住宿照入住日期排列（順序固定）；景點是使用者排的順序
const hotels = computed(() => hotelsOf(trip.items))
const spots = computed(() => spotsOf(trip.items))
const mapItems = computed(() => orderedItems(trip.items))

// 日期重疊的住宿（同一晚不可能住兩間），在清單上標示出來
const overlapIds = computed(() => {
  const hotels = trip.items.filter((i) => i.type === 'hotel' && i.checkin && i.checkout)
  const ids = new Set()
  hotels.forEach((a, n) =>
    hotels.slice(n + 1).forEach((b) => {
      if (a.checkin < b.checkout && b.checkin < a.checkout) ids.add(a.id).add(b.id)
    }),
  )
  return ids
})

const MAX_TEXT = 500
const messages = ref([]) // { role: 'user' | 'model', text, order? }
const input = ref('')
const loading = ref(false)
const error = ref('')
const messagesEl = ref(null)

async function send() {
  const text = input.value.trim()
  if (!text || loading.value) return
  error.value = ''
  messages.value.push({ role: 'user', text })
  input.value = ''
  loading.value = true
  await scrollToEnd()
  try {
    const history = messages.value.map((m) => ({ role: m.role, text: m.text }))
    const result = await tripChat(history, itemsForAgent())
    messages.value.push({ role: 'model', text: result.reply, order: result.order })
  } catch (e) {
    // 失敗時把提問放回輸入框，方便重送
    messages.value.pop()
    input.value = text
    error.value = e.message
  } finally {
    loading.value = false
    await scrollToEnd()
  }
}

function resetChat() {
  messages.value = []
  error.value = ''
}

async function scrollToEnd() {
  await nextTick()
  const el = messagesEl.value
  if (el) el.scrollTop = el.scrollHeight // 只捲動聊天框，不捲動整個頁面
}

function onKeydown(e) {
  // Enter 送出；輸入法選字中不送出
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

// ── 旅遊書：下載 PDF、複製文字（都在瀏覽器完成，不經過伺服器）──
// 旅遊書附上行程 Agent 最後一次的建議
const aiNote = computed(() => [...messages.value].reverse().find((m) => m.role === 'model')?.text ?? '')
const exportMsg = ref('')

function flash(text) {
  exportMsg.value = text
  setTimeout(() => (exportMsg.value = ''), 2500)
}

// AI 旅遊書：清單沒變就沿用上次的內容，不重複呼叫 AI（省免費額度）
const guide = ref({ open: false, loading: false, book: null, error: '', key: '', items: [] })
const guideKey = () => JSON.stringify(itemsForAgent())

async function openGuidebook(force = false) {
  guide.value.open = true
  const key = guideKey()
  if (!force && guide.value.key === key && guide.value.book) return
  // 旅遊書的編號對應送給 AI 的清單，所以把當下的清單一起記下來（住宿在前、景點在後）
  const items = orderedItems().filter((i) => Number.isFinite(i.lat) && Number.isFinite(i.lng))
  guide.value = { open: true, loading: true, book: null, error: '', key, items }
  try {
    guide.value.book = await generateGuidebook(itemsForAgent())
  } catch (e) {
    guide.value.error = e.message // 失敗時旅遊書會改顯示簡易版
    guide.value.key = ''
  } finally {
    guide.value.loading = false
  }
}

async function copyTrip() {
  try {
    await navigator.clipboard.writeText(shareText(orderedItems(), aiNote.value))
    flash('已複製行程文字，可以貼到 Discord、LINE 或 Email')
  } catch {
    flash('無法複製，請改用「下載旅遊書」')
  }
}

// 建議順序的顯示：用目前清單的名稱
const nameOf = (id) => trip.items.find((i) => i.id === id)?.name ?? '？'
</script>

<template>
  <section class="planner">
    <h1 class="title jp">行程規劃</h1>
    <p class="muted intro">把有興趣的住宿和景點加入清單，在地圖上看位置，再跟 AI 討論怎麼排順序。</p>

    <div class="layout">
      <!-- 左：地圖 -->
      <div class="map-cell">
        <TripMap :items="mapItems" :active="active" />
      </div>

      <!-- 右：文字行程 -->
      <aside class="plan" aria-label="行程內容">
        <div class="plan-head">
          <h2>行程（{{ trip.items.length }}）</h2>
          <button v-if="trip.items.length" type="button" class="link" @click="clearTrip">全部清除</button>
        </div>

        <div v-if="!trip.items.length" class="empty">
          <p>行程清單還是空的。</p>
          <p class="muted">到「和 AI 聊聊」，在飯店或景點卡片上按「＋ 加入行程」。</p>
          <button type="button" class="primary" @click="emit('go-search')">去找住宿和景點</button>
        </div>

        <template v-else>
          <!-- 住宿：依入住日期排列，不用排順序 -->
          <section v-if="hotels.length" class="group">
            <h3 class="group-head">住宿（{{ hotels.length }}）<span class="muted">依入住日期排列</span></h3>
            <ul class="items">
              <li v-for="item in hotels" :key="item.id" class="item item-hotel">
                <span class="num num-hotel">宿</span>
                <div class="body">
                  <div class="name jp">{{ item.name }}</div>
                  <div class="meta muted">
                    <span v-if="item.checkin">{{ shortDate(item.checkin) }}–{{ shortDate(item.checkout) }}</span>
                    <span v-else>沒有日期</span>
                    <span v-if="overlapIds.has(item.id)" class="overlap">・⚠ 日期重疊</span>
                  </div>
                  <div class="row-actions">
                    <a v-if="item.reserveUrl" :href="item.reserveUrl" target="_blank" rel="noopener noreferrer">到樂天訂房</a>
                    <span class="actions">
                      <button type="button" aria-label="移除" @click="removeItem(item.id)">✕</button>
                    </span>
                  </div>
                </div>
              </li>
            </ul>
          </section>

          <!-- 景點：使用者排的順序，可以上下移動 -->
          <section v-if="spots.length" class="group">
            <h3 class="group-head">景點（{{ spots.length }}）<span class="muted">可以調整順序</span></h3>
            <ol class="items">
              <template v-for="(item, i) in spots" :key="item.id">
                <li class="item">
                  <span class="num num-spot">{{ i + 1 }}</span>
                  <div class="body">
                    <div class="name jp">{{ item.name }}</div>
                    <div class="meta muted">
                      <span v-if="item.area">{{ item.area }}</span>
                    </div>
                    <div class="row-actions">
                      <span class="actions">
                        <button type="button" :disabled="i === 0" aria-label="往上移" @click="moveItem(item.id, -1)">↑</button>
                        <button type="button" :disabled="i === spots.length - 1" aria-label="往下移" @click="moveItem(item.id, 1)">↓</button>
                        <button type="button" aria-label="移除" @click="removeItem(item.id)">✕</button>
                      </span>
                    </div>
                  </div>
                </li>
                <li v-if="i < spots.length - 1" class="leg">
                  <a :href="directionsUrl(item, spots[i + 1])" target="_blank" rel="noopener noreferrer">
                    ↓ {{ i + 1 }} → {{ i + 2 }} 交通方式（Google 地圖）
                  </a>
                </li>
              </template>
            </ol>
          </section>
        </template>

        <p v-if="spots.length > 1" class="muted note">地圖虛線只代表景點的順序，不是實際路線。</p>

        <div v-if="trip.items.length" class="export">
          <button type="button" class="primary small" @click="openGuidebook()">製作旅遊書（AI）</button>
          <button type="button" class="outline" @click="copyTrip">複製行程文字</button>
          <p v-if="exportMsg" class="muted export-msg" role="status">{{ exportMsg }}</p>
        </div>
      </aside>

      <!-- 底：跟 AI 討論 -->
      <div class="chat" aria-label="跟 AI 討論行程">
        <div class="chat-head">
          <h2>跟 AI 討論順序</h2>
          <button v-if="messages.length" type="button" class="link" @click="resetChat">清除對話</button>
        </div>

        <div ref="messagesEl" class="messages" aria-live="polite">
          <div v-if="!messages.length" class="bubble ai">
            嗨！我可以根據你的行程清單和地點之間的距離，幫你排造訪順序。
            例如問我「哪個順序比較順？」或「日期有沒有衝突？」
          </div>
          <template v-for="(m, i) in messages" :key="i">
            <div v-if="m.role === 'user'" class="bubble user">{{ m.text }}</div>
            <div v-else class="bubble ai">
              <div class="reply" v-html="renderReply(m.text)"></div>
              <div v-if="m.order" class="proposal">
                <div class="proposal-order jp">
                  <span v-for="(id, n) in m.order" :key="id">
                    <span v-if="n" class="arrow">→</span>{{ nameOf(id) }}
                  </span>
                </div>
                <button
                  v-if="sameOrderSet(m.order) && !isCurrentOrder(m.order)"
                  type="button"
                  class="primary small"
                  @click="applyOrder(m.order)"
                >
                  套用這個順序
                </button>
                <span v-else-if="sameOrderSet(m.order)" class="muted small-note">✓ 目前就是這個順序</span>
                <span v-else class="muted small-note">行程清單已經變動，這個建議無法套用</span>
              </div>
            </div>
          </template>
          <div v-if="loading" class="muted thinking">AI 正在思考…</div>
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <form class="ask" @submit.prevent="send">
          <input
            v-model="input"
            type="text"
            :maxlength="MAX_TEXT"
            placeholder="例如：幫我排一個比較順的順序"
            aria-label="跟 AI 討論行程"
            @keydown="onKeydown"
          />
          <button type="submit" class="primary" :disabled="loading || !input.trim()">送出</button>
        </form>
        <p class="muted note">AI 只知道直線距離，實際交通方式和時間請點行程中的 Google 地圖連結查看。</p>
      </div>
    </div>
    <TripGuide
      :open="guide.open"
      :items="guide.items"
      :book="guide.book"
      :loading="guide.loading"
      :error="guide.error"
      @close="guide.open = false"
      @download="printGuidebook(guide.items)"
      @regenerate="openGuidebook(true)"
    />
  </section>
</template>

<style scoped>
.planner {
  margin: 24px 0 40px;
}
.title {
  margin: 0;
  font-size: clamp(1.6rem, 6vw, 2.4rem);
  font-weight: 900;
  letter-spacing: 0.04em;
}
.intro {
  margin: 4px 0 16px;
}

/* 版面：桌機 地圖 2/3 + 行程 1/3，聊天橫跨底部 */
.layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  grid-template-areas:
    'map plan'
    'chat chat';
  gap: 16px;
}
.map-cell {
  grid-area: map;
  height: 480px;
}
.plan {
  grid-area: plan;
  height: 480px;
  overflow-y: auto;
  padding: 12px;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
}
.chat {
  grid-area: chat;
  padding: 12px;
  border: 1px solid var(--rule);
  border-radius: var(--radius);
}

/* 右側行程 */
.plan-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}
.plan-head h2 {
  margin: 0;
  font-size: 1.05rem;
}
.link {
  font: inherit;
  font-size: 0.85rem;
  color: var(--muted);
  background: none;
  border: 0;
  cursor: pointer;
  text-decoration: underline;
}
.empty {
  padding: 20px 8px;
  text-align: center;
}
.empty p {
  margin: 0 0 6px;
}
.primary {
  font: inherit;
  font-weight: 700;
  color: var(--line-ink);
  background: var(--line);
  border: 0;
  border-radius: var(--radius);
  padding: 8px 18px;
  cursor: pointer;
}
.primary:disabled {
  opacity: 0.45;
  cursor: default;
}
.empty .primary {
  margin-top: 8px;
}
.items {
  list-style: none;
  margin: 0;
  padding: 0;
}
.item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 10px;
  background: var(--bg);
  border-left: 4px solid var(--line);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.num {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin-top: 2px;
  border-radius: 50%;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 700;
}
.num-hotel {
  background: #b26b00;
}
.num-spot {
  background: #1f7a5c;
}
.body {
  flex: 1;
  min-width: 0;
}
.name {
  font-weight: 700;
  line-height: 1.35;
}
.meta {
  font-size: 0.82rem;
}
.row-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  font-size: 0.82rem;
}
.row-actions a {
  color: var(--line);
}
.actions {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.actions button {
  font: inherit;
  width: 26px;
  height: 26px;
  padding: 0;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  cursor: pointer;
}
.actions button:disabled {
  opacity: 0.35;
  cursor: default;
}
.leg {
  padding: 4px 0 4px 14px;
  font-size: 0.8rem;
}
.leg a {
  color: var(--line);
}
.note {
  margin: 10px 0 0;
  font-size: 0.78rem;
}

/* 底部聊天 */
.chat-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}
.chat-head h2 {
  margin: 0;
  font-size: 1.05rem;
}
.messages {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
  margin-bottom: 10px;
}
.bubble {
  max-width: 80%;
  padding: 8px 12px;
  border-radius: var(--radius);
  line-height: 1.55;
}
.bubble.ai {
  align-self: flex-start;
  background: var(--panel);
}
.bubble.user {
  align-self: flex-end;
  white-space: pre-wrap;
  color: var(--line-ink);
  background: var(--line);
}
.reply :deep(p) {
  margin: 0 0 6px;
}
.reply :deep(p:last-child) {
  margin-bottom: 0;
}
.reply :deep(ul),
.reply :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}
.reply :deep(a) {
  color: var(--line);
}
.proposal {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--rule);
}
.proposal-order {
  flex: 1 1 100%;
  font-size: 0.85rem;
  font-weight: 700;
}
.export {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--rule);
}
.outline {
  font: inherit;
  font-size: 0.85rem;
  color: var(--line);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 12px;
  cursor: pointer;
}
.export-msg {
  flex: 1 1 100%;
  margin: 2px 0 0;
  font-size: 0.8rem;
}
.group + .group {
  margin-top: 14px;
}
.group-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 6px;
  font-size: 0.92rem;
}
.group-head .muted {
  font-size: 0.78rem;
  font-weight: 400;
}
.items li.item + li.item {
  margin-top: 6px;
}
.item-hotel {
  border-left-color: #b26b00;
}
.overlap {
  color: var(--price);
  font-weight: 700;
}
.arrow {
  margin: 0 6px;
  color: var(--muted);
}
.primary.small {
  padding: 4px 12px;
  font-size: 0.85rem;
}
.small-note {
  font-size: 0.82rem;
}
.thinking {
  font-size: 0.9rem;
}
.error {
  margin: 0 0 8px;
  color: var(--error);
}
.ask {
  display: flex;
  gap: 8px;
}
.ask input {
  flex: 1;
  min-width: 0;
  font: inherit;
  padding: 8px 10px;
  color: var(--ink);
  background: var(--bg);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
}

/* 手機：地圖 → 行程 → 聊天 */
@media (max-width: 760px) {
  .layout {
    grid-template-columns: 1fr;
    grid-template-areas:
      'map'
      'plan'
      'chat';
  }
  .map-cell {
    height: 300px;
  }
  .plan {
    height: auto;
    max-height: none;
  }
  .bubble {
    max-width: 100%;
  }
}
</style>
