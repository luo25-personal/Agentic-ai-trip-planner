"""
本機開發用的後端伺服器（只提供 /api/*）。

用法（在專案根目錄執行，開兩個終端機）：
    終端機 1：python scripts/dev_server.py          → 後端 http://127.0.0.1:8000
    終端機 2：cd frontend && npm run dev            → 前端 http://localhost:5173

瀏覽器打開 http://localhost:5173。前端的 /api 請求會由 Vite 轉給這個伺服器
（設定在 frontend/vite.config.js）。

金鑰從 .env.local 讀取。正式網站在 Vercel 上，不會用到這個檔案。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> None:
    if not path.exists():
        sys.exit(f"找不到 {path.name}。請把 .env.example 複製成 .env.local，再填入金鑰。")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    # 先讀金鑰、設定路徑，再匯入後端程式
    load_env(ROOT / ".env.local")
    sys.path.insert(0, str(ROOT))

    import uvicorn

    from api.index import app

    # 127.0.0.1：只有這台電腦連得到
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
