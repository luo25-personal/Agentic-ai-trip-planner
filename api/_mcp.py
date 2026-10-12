"""
透過 MCP 取得外部工具：Tavily 網路搜尋。

Tavily 在自己的伺服器上提供 MCP Server（https://mcp.tavily.com/mcp/），
連上後用 client.get_tools() 取得工具清單，再交給 Agent 使用。

只挑出「搜尋」工具：
- 不用 crawl / map（會爬別人的網站，有使用條款風險，也很耗額度）
- 不用 extract（讀整頁內容，token 太多）
- 不用 research（深度研究，一次用掉大量額度）

沒有設定 TAVILY_API_KEY 或連線失敗時，回傳空清單，Agent 照樣可以運作，只是不能上網搜尋。
"""

import json
import logging
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

TAVILY_MCP_URL = "https://mcp.tavily.com/mcp/"

# 每次搜尋的預設參數：基本深度、最多 5 筆、不要圖片，大約每次 1 credit
SEARCH_DEFAULTS = {"search_depth": "basic", "max_results": 5, "include_images": False}

logger = logging.getLogger(__name__)
_cached_tools = None  # 工具清單只要取一次，之後重複使用


def _is_search_tool(name: str) -> bool:
    name = name.lower()
    # research 是深度研究，一次會用掉大量額度，也排除
    return "search" in name and not any(w in name for w in ("crawl", "map", "extract", "research"))


async def get_search_tools() -> list:
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []

    client = MultiServerMCPClient(
        {
            "tavily": {
                "url": TAVILY_MCP_URL,
                "transport": "streamable_http",
                "headers": {
                    "Authorization": f"Bearer {api_key}",
                    "DEFAULT_PARAMETERS": json.dumps(SEARCH_DEFAULTS),
                },
            }
        }
    )
    try:
        tools = await client.get_tools()
    except Exception as err:  # 連不上就先不用搜尋，不讓整個 Agent 失敗
        logger.warning("無法連線到 Tavily MCP：%s", type(err).__name__)
        return []

    _cached_tools = [t for t in tools if _is_search_tool(t.name)]
    return _cached_tools


def is_search_tool(name: str) -> bool:
    """給 _agent.py 判斷某個工具呼叫是不是網路搜尋。
    只認真的有載入的工具名稱：AI 偶爾會自己編出不存在的工具（例如 search_spots），不能只看名稱有沒有 search。"""
    return any(t.name == name for t in _cached_tools or [])
