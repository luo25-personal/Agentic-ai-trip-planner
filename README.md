# Agentic AI Trip Planner

AI agent for Japan travel planning: real-time hotel vacancy search, weather, and itinerary suggestions.

日本旅遊 AI Agent：即時空房查詢、天氣資訊與行程安排建議。

> 🚧 開發中（Work in progress）。目前完成：專案規劃與合規評估。下一步：空房查詢後端。

## 架構

```
瀏覽器 ──► 前端（靜態網頁）──► /api/search（Vercel 後端函式）──► 樂天トラベル空室検索API
```

- **前端**：靜態網頁，輸入條件並顯示結果。
- **後端函式**：保管 API 金鑰、檢查參數、快取與頻率限制。金鑰不會出現在前端。
- **部署**：Vercel。

## 資料來源

本網站的飯店與空房資料來自 [Rakuten Web Service](https://webservice.rakuten.co.jp/)。

<!-- TODO: 依樂天官方標示規範放置「Supported by Rakuten Developers」標示 -->

## 聲明

- 本網站由個人開發與經營，**非樂天集團官方服務**，與樂天集團無合作關係。
- 空房與價格以各訂房頁面顯示為準，本網站不保證資料的正確性與即時性。
- 本網站不蒐集、不保存使用者的個人資料。

## 本機開發

（待補）

## 合規

本專案遵守 Rakuten Web Service 使用條款，檢查清單見 [`docs/RAKUTEN_COMPLIANCE.md`](docs/RAKUTEN_COMPLIANCE.md)。
安全與隱私做法見 [`docs/SECURITY_AND_COST.md`](docs/SECURITY_AND_COST.md)。
