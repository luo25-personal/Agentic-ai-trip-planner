// 行程清單（像購物車）：「AI 規劃」和「行程規劃」兩個 tab 共用同一份。
// 備份在瀏覽器的 sessionStorage：重新整理、手機切 App 回來被重新載入時清單還在，
// 關掉分頁就自動清掉。只存在使用者自己的瀏覽器，不會傳到伺服器保存。

import { reactive, watch } from 'vue'

const STORAGE_KEY = 'trip-items-v1'

// 舊版存在 localStorage（關掉瀏覽器也不會清），改版後順手刪掉，不留在使用者電腦上
try {
  localStorage.removeItem(STORAGE_KEY)
} catch {
  // 瀏覽器封鎖儲存空間時略過
}

function load() {
  try {
    const items = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(items) ? items : []
  } catch {
    return [] // 瀏覽器封鎖儲存空間時，就從空清單開始
  }
}

export const trip = reactive({ items: load() })

watch(
  () => trip.items,
  (items) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch {
      // 存不進去也沒關係，只是重新整理後清單會不見
    }
  },
  { deep: true },
)

const httpsOnly = (url) => (typeof url === 'string' && url.startsWith('https://') ? url : null)

/** 樂天飯店資料 → 行程項目 */
export function hotelToItem(hotel, query) {
  return {
    id: `hotel-${hotel.hotelNo}`,
    type: 'hotel',
    name: hotel.name,
    lat: hotel.latitude,
    lng: hotel.longitude,
    thumbnailUrl: httpsOnly(hotel.thumbnailUrl),
    reserveUrl: httpsOnly(hotel.cheapestPlan?.reserveUrl),
    checkin: query?.checkin,
    checkout: query?.checkout,
  }
}

/** AI 推薦的景點（show_spots 查到的真實座標）→ 行程項目 */
export function spotToItem(spot) {
  return {
    // 用座標當 id：同一個地點不會重複加入
    id: `spot-${Math.round(spot.latitude * 1e5)}-${Math.round(spot.longitude * 1e5)}`,
    type: 'spot',
    name: spot.name,
    lat: spot.latitude,
    lng: spot.longitude,
    area: spot.area || '',
  }
}

export const hasItem = (id) => trip.items.some((i) => i.id === id)

export function toggleItem(item) {
  const index = trip.items.findIndex((i) => i.id === item.id)
  if (index >= 0) trip.items.splice(index, 1)
  else trip.items.push(item)
}

export function removeItem(id) {
  const index = trip.items.findIndex((i) => i.id === id)
  if (index >= 0) trip.items.splice(index, 1)
}

/** 往上（-1）或往下（+1）移動一格 */
export function moveItem(id, step) {
  const from = trip.items.findIndex((i) => i.id === id)
  const to = from + step
  if (from < 0 || to < 0 || to >= trip.items.length) return
  const [item] = trip.items.splice(from, 1)
  trip.items.splice(to, 0, item)
}

/** 套用 AI 建議的順序（項目 id 陣列）；清單已經變動、對不上時不套用，回傳 false */
export function applyOrder(ids) {
  if (!sameOrderSet(ids)) return false
  const byId = new Map(trip.items.map((i) => [i.id, i]))
  trip.items.splice(0, trip.items.length, ...ids.map((id) => byId.get(id)))
  return true
}

/** 建議順序是否還對得上目前的清單（項目沒有增減） */
export function sameOrderSet(ids) {
  if (!Array.isArray(ids) || ids.length !== trip.items.length) return false
  const current = new Set(trip.items.map((i) => i.id))
  return new Set(ids).size === ids.length && ids.every((id) => current.has(id))
}

/** 是否已經是這個順序 */
export const isCurrentOrder = (ids) => ids.every((id, n) => trip.items[n]?.id === id)

/** 傳給行程 Agent 的資料：只送需要的欄位，沒有座標的項目無法算距離就不送 */
export function itemsForAgent() {
  return trip.items
    .filter((i) => Number.isFinite(i.lat) && Number.isFinite(i.lng))
    .map(({ id, type, name, lat, lng, checkin, checkout, area }) => ({
      id,
      type,
      name: String(name).slice(0, 100),
      lat,
      lng,
      checkin: checkin || null,
      checkout: checkout || null,
      area: area ? String(area).slice(0, 60) : null,
    }))
}

export function clearTrip() {
  trip.items.splice(0)
}

/** 在 Google 地圖上查看這個位置 */
export function mapUrl(lat, lng) {
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: `${lat},${lng}` })}`
}

/** Google 地圖大眾運輸路線連結（免費，不用金鑰） */
export function directionsUrl(from, to) {
  const params = new URLSearchParams({
    api: '1',
    origin: `${from.lat},${from.lng}`,
    destination: `${to.lat},${to.lng}`,
    travelmode: 'transit',
  })
  return `https://www.google.com/maps/dir/?${params}`
}
