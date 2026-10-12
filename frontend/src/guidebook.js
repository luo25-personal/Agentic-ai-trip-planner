// 旅遊書：把行程清單整理成「可以列印成 PDF」和「可以複製貼上的純文字」兩種格式。
// 全部在使用者的瀏覽器裡完成，不經過伺服器，也不需要使用者的 Email 或 Discord 帳號。

import { directionsUrl, mapUrl } from './trip.js'
import { shortDate } from './utils.js'

export const SITE_NAME = 'Agentic AI Trip Planner'

const typeLabel = (item) => (item.type === 'hotel' ? '住宿' : '景點')

/** 一個地點的說明，例如「住宿・10/16–10/17」「景點・京都府京都市東山区」 */
export function itemMeta(item) {
  const parts = [typeLabel(item)]
  if (item.checkin && item.checkout) parts.push(`${shortDate(item.checkin)}–${shortDate(item.checkout)}`)
  if (item.area) parts.push(item.area)
  return parts.join('・')
}

/** 整趟行程的日期範圍（從住宿的入住、退房日推算），沒有住宿就回傳空字串 */
export function tripDates(items) {
  const dates = items.flatMap((i) => [i.checkin, i.checkout]).filter(Boolean).sort()
  return dates.length ? `${shortDate(dates[0])}–${shortDate(dates[dates.length - 1])}` : ''
}

// AI 回覆是簡單的 Markdown，分享成純文字時去掉 ** 等記號
const plainText = (md) =>
  md
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '$1 $2')
    .trim()

/** 複製用的純文字（貼到 Discord、LINE、Email 都能看） */
export function shareText(items, aiNote = '') {
  const hotels = items.filter((i) => i.type === 'hotel')
  const spots = items.filter((i) => i.type !== 'hotel')
  const lines = [`我的日本行程${tripDates(items) ? `（${tripDates(items)}）` : ''}`]
  if (hotels.length) {
    lines.push('', '【住宿】')
    hotels.forEach((h) => {
      lines.push(`・${h.name}（${itemMeta(h)}）`)
      lines.push(`   ${h.reserveUrl ? `訂房：${h.reserveUrl}` : `地圖：${mapUrl(h.lat, h.lng)}`}`)
    })
  }
  if (spots.length) {
    lines.push('', '【景點】')
    spots.forEach((p, i) => {
      lines.push(`${i + 1}. ${p.name}（${itemMeta(p)}）`)
      lines.push(`   地圖：${mapUrl(p.lat, p.lng)}`)
      if (i < spots.length - 1) lines.push(`   ↓ 交通方式：${directionsUrl(p, spots[i + 1])}`)
    })
  }
  if (aiNote) lines.push('', 'AI 建議：', plainText(aiNote))
  lines.push('', `由 ${SITE_NAME} 整理，空房與價格以樂天訂房頁面為準。`)
  return lines.join('\n')
}

/** 下載成 PDF：用瀏覽器內建的列印功能，使用者選「另存為 PDF」即可 */
export function printGuidebook(items) {
  const old = document.title
  // PDF 預設檔名會用網頁標題
  document.title = `日本行程${tripDates(items) ? `_${tripDates(items).replace(/\//g, '-')}` : ''}`
  window.addEventListener('afterprint', () => (document.title = old), { once: true })
  window.print()
}
