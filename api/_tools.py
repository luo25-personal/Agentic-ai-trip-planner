"""
AI Agent 可以使用的工具（LangChain @tool）。

LangChain 會從函式名稱、型別和 docstring 自動產生工具說明交給 Gemini，
所以 docstring 要寫清楚：工具做什麼、每個參數是什麼。

每個工具都用 response_format="content_and_artifact"，回傳兩份資料：
- content：精簡版，交給 Gemini 閱讀（省 token）
- artifact：完整資料，不給 Gemini，留給前端顯示成卡片

價格、空房、天氣一律來自 API，不讓 AI 自己編。
"""

import json
import math
import os
import re
import threading
import time
import unicodedata
from datetime import date, timedelta

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

import _rakuten

TIMEOUT = 10
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 16  # Open-Meteo 最多預報 16 天

# WMO 天氣代碼 → 中文
WEATHER_CODES = {
    0: "晴", 1: "大致晴朗", 2: "多雲", 3: "陰",
    45: "霧", 48: "霧",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "凍毛毛雨", 57: "凍毛毛雨",
    61: "小雨", 63: "雨", 65: "大雨", 66: "凍雨", 67: "凍雨",
    71: "小雪", 73: "雪", 75: "大雪", 77: "雪粒",
    80: "陣雨", 81: "陣雨", 82: "強陣雨",
    85: "陣雪", 86: "強陣雪",
    95: "雷雨", 96: "雷雨伴冰雹", 99: "雷雨伴冰雹",
}


class ToolError(Exception):
    """工具執行失敗，訊息會回給 Gemini，讓它決定怎麼跟使用者說明。"""


def _content(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _error(err: Exception) -> tuple[str, None]:
    return _content({"error": str(err)}), None


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolError(f"{field} 格式錯誤，必須是 YYYY-MM-DD")


def _get_json(url: str, params: dict) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        raise ToolError("外部服務暫時無法連線")


# ── 工具 1：地名 → 座標 ─────────────────────────────────────────
#
# 優先用 OpenStreetMap 的 Nominatim（支援「青森駅」這種日文，能定位到車站本身），
# 查不到或被拒絕時，改用 Open-Meteo（只支援英文拼音，定位到城市中心）。
#
# Nominatim 使用政策 https://operations.osmfoundation.org/policies/nominatim/ ：
# - 全站每秒最多 1 次 → 下面用鎖控制間隔，並快取結果
# - 要用 User-Agent 標明應用程式（不能用 requests 預設值）
# - 要標示「© OpenStreetMap contributors」（在網頁頁尾）
# - 要能隨時停用 → 在 Vercel 把環境變數 GEOCODER 設成 open-meteo 即可，不用改程式

GEOCODER = (os.environ.get("GEOCODER") or "nominatim").lower()
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "agentic-ai-trip-planner/1.0 (+https://agentic-ai-trip-planner.vercel.app)"
NOMINATIM_MIN_INTERVAL = 1.1  # 秒，比規定的 1 秒再保守一點

_place_cache: dict[str, list] = {}
_nominatim_lock = threading.Lock()
_nominatim_last_call = 0.0


def _area(address: dict) -> str:
    """Nominatim 的地址拆解 → 「京都府京都市東山区」這種短地址。"""
    parts = [
        address.get("province") or address.get("state"),
        address.get("city") or address.get("town") or address.get("village"),
        address.get("city_district") or address.get("suburb"),
    ]
    return "".join(dict.fromkeys(p for p in parts if p))  # 去掉重複（例如東京都）


def _nominatim(name: str, extra: dict | None = None, limit: int = 5) -> list[dict]:
    global _nominatim_last_call
    with _nominatim_lock:  # 同一時間只送一個請求，且間隔至少 1.1 秒
        wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _nominatim_last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    "q": name,
                    "format": "jsonv2",
                    "countrycodes": "jp",
                    "accept-language": "ja",
                    "limit": limit,
                    "addressdetails": 1,
                    **(extra or {}),
                },
                headers={"User-Agent": NOMINATIM_USER_AGENT},
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            raise ToolError("地點服務暫時無法連線")
        finally:
            _nominatim_last_call = time.monotonic()

    if resp.status_code != 200:  # 429 太頻繁、403 被拒絕等
        raise ToolError(f"地點服務回應錯誤（{resp.status_code}）")
    try:
        results = resp.json()
    except ValueError:
        raise ToolError("地點服務回應格式錯誤")
    if not isinstance(results, list):
        raise ToolError("地點服務回應格式錯誤")
    return [
        {
            "name": r.get("name") or r.get("display_name", "").split(",")[0],
            "address": r.get("display_name"),
            "area": _area(r.get("address") or {}),
            "kind": f"{r.get('category')}/{r.get('type')}",  # 例如 railway/station
            "latitude": round(float(r["lat"]), 5),
            "longitude": round(float(r["lon"]), 5),
        }
        for r in results
        if "lat" in r and "lon" in r
    ]


def _open_meteo(name: str) -> list[dict]:
    data = _get_json(
        GEOCODE_URL,
        {"name": name, "count": 5, "language": "ja", "countryCode": "JP", "format": "json"},
    )
    return [
        {
            "name": r.get("name"),
            "address": r.get("admin1"),
            "kind": "city",
            "latitude": round(r["latitude"], 4),
            "longitude": round(r["longitude"], 4),
        }
        for r in data.get("results") or []
    ]


@tool(response_format="content_and_artifact", parse_docstring=True)
def find_place(name: str, name_en: str = ""):
    """把日本的地名、車站或景點名稱轉成經緯度。查飯店或天氣之前，如果還不知道座標，先呼叫這個工具。

    Args:
        name: 日文地名，車站要加「駅」，例如「青森駅」「新宿駅」「金沢」「嵐山」
        name_en: 同一個地點所在城市的英文羅馬拼音，例如 "Aomori"，查不到日文時備用
    """
    name, name_en = name.strip(), (name_en or "").strip()
    key = f"{name}|{name_en}"
    if key in _place_cache:
        return _content({"places": _place_cache[key]}), None

    places = []
    if GEOCODER == "nominatim" and name:
        try:
            places = _nominatim(name)
        except ToolError:
            places = []  # 改用備援
    if not places:
        for query in dict.fromkeys(q for q in (name_en, name) if q):  # 先英文、再原文，不重複
            try:
                places = _open_meteo(query)
            except ToolError:
                continue
            if places:
                break
    if not places:
        return _error(ToolError(f"找不到「{name}」，請換一個寫法或改查所在城市"))

    places = places[:3]
    if len(_place_cache) < 500:  # 快取，避免重複查詢同一個地名
        _place_cache[key] = places
    return _content({"places": places}), None


# ── 工具：把推薦的景點標示成卡片 ─────────────────────────────
#
# AI 推薦景點時呼叫，每個景點附上所在地區（例如「清水寺／京都市」）。
# 後端用 Nominatim 全日本搜尋，再挑地址裡有那個地區的結果：
# - 剛好一個地點符合 → 做成可以「＋ 加入行程」的卡片
# - 同地區有好幾個同名地點、或地區對不上 → 把候選交給 AI，請它回問使用者
# 座標一律來自 OpenStreetMap，不讓 AI 自己寫，避免編造。


class SpotQuery(BaseModel):
    name: str = Field(description="景點的日文正式名稱，例如「清水寺」「姫路城」")
    area: str = Field(description="景點所在的市區町村或都道府縣（日文），例如「京都市」「姫路市」「箱根町」")
    note: str = Field(default="", description="一句話特色（繁體中文），會顯示在景點卡片上")


MAX_SPOTS = 6
SAME_PLACE_KM = 1.0  # 同名結果距離 1 km 內，視為同一個地點（OSM 常同時有「點」和「範圍」兩筆）
AREA_SUFFIX = re.compile(r"(都|道|府|県|市|区|町|村)$")

_spot_cache: dict[str, dict] = {}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace(" ", "").replace("　", "")


def _variants(text: str) -> set[str]:
    """「京都市」→ {京都市, 京都}。原文也保留，因為「京都」本身去掉「都」會變成「京」。"""
    full = _norm(text)
    return {v for v in (full, AREA_SUFFIX.sub("", full)) if len(v) >= 2}


def _area_score(place: dict, area: str) -> int:
    """地址的每一段（東山区、京都市、京都府…）有幾段符合使用者的地區，0 表示不在這個地區。
    逐段比對而不是整串搜尋，避免「京都」誤配到「東京都」。"""
    wanted, full = _variants(area), _norm(area)
    score = 0
    for part in (place.get("address") or "").split(","):
        part = _norm(part)
        if len(part) < 2 or part.isdigit() or part == "日本":
            continue
        # 「京都市」=「京都」；或地區寫得比較細，例如 AI 寫「京都市東山区」，地址有「東山区」和「京都市」
        if _variants(part) & wanted or part in full:
            score += 1
    return score


def _best_in_area(places: list[dict], area: str) -> list[dict]:
    """只留下最符合地區的結果：寫「京都市東山区」時，東山区的比只有京都市的優先。"""
    scored = [(_area_score(p, area), p) for p in places]
    best = max((s for s, _ in scored), default=0)
    return _distinct([p for s, p in scored if s and s == best])


def _distinct(places: list[dict]) -> list[dict]:
    """去掉距離很近的重複結果，保留排序在前面（比較知名）的那筆。"""
    kept = []
    for p in places:
        if all(_km(p, k) > SAME_PLACE_KM for k in kept):
            kept.append(p)
    return kept


def _km(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(
        math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"])
    )
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _lookup_spot(name: str, area: str) -> dict:
    """回傳 {"status": "found" | "ambiguous" | "notInArea" | "notFound", ...}"""
    key = f"{name}|{area}"
    if key in _spot_cache:
        return _spot_cache[key]

    results = _nominatim(name, limit=10)
    matches = _best_in_area(results, area)
    if not matches:  # 只用名稱找不到時，加上地區再找一次（小地方常排不進前 10 名）
        more = _nominatim(f"{name} {area}", limit=5)
        results = results + more
        matches = _best_in_area(more, area)

    if len(matches) == 1:
        hit = matches[0]
        out = {
            "status": "found",
            "spot": {
                "name": name,  # 用 AI 寫的名稱，前端才能對應到回覆裡的景點
                "osmName": hit["name"],
                "area": hit["area"],
                "latitude": hit["latitude"],
                "longitude": hit["longitude"],
            },
        }
    elif matches:
        out = {"status": "ambiguous", "candidates": [m["area"] for m in matches[:3]]}
    elif results:
        out = {"status": "notInArea", "foundIn": list(dict.fromkeys(r["area"] for r in _distinct(results)))[:3]}
    else:
        out = {"status": "notFound"}

    if len(_spot_cache) < 500:
        _spot_cache[key] = out
    return out


@tool(response_format="content_and_artifact", parse_docstring=True)
def show_spots(spots: list[SpotQuery]):
    """推薦具體的景點、寺廟、公園、商圈、餐廳時呼叫，系統會查出位置並顯示成可以加入行程的卡片。

    Args:
        spots: 要顯示的景點，最多 6 個，可以在不同縣市。每個景點填 name（日文正式名稱）、area（所在地區）、note（一句話特色），例如 [{"name": "清水寺", "area": "京都市", "note": "清水舞台可以俯瞰京都市區"}]
    """
    if GEOCODER != "nominatim":
        return _error(ToolError("目前無法標示景點位置"))

    queries, seen = [], set()
    for q in spots:
        q = q if isinstance(q, SpotQuery) else SpotQuery.model_validate(q)
        name, area = q.name.strip()[:60], q.area.strip()[:30]
        if name and (name, area) not in seen:
            seen.add((name, area))
            queries.append((name, area, q.note.strip()[:80]))
    queries = queries[:MAX_SPOTS]
    if not queries:
        return _error(ToolError("spots 不能是空的"))

    found, ambiguous, not_in_area, not_found = [], [], [], []
    for name, area, note in queries:
        try:
            result = _lookup_spot(name, area)
        except ToolError as err:
            return _error(err)  # 服務連不上就停止，不要一直重試
        if result["status"] == "found":
            found.append({**result["spot"], "note": note})
        elif result["status"] == "ambiguous":
            ambiguous.append({"name": name, "area": area, "candidates": result["candidates"]})
        elif result["status"] == "notInArea":
            not_in_area.append({"name": name, "area": area, "foundIn": result["foundIn"]})
        else:
            not_found.append(name)

    content = _content({
        "shownAsCards": [s["name"] for s in found],
        "ambiguous": ambiguous,
        "notInArea": not_in_area,
        "notFound": not_found,
    })
    return content, ({"type": "spots", "spots": found} if found else None)


# ── 工具 2：查空房 ──────────────────────────────────────────────

def _summarize_hotels(result: dict) -> dict:
    hotels = []
    for h in result["hotels"][:10]:
        plan = h.get("cheapestPlan") or {}
        hotels.append(
            {
                "name": h["name"],
                "nearestStation": h.get("nearestStation"),
                "review": h.get("reviewAverage"),
                "firstNightPrice": plan.get("firstNightCharge"),
                "priceUnit": "每房" if plan.get("unit") == "room" else "每人",
            }
        )
    return {
        "totalHotelsWithVacancy": result["total"],
        "top10ByRakutenOrder": hotels,
        "note": "價格是第一晚、含稅。完整清單與訂房連結會以卡片顯示給使用者。",
    }


@tool(response_format="content_and_artifact", parse_docstring=True)
def search_hotels(
    latitude: float,
    longitude: float,
    checkin: str,
    checkout: str,
    adults: int,
    radius_km: float = 1.0,
    non_smoking: bool = False,
):
    """查詢指定座標附近、指定日期有空房的飯店（資料來自樂天トラベル），回傳每間飯店的最低價方案。

    查不到代表該條件下沒有空房。

    Args:
        latitude: 緯度
        longitude: 經度
        checkin: 入住日 YYYY-MM-DD
        checkout: 退房日 YYYY-MM-DD
        adults: 大人人數，1–10
        radius_km: 搜尋半徑 0.1–3.0 km，預設 1
        non_smoking: 是否只要禁菸房
    """
    try:
        start = _parse_date(checkin, "checkin")
        end = _parse_date(checkout, "checkout")
        if start < date.today():
            raise ToolError("入住日不能早於今天")
        if not 1 <= (end - start).days <= 9:
            raise ToolError("住宿晚數必須是 1–9 晚")
        adults = max(1, min(int(adults), 10))
        radius = max(0.1, min(float(radius_km or 1.0), 3.0))
        result = _rakuten.search_hotels(
            checkin, checkout, adults, latitude, longitude, radius, bool(non_smoking)
        )
    except ToolError as err:
        return _error(err)
    except _rakuten.RakutenError as err:
        return _error(err.message)

    result["query"] = {
        "checkin": checkin,
        "checkout": checkout,
        "adults": adults,
        "kinen": bool(non_smoking),
        "nights": (end - start).days,
        "lat": latitude,
        "lng": longitude,
        "radius": radius,
    }
    return _content(_summarize_hotels(result)), {"type": "hotels", **result}


# ── 工具 3：查天氣 ──────────────────────────────────────────────

@tool(response_format="content_and_artifact", parse_docstring=True)
def get_weather(latitude: float, longitude: float, start_date: str, end_date: str):
    """查詢指定座標的每日天氣預報（最高/最低氣溫、天氣、降雨機率）。

    只能查今天起 16 天內的日期，更遠的日期會回傳無法預報。

    Args:
        latitude: 緯度
        longitude: 經度
        start_date: 開始日期 YYYY-MM-DD
        end_date: 結束日期 YYYY-MM-DD
    """
    try:
        start = _parse_date(start_date, "start_date")
        end = _parse_date(end_date, "end_date")
        if end < start:
            raise ToolError("end_date 不能早於 start_date")
        today = date.today()
        last = today + timedelta(days=FORECAST_DAYS - 1)
        if start > last:
            result = {
                "available": False,
                "forecastUntil": last.isoformat(),
                "message": f"{start_date} 超過預報範圍（只能查到 {last.isoformat()}），無法提供天氣預報",
            }
            return _content(result), {"type": "weather", **result}
        # 行程後半段超過 16 天時，只查得到前面幾天，剩下的要告訴 AI 和使用者
        beyond = end > last
        start, end = max(start, today), min(end, last)

        data = _get_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "Asia/Tokyo",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
    except ToolError as err:
        return _error(err)

    daily = data.get("daily") or {}
    days = []
    for i, day in enumerate(daily.get("time", [])):
        code = daily["weather_code"][i]
        days.append(
            {
                "date": day,
                "weather": WEATHER_CODES.get(code, "—"),
                "code": code,
                "max": daily["temperature_2m_max"][i],
                "min": daily["temperature_2m_min"][i],
                "rain": daily["precipitation_probability_max"][i],
            }
        )
    result = {"available": True, "forecastUntil": last.isoformat(), "days": days}
    if beyond:
        result["note"] = f"{(last + timedelta(days=1)).isoformat()} 之後超過預報範圍，沒有天氣預報"
    return _content(result), {"type": "weather", **result}


TOOLS = [find_place, search_hotels, get_weather, show_spots]
