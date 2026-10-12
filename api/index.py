"""
後端 API（Vercel Python 函式）。所有 /api/* 請求都會由 vercel.json 轉到這裡。

GET /api/hotels                 飯店清單（每間飯店附最低價方案）
GET /api/hotels/{hotelNo}/plans 單一飯店的所有房型方案
POST /api/chat                  AI Agent：輸入一段文字，Agent 自己決定要查什麼
POST /api/trip-chat             行程討論 Agent：根據行程清單討論造訪順序
POST /api/guidebook             AI 旅遊書：根據行程清單寫旅遊書內容

金鑰只從環境變數讀取，不會出現在前端或回應內容裡。
"""

import os
import sys
import time
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 讓同資料夾的 _rakuten.py 在本機和 Vercel 上都能匯入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _agent  # noqa: E402
import _guidebook  # noqa: E402
import _planner  # noqa: E402
import _rakuten  # noqa: E402

app = FastAPI(title="Agentic AI Trip Planner API", docs_url=None, redoc_url=None)

MAX_NIGHTS = 9
MAX_DAYS_AHEAD = 365
# 同樣的查詢，Vercel 的 CDN 快取 5 分鐘，減少打到樂天的次數
CACHE_HEADERS = {"Cache-Control": "public, s-maxage=300, stale-while-revalidate=60"}


def _check_dates(checkin: date, checkout: date) -> None:
    today = date.today()
    if checkin < today:
        raise HTTPException(400, "入住日不能早於今天")
    if checkin > today + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(400, f"入住日最多只能查 {MAX_DAYS_AHEAD} 天後")
    nights = (checkout - checkin).days
    if nights < 1:
        raise HTTPException(400, "退房日必須晚於入住日")
    if nights > MAX_NIGHTS:
        raise HTTPException(400, f"最多查詢 {MAX_NIGHTS} 晚")


def _ok(body: dict) -> JSONResponse:
    return JSONResponse(body, headers=CACHE_HEADERS)


def _fail(err: _rakuten.RakutenError) -> HTTPException:
    return HTTPException(err.status, err.message)


@app.get("/api/hotels")
def hotels(
    checkin: date,
    checkout: date,
    adults: int = Query(2, ge=1, le=10),
    lat: float = Query(..., ge=20, le=46),  # 日本範圍
    lng: float = Query(..., ge=122, le=154),
    radius: float = Query(1.0, ge=0.1, le=3.0),
    kinen: bool = False,
    page: int = Query(1, ge=1, le=100),
):
    _check_dates(checkin, checkout)
    try:
        result = _rakuten.search_hotels(
            checkin.isoformat(), checkout.isoformat(), adults, lat, lng, radius, kinen, page
        )
    except _rakuten.RakutenError as err:
        raise _fail(err)
    result["nights"] = (checkout - checkin).days
    return _ok(result)


@app.get("/api/hotels/{hotel_no}/plans")
def plans(
    hotel_no: int,
    checkin: date,
    checkout: date,
    adults: int = Query(2, ge=1, le=10),
    kinen: bool = False,
):
    _check_dates(checkin, checkout)
    try:
        result = _rakuten.search_plans(
            hotel_no, checkin.isoformat(), checkout.isoformat(), adults, kinen
        )
    except _rakuten.RakutenError as err:
        raise _fail(err)
    result["nights"] = (checkout - checkin).days
    return _ok(result)


# ── AI Agent ─────────────────────────────────────────────────

MAX_MESSAGES = 12  # 最多帶幾則對話紀錄
MAX_TEXT = 500  # 每則訊息最多幾個字
RATE_LIMIT = 20  # 每個 IP 在 RATE_WINDOW 秒內最多問幾次（兩個聊天和旅遊書共用）
RATE_WINDOW = 600

# 簡易頻率限制：記在記憶體裡。Vercel 可能同時開好幾個執行個體，
# 所以這只是「盡量」限制，主要用來擋住同一個人短時間狂按。
_recent: dict[str, deque] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    q = _recent[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


class Message(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=MAX_TEXT * 4)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


def _check_chat(messages: list[dict], request: Request) -> list[dict]:
    """兩個聊天 API 共用：整理對話紀錄、檢查長度、頻率限制。"""
    messages = messages[-MAX_MESSAGES:]
    if messages[0]["role"] != "user":
        messages = messages[1:]
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(400, "最後一則訊息必須是使用者的提問")
    if len(messages[-1]["text"]) > MAX_TEXT:
        raise HTTPException(400, f"訊息太長了，請在 {MAX_TEXT} 字以內")

    client_host = request.client.host if request.client else ""
    ip = (request.headers.get("x-forwarded-for") or client_host).split(",")[0].strip()
    if _rate_limited(ip):
        raise HTTPException(429, "提問太頻繁了，請過幾分鐘再試")
    return messages


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    messages = _check_chat([m.model_dump() for m in body.messages], request)
    try:
        return await _agent.run(messages)
    except _agent.AgentError as err:
        raise HTTPException(err.status, err.message)


# ── 行程討論 Agent ───────────────────────────────────────────

MAX_TRIP_ITEMS = 20


class TripItem(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    type: Literal["hotel", "spot"]
    name: str = Field(min_length=1, max_length=100)
    lat: float = Field(ge=20, le=46)  # 日本範圍
    lng: float = Field(ge=122, le=154)
    checkin: date | None = None
    checkout: date | None = None
    area: str | None = Field(default=None, max_length=60)  # 景點所在區域，例如「京都府京都市東山区」


class TripChatRequest(ChatRequest):
    items: list[TripItem] = Field(max_length=MAX_TRIP_ITEMS)


@app.post("/api/trip-chat")
async def trip_chat(body: TripChatRequest, request: Request):
    messages = _check_chat([m.model_dump() for m in body.messages], request)
    if len({item.id for item in body.items}) != len(body.items):
        raise HTTPException(400, "行程清單有重複的項目")
    items = [item.model_dump(mode="json") for item in body.items]
    try:
        return await _planner.run(messages, items)
    except _agent.AgentError as err:
        raise HTTPException(err.status, err.message)


# ── AI 旅遊書 ───────────────────────────────────────────────


class GuidebookRequest(BaseModel):
    items: list[TripItem] = Field(min_length=1, max_length=MAX_TRIP_ITEMS)


@app.post("/api/guidebook")
async def guidebook(body: GuidebookRequest, request: Request):
    if len({item.id for item in body.items}) != len(body.items):
        raise HTTPException(400, "行程清單有重複的項目")
    client_host = request.client.host if request.client else ""
    ip = (request.headers.get("x-forwarded-for") or client_host).split(",")[0].strip()
    if _rate_limited(ip):  # 跟兩個聊天 API 共用頻率限制
        raise HTTPException(429, "使用太頻繁了，請過幾分鐘再試")
    try:
        return await _guidebook.generate([item.model_dump(mode="json") for item in body.items])
    except _guidebook.GuidebookError as err:
        raise HTTPException(err.status, err.message)
