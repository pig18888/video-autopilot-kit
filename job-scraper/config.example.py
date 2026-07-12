"""設定範例。複製成 config.py 後填入你的資料（config.py 已被 .gitignore 忽略）。

    cp config.example.py config.py
"""

# 要定時追蹤的搜尋條件（可多組）
SEARCHES = [
    {"keyword": "python 後端", "area": "台北市", "min_salary": 45000},
    {"keyword": "資料分析",     "area": "全部",   "min_salary": 40000},
]

# 每組最多抓幾頁
MAX_PAGES = 3

# 要查詢的來源
SOURCES = ["104", "1111"]

# ---- Email 通知（用 SMTP 寄新職缺；Gmail 需用「應用程式密碼」）----
EMAIL_ENABLED = False          # 設 True 才會實際寄信
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "you@gmail.com"
SMTP_PASSWORD = "your-app-password"   # 建議改用環境變數，不要硬編在檔案裡
EMAIL_FROM = "you@gmail.com"
EMAIL_TO = ["you@gmail.com"]
