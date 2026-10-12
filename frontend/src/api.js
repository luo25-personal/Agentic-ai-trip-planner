// 呼叫自己的後端（/api/*）。金鑰只在後端，前端不會碰到。

async function getJSON(path, params) {
  const res = await fetch(`${path}?${new URLSearchParams(params)}`)
  let body = null
  try {
    body = await res.json()
  } catch {
    // 回應不是 JSON，下面用預設訊息
  }
  if (!res.ok) {
    const message =
      typeof body?.detail === 'string' ? body.detail : '查詢條件有誤，請檢查日期與人數'
    throw new Error(message)
  }
  return body
}

/** 車站周邊有空房的飯店（每間附最低價方案） */
export function searchHotels({ checkin, checkout, adults, lat, lng, radius, kinen, page = 1 }) {
  return getJSON('/api/hotels', { checkin, checkout, adults, lat, lng, radius, kinen, page })
}

/** 單一飯店所有可訂的房型方案 */
export function searchPlans(hotelNo, { checkin, checkout, adults, kinen }) {
  return getJSON(`/api/hotels/${hotelNo}/plans`, { checkin, checkout, adults, kinen })
}

/** AI Agent：送出對話紀錄，取得回覆與 Agent 查到的資料 */
export async function chat(messages) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  })
  let body = null
  try {
    body = await res.json()
  } catch {
    // 回應不是 JSON
  }
  if (!res.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'AI 暫時無法回覆，請稍後再試')
  }
  return body
}

/** 行程討論 Agent：送出對話紀錄和目前的行程清單，取得回覆與建議順序 */
export async function tripChat(messages, items) {
  const res = await fetch('/api/trip-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, items }),
  })
  let body = null
  try {
    body = await res.json()
  } catch {
    // 回應不是 JSON
  }
  if (!res.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'AI 暫時無法回覆，請稍後再試')
  }
  return body
}

/** AI 旅遊書：送出行程清單，取得 AI 寫好的旅遊書內容（固定格式） */
export async function generateGuidebook(items) {
  const res = await fetch('/api/guidebook', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })
  let body = null
  try {
    body = await res.json()
  } catch {
    // 回應不是 JSON
  }
  if (!res.ok) {
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'AI 暫時無法生成旅遊書')
  }
  return body
}
