// 日期（YYYY-MM-DD，使用者當地時區）
export function isoDate(d = new Date()) {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

export function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + n)
  return isoDate(d)
}

export function nightsBetween(checkin, checkout) {
  const n = (new Date(checkout) - new Date(checkin)) / 86400000
  return n > 0 ? n : 0
}

// 價格
export const yen = (n) => (n == null ? '—' : `${n.toLocaleString('ja-JP')} 円`)
export const unitLabel = (plan) => (plan.unit === 'room' ? '每房' : '每人')

// 把 AI 回覆的簡單 Markdown（粗體、條列）轉成 HTML。
// 先跳脫所有 HTML 字元，再加上少數標籤，避免 AI 回覆中的內容被當成程式碼執行。
const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const link = (url, text) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`

// hotels：這次查到的樂天飯店資料，用來在飯店區塊裡填上真實的價格與評分（AI 不寫價格）
// spots：這次 show_spots 查到位置的景點
// 飯店和景點卡片都有「＋ 加入行程」按鈕；added.hotel(hotel)、added.spot(spot) 判斷是否已加入
export function renderReply(text, hotels = [], spots = [], added = {}) {
  // 第 1 步：逐行分類成「段落、標題、分隔線、條列項目」
  const blocks = []
  for (const raw of escapeHtml(text).split('\n')) {
    if (/^\s*(?:-{3,}|\*{3,})\s*$/.test(raw)) {
      blocks.push({ type: 'hr' })
      continue
    }
    const line = inline(raw)
    const item = line.match(/^(\s*)(?:[-*•]|\d+\.)\s+(.*)$/)
    if (item) {
      blocks.push({ type: 'item', indent: item[1].replace(/\t/g, '  ').length, html: item[2] })
      continue
    }
    const heading = line.match(/^#{1,4}\s+(.*)$/)
    if (heading) blocks.push({ type: 'p', html: `<strong>${heading[1]}</strong>` })
    else if (line.trim()) blocks.push({ type: 'p', html: line })
  }

  // 第 2 步：輸出 HTML，連續的條列項目一起處理
  const html = []
  for (let i = 0; i < blocks.length; ) {
    const b = blocks[i]
    if (b.type !== 'item') {
      html.push(b.type === 'hr' ? '<hr>' : `<p>${b.html}</p>`)
      i++
      continue
    }
    let j = i
    while (j < blocks.length && blocks[j].type === 'item') j++
    const items = blocks.slice(i, j)
    if (isCardList(items)) {
      // 只有連結的項目（例如參考來源）不屬於卡片，從那裡開始改回一般條列
      const k = items.findIndex(isLinkOnly)
      const cards = k < 0 ? items : items.slice(0, k)
      html.push(renderCards(cards, hotels, spots, added))
      if (k >= 0) html.push(renderList(items.slice(k)))
    } else {
      html.push(renderList(items))
    }
    i = j
  }
  return html.join('')
}

// 整個項目只有連結，例如「- [樂吃購！日本](https://...)」
const isLinkOnly = (item) => /^(<a [^>]+>[^<]*<\/a>[\s、,，]*)+$/.test(item.html.trim())

// 只有粗體的項目，例如「- **ホテル京阪 京都八条口**」，當作一張卡片的標題
const isTitle = (item) => /^<strong>[^<]+<\/strong>\s*[：:]?\s*$/.test(item.html)

// 至少有 2 個標題、而且第一項就是標題，才改用卡片顯示（例如飯店清單）
function isCardList(items) {
  return isTitle(items[0]) && items.filter(isTitle).length >= 2
}

// 比對用：去掉 HTML、空白，全形轉半形
const plain = (html) =>
  html
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .normalize('NFKC')
    .replace(/\s+/g, '')
    .toLowerCase()

// 用名稱找對應的樂天飯店。AI 可能在名稱後面加中文翻譯，所以用「包含」比對
function findHotel(titleHtml, hotels) {
  const title = plain(titleHtml)
  if (title.length < 3) return null
  return (
    hotels.find((h) => {
      const name = plain(h.name || '')
      return name.length >= 3 && (title.includes(name) || name.includes(title))
    }) || null
  )
}

// 景點比對時再去掉「・」：AI 可能一下寫「ワ・ラッセ」一下寫「ワラッセ」
const spotKey = (html) => plain(html).replace(/[・･·]/g, '')

// 用名稱找對應的景點（景點名稱可能只有 2 個字，例如「嵐山」）。
// AI 寫的名稱和 OpenStreetMap 的正式名稱都拿來比對
function findSpot(titleHtml, spots) {
  const title = spotKey(titleHtml)
  if (title.length < 2) return -1
  return spots.findIndex((s) =>
    [s.name, s.osmName].some((n) => {
      const name = spotKey(escapeHtml(n || ''))
      return name.length >= 2 && (title.includes(name) || name.includes(title))
    }),
  )
}

// 「＋ 加入行程」按鈕：用 data-hotel / data-spot 記住是第幾間飯店或第幾個景點，
// ChatMessage 監聽點擊後加入行程（v-html 裡的按鈕不能直接綁 Vue 事件）
function addButton(kind, index, isAdded) {
  return (
    `<button type="button" class="info-card-add${isAdded ? ' added' : ''}" data-${kind}="${index}" aria-pressed="${isAdded}">` +
    `${isAdded ? '✓ 已加入行程' : '＋ 加入行程'}</button>`
  )
}

// 卡片右上角（手機在最下面）的按鈕區：飯店有訂房連結＋加入行程，景點只有加入行程
function sideActions(hotels, hotel, spots, spot, added) {
  let html = ''
  if (hotel) {
    html = bookLink(hotel) + addButton('hotel', hotels.indexOf(hotel), Boolean(added.hotel?.(hotel)))
  } else if (spot >= 0) {
    html = addButton('spot', spot, Boolean(added.spot?.(spots[spot])))
  } else if (added.spotsTried) {
    // 這次有標示景點，但這張卡片查不到位置：說清楚，不要讓使用者以為按鈕壞了
    return '<div class="info-card-side"><span class="info-card-nopin">查不到位置，無法加入行程</span></div>'
  }
  return html ? `<div class="info-card-side">${html}</div>` : ''
}

// 價格與評分一律來自樂天資料
function priceLine(hotel) {
  const plan = hotel?.cheapestPlan
  if (!plan) return ''
  const parts = [`第一晚 ${unitLabel(plan)} ${yen(plan.firstNightCharge)} 起`]
  if (hotel.reviewAverage) parts.push(`評分 ${hotel.reviewAverage}`)
  return `<p class="info-card-price">${parts.join('・')}</p>`
}

// 飯店照片（樂天資料）。只接受 https 網址，並跳脫引號，避免被插入其他屬性
function thumb(hotel) {
  const url = hotel?.thumbnailUrl
  if (!url || !/^https:\/\//.test(url)) return ''
  return `<img class="info-card-thumb" src="${escapeHtml(url)}" alt="" loading="lazy">`
}

// 訂房連結：樂天回傳的最低價方案網址，已帶好入住日、退房日、人數
function bookLink(hotel) {
  const url = hotel?.cheapestPlan?.reserveUrl
  if (!url || !/^https:\/\//.test(url)) return ''
  return `<a class="info-card-book" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">到樂天訂房</a>`
}

// 卡片：標題下面的項目（不管有沒有縮排）都歸到同一張卡片，直到下一個標題
function renderCards(items, hotels, spots, added) {
  const cards = []
  for (const item of items) {
    if (isTitle(item)) cards.push({ title: item.html.replace(/\s*[：:]\s*$/, ''), rows: [] })
    else cards[cards.length - 1].rows.push(item.html)
  }
  return cards
    .map((c) => {
      const hotel = findHotel(c.title, hotels)
      const spot = hotel ? -1 : findSpot(c.title, spots)
      return (
        `<div class="info-card${spot >= 0 ? ' info-card-spot' : ''}">${thumb(hotel)}<div class="info-card-body">` +
        `<p class="info-card-title">${c.title}</p>` +
        sideActions(hotels, hotel, spots, spot, added) +
        (spot >= 0 && spots[spot].area ? `<p class="info-card-area">${escapeHtml(spots[spot].area)}</p>` : '') +
        priceLine(hotel) +
        (c.rows.length ? `<ul>${c.rows.map((r) => `<li>${r}</li>`).join('')}</ul>` : '') +
        '</div></div>'
      )
    })
    .join('')
}

// 一般條列，支援縮排的子項目
function renderList(items) {
  const html = []
  const open = [] // 每一層的縮排寬度
  for (const item of items) {
    while (open.length && open[open.length - 1] > item.indent) {
      open.pop()
      html.push('</li></ul>')
    }
    const top = open[open.length - 1]
    if (top === undefined || item.indent > top) {
      html.push('<ul><li>')
      open.push(item.indent)
    } else {
      html.push('</li><li>')
    }
    html.push(item.html)
  }
  while (open.pop() !== undefined) html.push('</li></ul>')
  return html.join('')
}

// 一行文字裡的格式：連結、粗體、斜體
function inline(raw) {
  // [標題](網址) 先換成暫存記號，避免下面把網址又轉一次連結
  const links = []
  const line = raw.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, title, url) => {
    links.push(link(url, title))
    return `\u0000${links.length - 1}\u0000`
  })
  return line
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') // **粗體**
    .replace(/(^|[^*])\*(?!\s)([^*]+?)\*(?!\*)/g, '$1<em>$2</em>') // *斜體*
    // 單獨出現的網址也變成可點的連結（已經跳脫過 HTML，只接受 http/https）
    .replace(/https?:\/\/[^\s<>"，。、！？；：（）「」]+[^\s<>".,;:!?)，。、！？；：（）「」]/g, (url) => link(url, url))
    .replace(/\u0000(\d+)\u0000/g, (_, i) => links[Number(i)])
}

export const shortDate = (s) => {
  const [, m, d] = s.split('-')
  return `${Number(m)}/${Number(d)}`
}
