"""
AI Agent（LangChain create_agent）：讀懂使用者的文字，自己決定要呼叫哪些工具，最後用中文回覆。

create_agent 內部會跑「問模型 → 執行工具 → 把結果交回模型」的迴圈，
直到模型不再呼叫工具、給出最終回答。

跑完後，從訊息紀錄裡整理出：
- 最終回覆文字
- 用了哪些工具（前端顯示 Agent 的決策過程）
- 工具查到的完整飯店、天氣資料（ToolMessage.artifact，前端顯示成卡片）
- 網路搜尋用到的來源網址

工具有兩種來源：
- _tools.py：自己寫的工具（樂天、天氣、地點、景點卡片）
- _mcp.py：透過 MCP 連到 Tavily 取得的網路搜尋工具
MCP 工具需要非同步執行，所以這裡用 async / ainvoke。
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError, GoogleRateLimitError
from langgraph.errors import GraphRecursionError

import _mcp
import _tools

# 下面已明確指定使用 GEMINI_API_KEY；電腦上若也設了 GOOGLE_API_KEY，
# Google SDK 仍會印出「Using GOOGLE_API_KEY」的警告，但實際用的是 GEMINI_API_KEY，所以關掉這個警告
logging.getLogger("google_genai._api_client").setLevel(logging.ERROR)
# Tavily 工具的參數格式有些欄位 Gemini 不支援，LangChain 會自動略過並印警告；不影響使用，所以關掉
logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

# 免費額度：Flash-Lite 每天約 500 次，Flash 只有約 20 次，所以預設用 Flash-Lite
DEFAULT_MODEL = "gemini-flash-lite-latest"
MAX_TOOL_ROUNDS = 6  # 最多呼叫幾輪工具，避免無限迴圈和用光免費額度

SYSTEM_PROMPT = """你是日本旅遊規劃助理，使用繁體中文回答。今天是 {today}，天氣預報最遠只能查到 {forecast_until}。

你可以使用工具：
- find_place：地名轉經緯度
- search_hotels：查詢有空房的飯店（樂天トラベル）
- get_weather：查詢天氣預報（今天起 16 天內）
- show_spots：把推薦的景點顯示成可以「＋ 加入行程」的卡片（系統會查出真實位置）
{search_line}
只能呼叫上面列出的工具，名稱要完全一樣，不要自己組合出新的工具名稱。

規則：
1. 飯店、空房、價格、天氣只能根據工具結果回答，絕對不可以自己編造數字或飯店名稱。
   search_hotels 失敗或沒有結果時，只說明「目前查不到空房資料」並建議換日期、擴大範圍或稍後再試，
   不可以用自己的知識推薦任何飯店名稱。
2. 旅行日期一定要明確：
   - 使用者說要去旅行（例如「要去」「想去」「下個月去京都」），但沒有給明確的出發日和回程日（或住幾晚）時，
     先不要呼叫任何工具，用一句話詢問具體日期，例如「請問是幾月幾號出發、住幾晚呢？」。
     可以順便提出你的理解讓使用者確認，例如「11 月底是指 11/28 出發、住 1 晚嗎？」，但使用者確認前不要當成已知。
   - 算明確的：有寫出「月/日」的日期，例如「11/20」「10/16–10/18」「11/20 起住 2 晚」「11/20 出發，兩天一夜」。
     換算成 YYYY-MM-DD；沒說年份就用最近的未來日期。
     退房日＝入住日＋住幾晚：「住一晚」「兩天一夜」＝1 晚，「三天兩夜」＝2 晚。例如 10/23 入住、住 1 晚，退房日是 10/24。
   - 不算明確的，一定要先問，不要自己換算：
     - 相對的說法：「明天」「後天」「這週五」「下週五」「這個週末」「三天後」
     - 範圍或模糊的說法：「11 月底」「下個月」「秋天」「連假」「三個月後」「過年」
     詢問時說明原因並請使用者給「月/日」，例如：「為了避免日期弄錯，請告訴我確切的入住日期（例如 10/23）和住幾晚。」
   - 只是問一般資訊、沒有說要去旅行（例如「京都有什麼紅葉景點？」），可以直接回答，不用問日期。
   - 查飯店還需要地點和人數，缺少的話跟日期一起問，一次問完，不要自己猜。
3. 查飯店或天氣前，先用 find_place 取得座標：name 填日文地名（車站要用「駅」，例如「青森站」→「青森駅」），name_en 填所在城市的英文拼音（例如 "Aomori"）。
4. 飯店的完整清單和訂房連結會以卡片顯示在你的回覆下方。查到飯店後，先用一句話總結（找到幾間），
   再推薦 2–3 間；使用者要求列出全部或更多飯店時，才列出更多。每間飯店固定用這個格式（名稱那一行只放粗體名稱，名稱照工具結果原文）：
   - **飯店名稱**
     - 特色：一句話
   不要在文字裡寫任何飯店價格或評分，系統會自動從樂天資料顯示在每間飯店旁邊，避免數字出錯。
   總結裡的價格範圍也不要寫，只寫找到幾間。
5. 景點、活動、營業時間等需要最新資訊時，用網路搜尋查詢，每個問題最多搜尋 2 次，並在回覆最後列出 1–3 個參考來源網址。
   沒有搜尋工具時，可以根據一般知識提供，但要說明「營業時間與票價請以官方資訊為準」。
   飯店價格和空房不要用網路搜尋，一律用 search_hotels。
   參考來源放在回覆最後，先寫一行「參考來源：」，再用 [網站標題](網址) 的格式列出，不要放在景點或飯店的條列裡面。
6. 這個聊天負責「挑選」想去的地方，排順序和安排行程是「行程規劃」分頁的工作：
   - 使用者要求排行程、安排順序、幾天幾夜的規劃時，不要寫逐日行程、時段或時間表，
     改成照下面的景點格式一個一個推薦（每個景點各自一張卡片），
     最後一句固定提醒：「把想去的地方按「＋ 加入行程」，再到「行程規劃」分頁讓 AI 幫你排順序。」
   推薦具體的景點、寺廟、公園、商圈、餐廳時：
   - 只要推薦具體地點，一定要呼叫 show_spots，系統會把查到位置的地點顯示成卡片。
     每個景點填 name（日文正式名稱）、area（所在的市區町村或都道府縣，日文，例如「京都市」「姫路市」「箱根町」）、note（一句話特色）。
     不需要先查座標；不同縣市的景點可以放在同一次呼叫，一次最多 6 個。
   - 文字中每個景點固定用這個格式，名稱必須和 show_spots 的 name 完全相同：
     - **景點名稱**
       - 特色：一句話
   - show_spots 回傳結果的處理：
     - ambiguous：同一地區有好幾個同名地點，列出 candidates 的地區，問使用者是哪一個；使用者回答後，用更精確的 area 再呼叫一次。
     - notInArea：指定地區找不到，但 foundIn 的地區有同名地點，問使用者是不是指那裡。
     - notFound：照樣介紹，但說明「無法標示位置，不能加入行程」。
   - 使用者只是問一般問題（例如交通、天氣）時不用呼叫 show_spots。
7. 天氣固定照下面的方式處理，不要混用。Open-Meteo 只能預報今天起 16 天內（到 {forecast_until}）：
   - get_weather 的 start_date、end_date 一定要是使用者的旅行日期（例如入住日到退房日），不可以為了查到資料改查今天或其他日期。
   - 日期在 {forecast_until}（含）之前：用 get_weather 查預報。查到後系統會在回覆最上面顯示每天的天氣卡片，並標示資料來源，
     所以文字裡不要列出每天的天氣、氣溫或降雨機率，只用一句話給穿著或攜帶建議（例如「氣溫偏涼，記得帶外套和雨具」），
     而且這句要放在整個回覆的第一句（緊接在天氣卡片下面），飯店、景點等其他內容放在後面。
   - 行程有一部分在 {forecast_until} 之後（get_weather 回傳 note）：說明哪幾天天氣預報 API 還查不到；有網路搜尋時，可以補充往年同期平均，
     並寫明「這幾天是透過網路搜尋找到的往年同期平均，不是預報」。
   - 日期在 {forecast_until} 之後：不要呼叫 get_weather（一定查不到）。回覆的天氣段落第一句固定寫：
     「出發日超過 16 天，天氣預報 API 還查不到；以下是透過網路搜尋找到的往年同期平均，不是預報。」
     接著搜尋「地點＋月份＋平均氣溫」，寫出平均最高、最低氣溫和穿著建議，並列出參考來源。
     沒有網路搜尋時，改寫「出發日超過 16 天，天氣預報 API 還查不到，建議出發前兩週再查」。
8. 只回答與日本旅遊有關的問題。回覆簡潔，適合在手機上閱讀，可以用條列。
9. 不要要求使用者提供姓名、電話、護照等個人資料。
"""


class AgentError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AgentError(500, "伺服器尚未設定 Gemini API 金鑰")
    # 跟 create_agent(model="google_genai:...") 一樣是用字串指定模型，
    # 改用 init_chat_model 只是為了多設定 temperature 和重試次數
    return init_chat_model(
        f"google_genai:{os.environ.get('GEMINI_MODEL') or DEFAULT_MODEL}",
        # 明確指定金鑰：電腦上如果另外設了 GOOGLE_API_KEY，SDK 預設會優先用那個
        google_api_key=api_key,
        temperature=0.4,  # 讓回答穩定一點
        max_retries=1,  # 免費額度有限，失敗不要一直重試
    )


WEEKDAYS = "一二三四五六日"
TAIWAN_TZ = timezone(timedelta(hours=8))  # 台灣時間（使用者在台灣）。Vercel 伺服器用 UTC，直接用 date.today() 早上會差一天


def _today() -> date:
    return datetime.now(TAIWAN_TZ).date()


async def build_agent():
    search_tools = await _mcp.get_search_tools()  # 沒有設定 Tavily 金鑰時是空清單
    return create_agent(
        model=_model(),
        tools=[*_tools.TOOLS, *search_tools],
        system_prompt=SYSTEM_PROMPT.format(
            search_line=(
                f"- {'、'.join(t.name for t in search_tools)}：網路搜尋，查景點、活動、祭典、營業時間、交通等最新資訊"
                if search_tools
                else "- （目前沒有網路搜尋工具）"
            ),
            today=f"{_today().isoformat()}（星期{WEEKDAYS[_today().weekday()]}）",
            forecast_until=(date.today() + timedelta(days=_tools.FORECAST_DAYS - 1)).isoformat(),
        ),
    )


def _to_messages(messages: list[dict]) -> list:
    return [
        HumanMessage(m["text"]) if m["role"] == "user" else AIMessage(m["text"])
        for m in messages
    ]


def _is_error(msg: ToolMessage) -> bool:
    if msg.status == "error":  # MCP 工具失敗時會標記 error
        return True
    try:
        return "error" in json.loads(msg.content)
    except (TypeError, ValueError):
        return False


URL_PATTERN = re.compile(r"https?://[^\s\"'<>)\]]+")


def _urls(content) -> list[str]:
    """從搜尋結果裡找出網址，給前端顯示「參考來源」。"""
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return URL_PATTERN.findall(text)


def _collect(history: list) -> dict:
    """從 Agent 的訊息紀錄整理出前端需要的資料。"""
    steps, hotels, weather, reply, sources, spots = [], None, None, "", [], []
    calls = {}  # tool_call_id → 這次呼叫的步驟

    for msg in history:
        if isinstance(msg, AIMessage):
            for call in msg.tool_calls:
                step = {
                    "tool": call["name"],
                    "args": call["args"],
                    "ok": True,
                    "search": _mcp.is_search_tool(call["name"]),  # 前端用來顯示「搜尋網路」
                }
                calls[call["id"]] = step
                steps.append(step)
            if msg.text:
                reply = msg.text  # 最後一則有文字的 AI 訊息就是最終回覆
        elif isinstance(msg, ToolMessage):
            step = calls.get(msg.tool_call_id)
            if step and _is_error(msg):
                step["ok"] = False
                # 在伺服器終端機記錄失敗原因，方便除錯（只記工具名稱和錯誤訊息，不記使用者輸入的內容）
                logging.getLogger(__name__).warning(
                    "工具 %s 失敗：%s", step["tool"], str(msg.content)[:300]
                )
            if step and step["ok"] and step["search"]:
                sources += [u for u in _urls(msg.content) if u not in sources]
            artifact = msg.artifact or {}
            if artifact.get("type") == "hotels":
                hotels = artifact
            elif artifact.get("type") == "weather":
                weather = artifact
            elif artifact.get("type") == "spots":
                # AI 可能用不同名稱查到同一個地點（例如「アスパム」和「青森県観光物産館アスパム」），用座標去重複
                for spot in artifact["spots"]:
                    if all(_tools._km(spot, s) > 0.1 for s in spots):
                        spots.append(spot)

    return {
        "reply": reply.strip(),
        "steps": steps,
        "hotels": hotels,
        "weather": _trip_weather(weather, hotels),
        "sources": sources[:8],
        "spots": spots,
    }


def _trip_weather(weather: dict | None, hotels: dict | None) -> dict | None:
    """
    有查飯店時，天氣只留住宿期間（入住日～退房日）的日子。
    AI 偶爾會拿「今天起 16 天」去查天氣，跟旅行日期完全無關；這種天氣卡片不顯示，避免誤導。
    """
    query = (hotels or {}).get("query") or {}
    checkin, checkout = query.get("checkin"), query.get("checkout")
    if not weather or not weather.get("available") or not checkin or not checkout:
        return weather
    days = [d for d in weather.get("days", []) if checkin <= d["date"] <= checkout]
    if not days:
        return None
    out = {**weather, "days": days}
    out.pop("note", None)
    if checkout > weather.get("forecastUntil", checkout):
        out["note"] = "後面的日期超過預報範圍"
    return out


class TooManySteps(Exception):
    """Agent 呼叫工具的輪數超過上限。"""


async def invoke(agent, messages: list[dict]) -> list:
    """
    執行 Agent，回傳「這次新產生的訊息」。
    兩個 Agent（旅遊規劃、行程討論）共用這段錯誤處理。
    """
    try:
        result = await agent.ainvoke(
            {"messages": _to_messages(messages)},
            # 每一輪工具 = 模型 + 工具兩個步驟
            config={"recursion_limit": MAX_TOOL_ROUNDS * 2 + 1},
        )
    except GraphRecursionError:
        raise TooManySteps()
    except GoogleRateLimitError:
        raise AgentError(429, "AI 使用量已達上限，請過一陣子再試")
    except ChatGoogleGenerativeAIError:
        raise AgentError(502, "AI 服務暫時無法使用")
    except Exception as err:  # 其他意外錯誤（例如搜尋服務斷線），只記錄類型，不把細節回傳給前端
        logging.getLogger(__name__).exception("Agent 執行失敗：%s", type(err).__name__)
        raise AgentError(502, "查詢時發生錯誤，請稍後再試")
    # 只看這次新產生的訊息，不重複計算之前的對話
    return result["messages"][len(messages):]


async def run(messages: list[dict]) -> dict:
    """
    messages：[{"role": "user" | "model", "text": "..."}]，最後一則必須是 user。
    回傳：{"reply": 文字, "steps": 使用過的工具, "hotels": 飯店資料或 None, "weather": 天氣資料或 None}
    """
    agent = await build_agent()
    try:
        new_messages = await invoke(agent, messages)
    except TooManySteps:
        return {
            "reply": "這個問題需要查詢的資料太多了，請把需求拆小一點再問一次。",
            "steps": [], "hotels": None, "weather": None, "sources": [], "spots": [],
        }

    out = _collect(new_messages)
    if not out["reply"]:
        out["reply"] = "抱歉，我沒有產生回覆，請換個說法再試一次。"
    return out
