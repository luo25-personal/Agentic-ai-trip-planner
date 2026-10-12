"""
階段 0 驗證：呼叫一次樂天トラベル空室検索API，看回傳長什麼樣子。

用法（在專案根目錄執行）：
    python scripts/rakuten_probe.py --checkin 2026-11-20 --checkout 2026-11-21
    python scripts/rakuten_probe.py --checkin 2026-11-20 --checkout 2026-11-21 --kinen
    python scripts/rakuten_probe.py --checkin 2026-11-20 --checkout 2026-11-21 --hotel-no 12345
    python scripts/rakuten_probe.py --checkin 2026-11-20 --checkout 2026-11-21 --hotel-no 12345 --all-plans

預設地點：青森站，半徑 1 km，2 位大人。

注意：
- 金鑰從 .env.local 讀取（已被 .gitignore 排除）。
- 每執行一次只呼叫 API 一次，請不要寫迴圈大量呼叫。
- 原始回傳存到 samples/（已被 .gitignore 排除，不可公開，樂天條款第 10 條 1 項 (9)）。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

ENDPOINT = "https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426"
ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict:
    """讀取 .env.local（簡單的 KEY=VALUE 格式），不需要額外安裝套件。"""
    if not path.exists():
        sys.exit(f"找不到 {path.name}。請把 .env.example 複製成 .env.local，再填入金鑰。")
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description="樂天空室検索API 測試")
    parser.add_argument("--checkin", required=True, help="入住日 YYYY-MM-DD")
    parser.add_argument("--checkout", required=True, help="退房日 YYYY-MM-DD")
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument("--lat", type=float, default=40.8286, help="緯度（預設：青森站）")
    parser.add_argument("--lng", type=float, default=140.7337, help="經度（預設：青森站）")
    parser.add_argument("--radius", type=float, default=1.0, help="搜尋半徑 km（0.1–3.0）")
    parser.add_argument("--hotel-no", help="指定飯店編號；指定時會忽略經緯度")
    parser.add_argument("--kinen", action="store_true", help="只要禁菸房")
    parser.add_argument(
        "--all-plans", action="store_true", help="列出每個房型方案（searchPattern=1），而不是每間飯店只列一個"
    )
    args = parser.parse_args()

    env = load_env(ROOT / ".env.local")
    for key in ("RAKUTEN_APPLICATION_ID", "RAKUTEN_ACCESS_KEY"):
        if not env.get(key):
            sys.exit(f".env.local 裡缺少 {key}")
    # 舊的 RAKUTEN_REFERER 也接受，會自動轉成 Origin 格式
    site = env.get("RAKUTEN_ORIGIN") or env.get("RAKUTEN_REFERER")
    if not site:
        sys.exit(".env.local 裡缺少 RAKUTEN_ORIGIN")

    params = {
        "applicationId": env["RAKUTEN_APPLICATION_ID"],
        "accessKey": env["RAKUTEN_ACCESS_KEY"],
        "format": "json",
        "formatVersion": 2,
        "responseType": "middle",
        "checkinDate": args.checkin,
        "checkoutDate": args.checkout,
        "adultNum": args.adults,
    }
    if args.hotel_no:
        params["hotelNo"] = args.hotel_no
    else:
        params.update(
            latitude=args.lat,
            longitude=args.lng,
            datumType=1,
            searchRadius=args.radius,
        )
    if args.kinen:
        params["squeezeCondition"] = "kinen"
    if args.all_plans:
        params["searchPattern"] = 1

    # 樂天用 Origin 檢查來源網站（只送 Referer 會得到 403 REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING）。
    # Origin 只能是 https://網域，不能有結尾斜線或路徑。
    origin = "/".join(site.split("/")[:3])  # https://xxx.vercel.app/ → https://xxx.vercel.app
    headers = {"Origin": origin}

    try:
        resp = requests.get(ENDPOINT, params=params, headers=headers, timeout=15)
    except requests.RequestException as exc:
        # 不印出完整網址，避免金鑰出現在畫面或紀錄裡
        sys.exit(f"連線失敗：{type(exc).__name__}")

    print(f"HTTP {resp.status_code}")

    try:
        data = resp.json()
    except ValueError:
        print("回傳不是 JSON，前 300 字：")
        print(resp.text[:300])
        return

    # 存原始回傳，方便之後分析（samples/ 不會進 git）
    samples = ROOT / "samples"
    samples.mkdir(exist_ok=True)
    tag = ("kinen" if args.kinen else "all") + ("_plans" if args.all_plans else "")
    where = f"hotel{args.hotel_no}" if args.hotel_no else "geo"
    out = samples / f"{datetime.now():%Y%m%d-%H%M%S}_{args.checkin}_{where}_{tag}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"原始回傳已存到 {out.relative_to(ROOT)}")

    if resp.status_code == 404:
        print("→ 查無結果（not_found）。用 hotelNo 查詢時，通常代表該日期客滿或沒有符合條件的方案。")
        return
    if resp.status_code != 200:
        # 樂天有兩種錯誤格式：{"error", "error_description"} 和 {"errors": {"errorCode", "errorMessage"}}
        errs = data.get("errors") or {}
        code = data.get("error") or errs.get("errorCode")
        msg = data.get("error_description") or errs.get("errorMessage")
        print(f"→ 錯誤：{code} / {msg}")
        if resp.status_code == 429:
            print("  請求太頻繁，請等一陣子再試。")
        return

    hotels = data.get("hotels", [])
    paging = data.get("pagingInfo", {})
    unit_label = "筆" if args.all_plans else "間飯店"
    print(f"→ 有空房：共 {paging.get('recordCount', len(hotels))} {unit_label}（本頁 {len(hotels)} 筆，第 {paging.get('page')}/{paging.get('pageCount')} 頁）\n")

    for item in hotels:
        # formatVersion=2 時，每間飯店是一個 list：[{hotelBasicInfo}, {hotelDetailInfo}, {roomInfo...}, ...]
        parts = item if isinstance(item, list) else item.get("hotel", [])
        basic, rooms, reserve = {}, [], {}
        for part in parts:
            if "hotelBasicInfo" in part:
                basic = part["hotelBasicInfo"]
            if "roomInfo" in part:
                rooms.extend(part["roomInfo"])  # 可能有好幾個 roomInfo 區塊，全部收集
            if "hotelReserveInfo" in part:
                reserve = part["hotelReserveInfo"]
        print(f"■ {basic.get('hotelName')}（hotelNo: {basic.get('hotelNo')}）")
        print(
            f"  最低價：{basic.get('hotelMinCharge')} 円｜最近車站：{basic.get('nearestStation')}"
            f"｜可訂方案數：{reserve.get('reserveRecordCount')}"
        )
        for room in rooms[:40]:  # 最多印 20 個方案（每個方案 2 筆）
            if "roomBasicInfo" in room:
                rb = room["roomBasicInfo"]
                print(f"  - {rb.get('roomName')}｜{rb.get('planName')}")
            if "dailyCharge" in room:
                # total = 全部房客合計；rakutenCharge = 每人（chargeFlag 0）或每房（chargeFlag 1）
                dc = room["dailyCharge"]
                unit = "每房" if dc.get("chargeFlag") == 1 else "每人"
                print(
                    f"    {dc.get('stayDate')}：合計 {dc.get('total')} 円"
                    f"（{unit} {dc.get('rakutenCharge')} 円）"
                )
        print()


if __name__ == "__main__":
    main()
