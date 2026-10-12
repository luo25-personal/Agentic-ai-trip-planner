# Agentic AI Trip Planner

AI agent for Japan travel planning: real-time hotel vacancy search, weather, and itinerary suggestions.

日本旅遊 AI Agent：即時空房查詢、天氣資訊與行程安排建議。

> 🚧 **持續開發中（Work in progress）**

🔗 **網站：<https://agentic-ai-trip-planner.vercel.app>**

**技術**：Vue 3 · Vite · Leaflet ｜ Python · FastAPI ｜ LangChain · Gemini Flash-Lite · MCP（Tavily）｜ Vercel

## 功能

- **和 AI 聊聊**：用一句話描述需求（日期、地點、人數），AI Agent 自己決定要查空房、天氣、景點或上網搜尋，結果以卡片呈現
- **行程購物車**：飯店和景點卡片都能「＋ 加入行程」，在地圖上看位置
- **行程規劃**：跟另一個 AI 討論造訪順序，建議的順序由使用者決定是否套用
- **AI 旅遊書**：依行程清單產生每日行程、介紹與小提醒，可另存成 PDF
- **自己搜尋飯店**：不經過 AI，直接查車站周邊的空房與房型

## 架構

```
瀏覽器 ──► 前端（Vue 3 + Vite）──► /api/*（FastAPI，Vercel 後端函式）
                                        │
                                        ├─ /api/chat ──► AI Agent（LangChain + Gemini）──► 工具
                                        │                                    ├─ find_place    → Nominatim（OpenStreetMap）／Open-Meteo Geocoding
                                        │                                    ├─ search_hotels → 樂天トラベル空室検索API
                                        │                                    ├─ get_weather   → Open-Meteo Forecast
                                        │                                    ├─ show_spots    → Nominatim（推薦景點的真實座標 → 可加入行程的卡片）
                                        │                                    └─ 網路搜尋      → Tavily（MCP）
                                        ├─ /api/trip-chat ──► 行程討論 Agent（讀行程清單＋直線距離）──► propose_order（建議順序）
                                        ├─ /api/guidebook ──► Gemini 結構化輸出（固定格式的旅遊書內容）
                                        └─ /api/hotels ──► 樂天トラベル空室検索API（手動搜尋）
```

- **前端**：Vue 3 + Vite，元件化（`frontend/src/components/`）。先列出有空房的飯店與最低價，點開再看該飯店的所有房型。
- **後端函式**：Python（FastAPI），保管 API 金鑰、檢查參數、快取。
- **部署**：Vercel。

| API | 用途 |
|---|---|
| `GET /api/hotels` | 車站周邊有空房的飯店，每間附最低價方案 |
| `GET /api/hotels/{hotelNo}/plans` | 單一飯店所有可訂的房型方案 |
| `POST /api/chat` | AI Agent：輸入一段文字，Agent 自己決定要呼叫哪些工具 |
| `POST /api/guidebook` | AI 旅遊書：根據行程清單寫旅遊書內容（固定格式），前端排版後可另存成 PDF |
| `POST /api/trip-chat` | 行程討論 Agent：送出對話和行程清單，回覆建議的造訪順序（由使用者決定是否套用） |

## Agent 設計

價格、空房、天氣只取自工具結果，以卡片顯示，不經 AI 改寫，避免幻覺；AI 負責理解需求、選擇工具與整理建議。前端會顯示 Agent 使用了哪些工具。

除了在 prompt 裡定規則，容易出錯的地方也用程式把關，不只靠 AI 遵守：

- **日期不明確就先問**：「下週五」「月底」這類說法容易算錯，Agent 會先請使用者給確切的入住日期和晚數，再查空房。
- **查不到就說查不到**：飯店名稱、價格只來自樂天的查詢結果；查詢失敗時直接告知，不會自己編出飯店。
- **AI 漏呼叫工具時的保底**：AI 有時只在文字裡寫出建議順序（例如「3 → 1 → 2」）而沒呼叫工具，程式會從文字中解析出來，照樣顯示「套用這個順序」按鈕；回覆裡假的工具呼叫文字也會被清掉。
- **工具結果再過濾**：天氣只保留旅行日期、重複的景點依座標去除、住宿日期重疊時由程式偵測並暫停排序，請使用者先決定住哪一間。
- **建議由使用者決定**：AI 建議的順序不會直接改掉清單，要使用者按下「套用」才會生效。

## 設計決策

### 資料來源：只用官方開放的 API

評估過的選項與結論：

| 來源 | 結論 | 原因 |
|---|---|---|
| Booking.com / Agoda API | ✗ | 僅限簽約的合作夥伴 |
| 爬取訂房網站 | ✗ | 違反使用條款，且不穩定 |
| Web search | ✗（空房、價格） | 無法帶日期查詢，資料不即時，LLM 容易把舊資訊當成現況；只用在景點、活動等一般資訊 |
| Google Hotels（第三方 API） | △ | 只有價格，無法判斷是否有空房；免費額度少 |
| **樂天トラベル空室検索API** | ✓ | 官方公開、免費、可直接判斷有無空房、可篩選禁菸房 |

### 為什麼需要後端

即使把金鑰放在環境變數，純前端網站在建置時仍會把它打包進 JavaScript，訪客打開開發者工具就看得到。因此由後端函式持有金鑰，前端只呼叫自己的 `/api/*`。

## 安全與隱私

- **金鑰只存在伺服器端**：放在 Vercel 環境變數，不進程式碼、不進 git 歷史，前端也拿不到。
- **後端防護**：參數白名單（避免被當成任意代理）、AI 相關 API 的每個 IP 頻率限制、飯店查詢的回應快取；沒有開放跨網域（CORS），其他網站的網頁無法直接呼叫。
- **錯誤處理不外洩**：錯誤訊息不回傳上游請求內容。
- **不蒐集個資**：不需要登入、不保存搜尋紀錄、不使用追蹤工具。行程清單只暫存在使用者自己的瀏覽器（sessionStorage），關掉分頁就清除。

## 使用條款遵循

本專案逐條檢視了 Rakuten Web Service 使用條款，並在設計上對應：

- 網站對外公開，任何人都能使用
- 即時查詢、即時顯示，不保存或轉發 API 資料
- 搜尋結果附上樂天的訂房連結，不混入其他訂房網站的連結
- 控制請求頻率並使用快取，避免對 API 造成負擔
- 標示資料來源，並聲明非官方服務

## 資料來源

| 資料 | 來源 |
|---|---|
| 飯店、空房、價格 | [Rakuten Web Service](https://webservice.rakuten.co.jp/) |
| 天氣預報 | [Open-Meteo](https://open-meteo.com/)（[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)） |
| 地名、景點座標、地圖 | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors（[ODbL](https://opendatacommons.org/licenses/odbl/)），透過 Nominatim 查詢 |
| 網路搜尋（景點、活動資訊） | [Tavily](https://tavily.com/) |
| AI 模型 | [Google Gemini](https://ai.google.dev/) |

## 聲明

- 本網站由個人開發與經營，**非樂天集團官方服務**，與樂天集團無合作關係。
- 空房與價格以各訂房頁面顯示為準，本網站不保證資料的正確性與即時性。
- 本網站不蒐集、不保存使用者的個人資料。

## 本機開發

需要 Python 3.10+ 與 Node.js 20.19+。

```bash
# 後端
pip install -r requirements-dev.txt
cp .env.example .env.local      # Windows 用 copy .env.example .env.local
python scripts/dev_server.py    # http://127.0.0.1:8000

# 前端（另開一個終端機）
cd frontend
npm install
npm run dev                     # 打開 http://localhost:5173
```

`.env.local` 需要填入自己的金鑰（說明見 `.env.example`）：

- `RAKUTEN_APPLICATION_ID`、`RAKUTEN_ACCESS_KEY`：[Rakuten Web Service](https://webservice.rakuten.co.jp/)
- `GEMINI_API_KEY`：[Google AI Studio](https://aistudio.google.com/)
- `TAVILY_API_KEY`（選填）：[Tavily](https://tavily.com/)，留空則 Agent 不會上網搜尋
