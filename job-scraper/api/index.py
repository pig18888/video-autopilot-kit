"""Vercel serverless 入口：把整個 Flask app 掛在 /api/index，
vercel.json 的 rewrite 會把所有路徑導過來。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402,F401  (Vercel Python runtime 會偵測 `app`)
