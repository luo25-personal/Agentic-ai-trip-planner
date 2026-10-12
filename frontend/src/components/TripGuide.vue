<script setup>
// AI 旅遊書：先在畫面上預覽，按「下載 PDF」時用瀏覽器的列印功能另存成 PDF。
// - 文字內容（標題、簡介、每天的行程介紹、小提醒）由後端 /api/guidebook 的 AI 填好固定格式
// - 排版、照片（樂天飯店照片）、地圖都由這個版型處理，所以版面每次都一樣
// - 用 Teleport 放到 <body> 最外層：列印時把網站其他部分隱藏，只印旅遊書
import { computed } from 'vue'
import TripMap from './TripMap.vue'
import { SITE_NAME, itemMeta, tripDates } from '../guidebook.js'
import { directionsUrl, mapUrl } from '../trip.js'
import { shortDate } from '../utils.js'

const props = defineProps({
  open: Boolean,
  items: { type: Array, required: true }, // 行程清單（照順序）
  book: { type: Object, default: null }, // AI 寫好的內容；null 表示還在生成或生成失敗
  loading: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['close', 'download', 'regenerate'])

// AI 生成失敗時，用清單本身排一份簡易版，使用者還是可以下載
const content = computed(
  () =>
    props.book ?? {
      title: '我的日本行程',
      intro: '',
      days: [{ label: '行程', date: '', theme: '', stops: props.items.map((_, i) => ({ ref: i + 1, time: '', description: '', tip: '' })) }],
      tips: [],
    },
)

const itemOf = (stop) => props.items[stop.ref - 1]
// 跟行程清單一樣：住宿標「宿」，景點照景點的順序編號
const badge = (stop) => {
  const item = itemOf(stop)
  if (item.type === 'hotel') return '宿'
  return props.items.filter((i) => i.type !== 'hotel').indexOf(item) + 1
}
const WEEK = '日一二三四五六'
const dayDate = (d) => (d ? `${shortDate(d)}（${WEEK[new Date(`${d}T00:00:00`).getDay()]}）` : '')
const nextStop = (day, i) => day.stops[i + 1]
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="guidebook" role="dialog" aria-modal="true" aria-label="旅遊書預覽">
      <div class="gb-toolbar">
        <strong>旅遊書預覽</strong>
        <span class="gb-spacer"></span>
        <button v-if="!loading" type="button" class="gb-btn" @click="emit('regenerate')">重新生成</button>
        <button type="button" class="gb-btn gb-primary" :disabled="loading" @click="emit('download')">下載 PDF</button>
        <button type="button" class="gb-btn" @click="emit('close')">關閉</button>
      </div>

      <div v-if="loading" class="gb-loading">
        <p>AI 正在撰寫旅遊書…</p>
        <p class="gb-muted">大約需要 5–10 秒</p>
      </div>

      <article v-else class="gb-book">
        <p v-if="error" class="gb-error">{{ error }}，先顯示簡易版旅遊書。</p>

        <!-- 封面 -->
        <header class="gb-cover">
          <p class="gb-brand">{{ SITE_NAME }}</p>
          <h1>{{ content.title }}</h1>
          <p class="gb-sub">
            <span v-if="tripDates(items)">{{ tripDates(items) }}・</span>{{ items.length }} 個地點<span
              v-if="content.days.length > 1"
              >・{{ content.days.length }} 天</span
            >
          </p>
          <p v-if="content.intro" class="gb-intro">{{ content.intro }}</p>
          <div class="gb-map">
            <TripMap :items="items" :active="open && !loading" />
          </div>
        </header>

        <!-- 每天的行程 -->
        <section v-for="(day, d) in content.days" :key="d" class="gb-day">
          <div class="gb-day-head">
            <span class="gb-day-no">{{ day.label }}</span>
            <span v-if="day.date" class="gb-day-date">{{ dayDate(day.date) }}</span>
            <span v-if="day.theme" class="gb-day-theme">{{ day.theme }}</span>
          </div>

          <ol class="gb-stops">
            <template v-for="(stop, i) in day.stops" :key="i">
              <li class="gb-stop" :class="`gb-${itemOf(stop).type}`">
                <div class="gb-time">{{ stop.time }}</div>
                <div class="gb-card">
                  <img
                    v-if="itemOf(stop).thumbnailUrl"
                    class="gb-photo"
                    :src="itemOf(stop).thumbnailUrl"
                    alt=""
                  />
                  <div class="gb-card-body">
                    <h2>
                      <span class="gb-num">{{ badge(stop) }}</span>{{ itemOf(stop).name }}
                    </h2>
                    <p class="gb-meta">{{ itemMeta(itemOf(stop)) }}</p>
                    <p v-if="stop.description" class="gb-desc">{{ stop.description }}</p>
                    <p v-if="stop.tip" class="gb-tip"><strong>小提醒</strong>{{ stop.tip }}</p>
                    <p class="gb-links">
                      <a v-if="itemOf(stop).reserveUrl" :href="itemOf(stop).reserveUrl" target="_blank" rel="noopener noreferrer">到樂天訂房</a>
                      <a :href="mapUrl(itemOf(stop).lat, itemOf(stop).lng)" target="_blank" rel="noopener noreferrer">Google 地圖</a>
                    </p>
                  </div>
                </div>
              </li>
              <li v-if="nextStop(day, i) && nextStop(day, i).ref !== stop.ref" class="gb-leg">
                <a :href="directionsUrl(itemOf(stop), itemOf(nextStop(day, i)))" target="_blank" rel="noopener noreferrer">
                  ↓ 交通方式（Google 地圖）
                </a>
              </li>
            </template>
          </ol>
        </section>

        <section v-if="content.tips.length" class="gb-tips">
          <h2>旅行小提醒</h2>
          <ul>
            <li v-for="(t, i) in content.tips" :key="i">{{ t }}</li>
          </ul>
        </section>

        <footer class="gb-footer">
          空房與價格以樂天訂房頁面為準；營業時間、票價與交通方式請以官方資訊和 Google 地圖為準。
          文字由 Google Gemini 產生，僅供參考。飯店照片：Rakuten Travel。地圖 © OpenStreetMap contributors。
        </footer>
      </article>
    </div>
  </Teleport>
</template>

<style>
/* 不用 scoped：列印時要能隱藏網站的其他部分。旅遊書固定用淺色紙張配色，不跟深色模式 */
.guidebook {
  --gb-paper: #fbf8f2;
  --gb-ink: #1f2a25;
  --gb-muted: #6b716d;
  --gb-line: #1f7a5c;
  --gb-hotel: #b26b00;
  --gb-rule: #e3ded3;
  position: fixed;
  inset: 0;
  z-index: 1000;
  overflow-y: auto;
  background: rgba(20, 24, 22, 0.6);
  color: var(--gb-ink);
  font-family: 'Noto Sans TC', var(--font-jp), sans-serif;
  line-height: 1.6;
}
.gb-toolbar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid var(--gb-rule);
}
.gb-spacer {
  flex: 1;
}
.gb-btn {
  font: inherit;
  font-size: 0.9rem;
  padding: 6px 14px;
  color: var(--gb-line);
  background: #fff;
  border: 1px solid var(--gb-line);
  border-radius: 6px;
  cursor: pointer;
}
.gb-primary {
  color: #fff;
  background: var(--gb-line);
  font-weight: 700;
}
.gb-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.gb-loading {
  max-width: 760px;
  margin: 40px auto;
  padding: 60px 20px;
  text-align: center;
  background: var(--gb-paper);
  border-radius: 8px;
}
.gb-loading p {
  margin: 0 0 4px;
}
.gb-muted {
  color: var(--gb-muted);
  font-size: 0.85rem;
}
.gb-book {
  max-width: 760px;
  margin: 24px auto 48px;
  padding: 40px 44px;
  background: var(--gb-paper);
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
}
.gb-error {
  margin: 0 0 16px;
  padding: 8px 12px;
  color: #8a3b12;
  background: #fbe9dc;
  border-radius: 6px;
  font-size: 0.9rem;
}

/* 封面 */
.gb-cover {
  padding-bottom: 20px;
  margin-bottom: 8px;
  border-bottom: 3px double var(--gb-line);
}
.gb-brand {
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gb-line);
  font-weight: 700;
}
.gb-cover h1 {
  margin: 6px 0 4px;
  font-family: var(--font-jp);
  font-size: 2rem;
  font-weight: 900;
  line-height: 1.3;
}
.gb-sub {
  margin: 0;
  color: var(--gb-muted);
}
.gb-intro {
  margin: 14px 0 0;
  font-size: 1.02rem;
}
.gb-map {
  height: 260px;
  margin-top: 16px;
}

/* 每一天 */
.gb-day {
  margin-top: 28px;
}
.gb-day-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--gb-rule);
  break-after: avoid;
}
.gb-day-no {
  font-family: var(--font-jp);
  font-size: 1.35rem;
  font-weight: 900;
  color: var(--gb-line);
}
.gb-day-date {
  font-weight: 700;
}
.gb-day-theme {
  color: var(--gb-muted);
}
.gb-stops {
  list-style: none;
  margin: 0;
  padding: 0;
}
.gb-stop {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 12px;
  break-inside: avoid;
}
.gb-time {
  padding-top: 12px;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--gb-muted);
  text-align: right;
}
.gb-card {
  display: flex;
  gap: 14px;
  padding: 12px 14px;
  background: #fff;
  border-left: 4px solid var(--gb-line);
  border-radius: 0 8px 8px 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.gb-hotel .gb-card {
  border-left-color: var(--gb-hotel);
}
.gb-photo {
  flex: 0 0 auto;
  width: 120px;
  height: 90px;
  object-fit: cover;
  border-radius: 6px;
  background: var(--gb-rule);
}
.gb-card-body {
  flex: 1;
  min-width: 0;
}
.gb-card h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-family: var(--font-jp);
  font-size: 1.1rem;
  line-height: 1.35;
}
.gb-num {
  flex: 0 0 auto;
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #fff;
  background: var(--gb-line);
  font-size: 0.75rem;
}
.gb-hotel .gb-num {
  background: var(--gb-hotel);
}
.gb-meta {
  margin: 2px 0 0;
  font-size: 0.82rem;
  color: var(--gb-muted);
}
.gb-desc {
  margin: 8px 0 0;
}
.gb-tip {
  margin: 6px 0 0;
  font-size: 0.9rem;
}
.gb-tip strong {
  display: inline-block;
  margin-right: 6px;
  padding: 0 6px;
  font-size: 0.75rem;
  color: var(--gb-hotel);
  border: 1px solid var(--gb-hotel);
  border-radius: 4px;
}
.gb-links {
  margin: 6px 0 0;
  font-size: 0.85rem;
}
.gb-links a,
.gb-leg a,
.gb-footer a {
  color: var(--gb-line);
}
.gb-links a + a {
  margin-left: 12px;
}
.gb-leg {
  padding: 6px 0 6px 68px;
  font-size: 0.82rem;
}

.gb-tips {
  margin-top: 28px;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid var(--gb-rule);
  border-radius: 8px;
  break-inside: avoid;
}
.gb-tips h2 {
  margin: 0 0 6px;
  font-family: var(--font-jp);
  font-size: 1.1rem;
}
.gb-tips ul {
  margin: 0;
  padding-left: 1.2em;
}
.gb-footer {
  margin-top: 28px;
  padding-top: 10px;
  border-top: 1px solid var(--gb-rule);
  font-size: 0.75rem;
  color: var(--gb-muted);
}

@media (max-width: 600px) {
  .gb-book {
    margin: 0;
    padding: 24px 16px;
    border-radius: 0;
  }
  .gb-cover h1 {
    font-size: 1.5rem;
  }
  .gb-stop {
    grid-template-columns: 1fr;
    gap: 2px;
  }
  .gb-time {
    padding-top: 0;
    text-align: left;
  }
  .gb-photo {
    width: 84px;
    height: 64px;
  }
  .gb-leg {
    padding-left: 8px;
  }
}

/* 列印：只印旅遊書本身 */
@media print {
  body > :not(.guidebook) {
    display: none !important;
  }
  body {
    background: #fff !important;
  }
  .guidebook {
    position: static;
    overflow: visible;
    background: none;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }
  .gb-toolbar,
  .gb-error {
    display: none;
  }
  .gb-book {
    max-width: none;
    margin: 0;
    padding: 0;
    box-shadow: none;
    background: #fff;
  }
  .gb-map .leaflet-control-zoom {
    display: none;
  }
}
</style>
