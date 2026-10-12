"""
樂天トラベル空室検索API 的呼叫與資料整理。

檔名開頭是底線，Vercel 不會把它當成一個獨立的 API，只給 index.py 匯入使用。

兩種查詢：
- search_hotels()：飯店清單，每間飯店只回傳一個代表方案（最低價）。
- search_plans()：指定一間飯店，列出所有可訂的房型方案（searchPattern=1）。
"""

import logging
import os

import requests

ENDPOINT = "https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426"
TIMEOUT = 15


class RakutenError(Exception):
    """呼叫樂天失敗。status 是要回給前端的 HTTP 狀態碼。"""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _config() -> tuple[dict, dict]:
    app_id = os.environ.get("RAKUTEN_APPLICATION_ID")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
    # 舊名稱 RAKUTEN_REFERER 也接受
    site = os.environ.get("RAKUTEN_ORIGIN") or os.environ.get("RAKUTEN_REFERER")
    if not (app_id and access_key and site):
        raise RakutenError(500, "伺服器尚未設定樂天 API 金鑰")
    # 樂天用 Origin 檢查來源網站；格式只能是 https://網域，不能有結尾斜線或路徑
    origin = "/".join(site.split("/")[:3])
    base = {
        "applicationId": app_id,
        "accessKey": access_key,
        "format": "json",
        "formatVersion": 2,
        "responseType": "middle",
    }
    return base, {"Origin": origin}


def _call(params: dict) -> dict | None:
    """呼叫樂天。查無空房（404）回傳 None。錯誤訊息不包含網址，避免金鑰外洩。"""
    base, headers = _config()
    try:
        resp = requests.get(ENDPOINT, params={**base, **params}, headers=headers, timeout=TIMEOUT)
    except requests.RequestException:
        raise RakutenError(502, "無法連線到樂天")

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        # 在伺服器紀錄樂天的錯誤代碼，方便除錯（例如 403 是哪一種拒絕）。
        # 只記錄錯誤代碼和說明，不記錄請求網址，避免金鑰出現在紀錄裡
        logging.getLogger(__name__).warning(
            "樂天回應 %s：%s", resp.status_code, _error_detail(resp)
        )
    if resp.status_code == 429:
        raise RakutenError(429, "查詢太頻繁，請稍後再試")
    if resp.status_code == 400:
        raise RakutenError(400, "查詢條件有誤")
    if resp.status_code != 200:
        raise RakutenError(502, f"樂天回應錯誤（{resp.status_code}）")
    try:
        return resp.json()
    except ValueError:
        raise RakutenError(502, "樂天回應格式錯誤")


def _error_detail(resp) -> str:
    """樂天有兩種錯誤格式：{"error", "error_description"} 和 {"errors": {"errorCode", "errorMessage"}}"""
    try:
        body = resp.json()
    except ValueError:
        return "（回應不是 JSON）"
    if not isinstance(body, dict):
        return "（無法解析）"
    errors = body.get("errors") if isinstance(body.get("errors"), dict) else {}
    code = body.get("error") or errors.get("errorCode")
    message = body.get("error_description") or errors.get("errorMessage")
    return f"{code}｜{message}"[:300]


def _split(item) -> tuple[dict, list[dict]]:
    """
    把一筆結果拆成（飯店基本資料, 方案列表）。

    formatVersion=2 時，一筆結果是 list：
    [{hotelBasicInfo}, {hotelDetailInfo}, {hotelReserveInfo}, {roomInfo: [...]}]
    roomInfo 裡是 roomBasicInfo、dailyCharge 交替出現，兩個一組是一個方案。
    """
    parts = item if isinstance(item, list) else item.get("hotel", [])
    basic, room_items = {}, []
    for part in parts:
        if "hotelBasicInfo" in part:
            basic = part["hotelBasicInfo"]
        if "roomInfo" in part:
            room_items.extend(part["roomInfo"])

    plans, current = [], None
    for entry in room_items:
        if "roomBasicInfo" in entry:
            current = {"basic": entry["roomBasicInfo"], "charge": {}}
            plans.append(current)
        elif "dailyCharge" in entry and current is not None:
            current["charge"] = entry["dailyCharge"]
    return basic, plans


def _plan_view(plan: dict) -> dict:
    b, c = plan["basic"], plan["charge"]
    return {
        "planId": b.get("planId"),
        "roomName": b.get("roomName"),
        "planName": b.get("planName"),
        "withBreakfast": b.get("withBreakfastFlag") == 1,
        "withDinner": b.get("withDinnerFlag") == 1,
        # chargeFlag 0：rakutenCharge 是每人價格；1：每房價格
        "unit": "room" if c.get("chargeFlag") == 1 else "person",
        "firstNightCharge": c.get("rakutenCharge"),
        "firstNightTotal": c.get("total"),  # 全部房客合計
        "stayDate": c.get("stayDate"),
        "reserveUrl": b.get("reserveUrl"),
    }


def _hotel_view(basic: dict) -> dict:
    return {
        "hotelNo": basic.get("hotelNo"),
        "name": basic.get("hotelName"),
        "special": basic.get("hotelSpecial"),
        "address": f"{basic.get('address1') or ''}{basic.get('address2') or ''}",
        "access": basic.get("access"),
        "nearestStation": basic.get("nearestStation"),
        "reviewAverage": basic.get("reviewAverage"),
        "reviewCount": basic.get("reviewCount"),
        "thumbnailUrl": basic.get("hotelThumbnailUrl"),
        "imageUrl": basic.get("hotelImageUrl"),
        "infoUrl": basic.get("hotelInformationUrl"),
        "planListUrl": basic.get("planListUrl"),
        "latitude": basic.get("latitude"),
        "longitude": basic.get("longitude"),
    }


def _common_params(checkin: str, checkout: str, adults: int, kinen: bool) -> dict:
    params = {"checkinDate": checkin, "checkoutDate": checkout, "adultNum": adults}
    if kinen:
        params["squeezeCondition"] = "kinen"
    return params


def search_hotels(
    checkin: str,
    checkout: str,
    adults: int,
    lat: float,
    lng: float,
    radius: float,
    kinen: bool,
    page: int = 1,
) -> dict:
    """飯店清單：每間飯店一筆，附上最低價方案。"""
    params = _common_params(checkin, checkout, adults, kinen)
    params.update(
        latitude=lat,
        longitude=lng,
        datumType=1,  # 1 = 世界測地系（WGS84），單位為度
        searchRadius=radius,
        hits=30,
        page=page,
    )
    data = _call(params)
    if data is None:
        return {"hotels": [], "page": 1, "pageCount": 0, "total": 0}

    hotels = []
    for item in data.get("hotels", []):
        basic, plans = _split(item)
        hotel = _hotel_view(basic)
        hotel["cheapestPlan"] = _plan_view(plans[0]) if plans else None
        hotels.append(hotel)

    paging = data.get("pagingInfo", {})
    return {
        "hotels": hotels,
        "page": paging.get("page", page),
        "pageCount": paging.get("pageCount", 1),
        "total": paging.get("recordCount", len(hotels)),
    }


def search_plans(hotel_no: int, checkin: str, checkout: str, adults: int, kinen: bool) -> dict:
    """單一飯店的所有可訂方案（searchPattern=1），依第一晚價格由低到高排序。"""
    params = _common_params(checkin, checkout, adults, kinen)
    params.update(hotelNo=hotel_no, searchPattern=1, hits=30)
    data = _call(params)
    if data is None:
        return {"hotel": None, "plans": []}

    hotel, plans = None, []
    for item in data.get("hotels", []):
        basic, item_plans = _split(item)
        if hotel is None and basic:
            hotel = _hotel_view(basic)
        plans.extend(_plan_view(p) for p in item_plans)

    plans.sort(key=lambda p: p["firstNightCharge"] if p["firstNightCharge"] is not None else float("inf"))
    return {"hotel": hotel, "plans": plans}
