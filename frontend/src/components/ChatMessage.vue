<script setup>
import { computed, ref } from 'vue'
import ToolTrace from './ToolTrace.vue'
import WeatherStrip from './WeatherStrip.vue'
import HotelList from './HotelList.vue'
import { hasItem, hotelToItem, mapUrl, spotToItem, toggleItem } from '../trip.js'
import { renderReply } from '../utils.js'

const props = defineProps({ message: { type: Object, required: true } })

// AI 推薦、而且查得到位置的景點（show_spots）
const spots = computed(() => props.message.spots ?? [])
const spotAdded = (spot) => hasItem(spotToItem(spot).id)

// AI 回覆先跳脫 HTML 再加格式，所以可以安全地用 v-html 顯示。
// 有讀到行程清單（hasItem），加入或移除時按鈕文字會自動更新
const hotels = computed(() => props.message.hotels?.hotels ?? [])
const html = computed(() =>
  renderReply(props.message.text, hotels.value, spots.value, {
    hotel: (h) => hasItem(`hotel-${h.hotelNo}`),
    spot: spotAdded,
    spotsTried: (props.message.steps ?? []).some((st) => st.tool === 'show_spots'),
  }),
)

// 回覆文字裡沒有對應卡片的景點（例如只推薦一個，或名稱寫法不同），另外列在下面
const extraSpots = computed(() =>
  spots.value.map((spot, i) => ({ spot, i })).filter(({ i }) => !html.value.includes(`data-spot="${i}"`)),
)

// v-html 裡的按鈕不能直接綁 @click，所以在外層接住點擊，再看點到的是哪個景點
function onReplyClick(e) {
  const button = e.target.closest('[data-spot], [data-hotel]')
  if (!button) return
  if (button.dataset.hotel !== undefined) {
    const hotel = hotels.value[Number(button.dataset.hotel)]
    if (hotel) toggleItem(hotelToItem(hotel, props.message.hotels.query))
    return
  }
  const spot = spots.value[Number(button.dataset.spot)]
  if (spot) toggleItem(spotToItem(spot))
}

// 來源只顯示網域，例如 www.gotokyo.org
function host(url) {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

// 飯店太多時先顯示 5 間，避免對話被拉得很長
const PREVIEW = 5
const showAll = ref(false)
const allHotels = computed(() => props.message.hotels?.hotels ?? [])
const visibleHotels = computed(() => (showAll.value ? allHotels.value : allHotels.value.slice(0, PREVIEW)))
</script>

<template>
  <li v-if="message.role === 'user'" class="user">
    <p>{{ message.text }}</p>
  </li>

  <li v-else class="agent">
    <ToolTrace v-if="message.steps?.length" :steps="message.steps" />
    <!-- 天氣放最上面，下面的 AI 推薦飯店和完整飯店清單才會連在一起 -->
    <WeatherStrip v-if="message.weather" :weather="message.weather" />
    <div class="reply" @click="onReplyClick" v-html="html"></div>
    <!-- 保底：AI 有標示景點、但回覆文字裡沒有對應卡片時，程式直接用 show_spots 的結果畫卡片 -->
    <div v-if="extraSpots.length" class="reply extra-spots">
      <p class="muted extra-head">可以加入行程的景點：</p>
      <div v-for="{ spot, i } in extraSpots" :key="i" class="info-card info-card-spot">
        <div class="info-card-body">
          <p class="info-card-title"><strong>{{ spot.name }}</strong></p>
          <div class="info-card-side">
            <button
              type="button"
              class="info-card-add"
              :class="{ added: spotAdded(spot) }"
              :aria-pressed="spotAdded(spot)"
              @click="toggleItem(spotToItem(spot))"
            >
              {{ spotAdded(spot) ? '✓ 已加入行程' : '＋ 加入行程' }}
            </button>
          </div>
          <p v-if="spot.area" class="info-card-area">
            {{ spot.area }}・<a :href="mapUrl(spot.latitude, spot.longitude)" target="_blank" rel="noopener noreferrer">地圖</a>
          </p>
          <ul v-if="spot.note"><li>{{ spot.note }}</li></ul>
        </div>
      </div>
    </div>
    <template v-if="message.hotels">
      <p v-if="!message.hotels.total" class="muted">這個條件下沒有空房。</p>
      <template v-else>
        <p class="muted count">找到 {{ message.hotels.total }} 間有空房的飯店：</p>
        <HotelList :hotels="visibleHotels" :query="message.hotels.query" />
        <button v-if="allHotels.length > PREVIEW" type="button" class="more" @click="showAll = !showAll">
          {{ showAll ? '只顯示前 5 間' : `顯示全部 ${allHotels.length} 間` }}
        </button>
        <p v-if="message.hotels.total > allHotels.length" class="muted more-note">
          這裡最多列出 {{ allHotels.length }} 間，可以縮小範圍或改用「自己搜尋飯店」查看更多。
        </p>
      </template>
    </template>
    <div v-if="message.sources?.length" class="sources">
      <span class="muted">Agent 搜尋到的網頁：</span>
      <a v-for="url in message.sources" :key="url" :href="url" target="_blank" rel="noopener noreferrer">{{ host(url) }}</a>
    </div>
  </li>
</template>

<style scoped>
li {
  list-style: none;
}
.user {
  display: flex;
  justify-content: flex-end;
  margin: 20px 0;
}
.user p {
  max-width: 80%;
  margin: 0;
  padding: 10px 14px;
  background: var(--line);
  color: var(--line-ink);
  border-radius: 14px 14px 4px 14px;
  white-space: pre-wrap;
}
.agent {
  margin: 20px 0 28px;
}
.reply :deep(p) {
  margin: 0 0 8px;
}
.reply :deep(ul) {
  margin: 0 0 8px;
  padding-left: 1.3em;
}
.reply :deep(hr) {
  border: 0;
  border-top: 1px solid var(--rule);
  margin: 12px 0;
}
.reply :deep(li) {
  list-style: disc;
  margin-bottom: 2px;
}
.reply :deep(ul ul) {
  margin: 2px 0 4px;
}
.reply :deep(ul ul li) {
  list-style: circle;
  color: var(--muted);
}
/* AI 回覆裡的飯店清單：每間一個區塊，左邊一條邊框 */
.reply :deep(.info-card) {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin: 8px 0;
  padding: 8px 12px;
  background: var(--panel);
  border-left: 4px solid var(--line);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.reply :deep(.info-card-thumb) {
  flex: 0 0 auto;
  width: 88px;
  height: 66px;
  object-fit: cover;
  border-radius: 4px;
  background: var(--rule);
}
/* 桌面：訂房按鈕在右上角；手機：放到最下面 */
.reply :deep(.info-card-body) {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: 1fr auto;
  column-gap: 12px;
}
.reply :deep(.info-card-body > :not(.info-card-book):not(.info-card-side)) {
  grid-column: 1;
}
.reply :deep(.info-card-book) {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: start;
  justify-self: end;
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--line);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 2px 10px;
  text-decoration: none;
  word-break: normal;
}
.reply :deep(.info-card-side) {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: start;
  justify-self: end;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}
/* 景點卡片：綠色左邊框，跟地圖上的景點圖釘同色 */
.reply :deep(.info-card-spot) {
  border-left-color: #1f7a5c;
}
.reply :deep(.info-card-nopin) {
  font-size: 0.8rem;
  color: var(--muted);
  white-space: nowrap;
}
.reply :deep(.info-card-area) {
  margin: 0 0 2px;
  font-size: 0.82rem;
  color: var(--muted);
}
.reply :deep(.info-card-add) {
  font: inherit;
  font-size: 0.85rem;
  white-space: nowrap;
  color: var(--line);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 2px 10px;
  cursor: pointer;
}
/* 飯店的加入按鈕用橘色，跟下面飯店清單、地圖上的住宿圖釘同色 */
.reply :deep(.info-card-add[data-hotel]) {
  color: var(--price);
  border-color: var(--price);
}
.reply :deep(.info-card-add[data-hotel].added) {
  color: var(--bg);
  background: var(--price);
}
.reply :deep(.info-card-add.added) {
  color: var(--line-ink);
  background: var(--line);
}
.extra-spots {
  margin-top: 4px;
}
.extra-head {
  margin: 0 0 4px;
  font-size: 0.9rem;
}
.reply :deep(.info-card-book:hover) {
  background: var(--line);
  color: var(--line-ink);
}
@media (max-width: 600px) {
  .reply :deep(.info-card-thumb) {
    width: 64px;
    height: 48px;
  }
  .reply :deep(.info-card-body) {
    grid-template-columns: 1fr;
  }
  .reply :deep(.info-card-side) {
    grid-column: 1;
    grid-row: auto;
    order: 1;
    justify-self: start;
    justify-content: flex-start;
    margin-top: 6px;
  }
}
.reply :deep(.info-card-title) {
  margin: 0 0 2px;
  font-family: var(--font-jp);
}
.reply :deep(.info-card-price) {
  margin: 0 0 4px;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--price);
  font-variant-numeric: tabular-nums;
}
.reply :deep(.info-card ul) {
  margin: 0;
  padding-left: 1.1em;
}
.reply :deep(.info-card li) {
  list-style: none;
  position: relative;
  font-size: 0.92rem;
}
.reply :deep(.info-card li)::before {
  content: '・';
  position: absolute;
  left: -1em;
  color: var(--muted);
}
.more {
  margin-top: -28px;
  font: inherit;
  font-size: 0.9rem;
  color: var(--line);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 14px;
  cursor: pointer;
}
.more-note {
  font-size: 0.85rem;
}
.sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin: 12px 0 0;
  font-size: 0.85rem;
}
.sources a,
.reply :deep(a) {
  color: var(--line);
  word-break: break-all;
}
.count {
  margin: 16px 0 4px;
  font-size: 0.9rem;
}
</style>
