# 職缺自動查詢網站（104 + 1111）

靈感來自 [kobojp/scraper_104_1111](https://github.com/kobojp/scraper_104_1111)。
改用各家人力銀行的 **JSON API**（`requests` 直接呼叫），不需 Selenium／瀏覽器，
更穩定也更快，並做成一個可在瀏覽器操作、能定時通知、會累積歷史的網站。

## 功能

- **多來源查詢**：同時抓 **104 + 1111**，可自選來源，依 `job_url` 去重
- 網頁輸入 **關鍵字 / 地區 / 最低月薪 / 頁數**，即時查詢
- **薪資解析**：把「月薪 40,000~60,000元」「年薪 600,000元」換算成月薪下限用於過濾
  （時薪、面議無法比較，一律保留）
- **一鍵匯出 CSV**（含 BOM，Excel 直接開不亂碼）
- **歷史追蹤（SQLite）**：每次查詢自動存檔、去重，`/history` 可回顧
- **薪資趨勢圖**：`/trends` 用內建 SVG 折線圖畫出每日新職缺平均月薪（無前端套件）
- **定時抓取 + Email 通知**：`notify.py` 定時查詢，只把「新出現」的職缺寄給你

## 安裝與啟動

```bash
cd job-scraper
pip install -r requirements.txt
python app.py
# 瀏覽器開 http://127.0.0.1:5000
```

> 需要能連到 `www.104.com.tw` 與 `www.1111.com.tw`。受限網路（某些 CI／沙箱）會連不到。

## 定時抓取 + Email 通知

```bash
cp config.example.py config.py     # 填入搜尋條件與 SMTP 設定（config.py 已被 gitignore）
python notify.py --dry-run         # 先試跑：只抓取＋存檔，不寄信
python notify.py                   # 依 config 決定是否寄信
python notify.py --loop 720        # 內建排程：每 720 分鐘跑一次（常駐）
```

用系統 cron 更省資源（每天 9 點）：

```cron
0 9 * * *  cd /path/to/job-scraper && python notify.py >> notify.log 2>&1
```

Gmail 需在 Google 帳號開啟兩步驟驗證後，用**應用程式密碼**當作 `SMTP_PASSWORD`。

## 檔案

| 檔案 | 說明 |
|------|------|
| `app.py` | Flask 網站：`/` 查詢、`/export.csv` 匯出、`/history` 歷史、`/trends` 趨勢圖 |
| `scraper.py` | 104 API 客戶端 + 共用 `Job` 資料結構、薪資解析、CSV 轉換 |
| `scraper_1111.py` | 1111 API 客戶端（防禦性欄位解析）|
| `sources.py` | 整合多來源查詢、去重、單一來源失敗容錯 |
| `db.py` | SQLite：職缺去重存檔、歷史查詢、薪資趨勢統計 |
| `notify.py` | 定時抓取 + 新職缺 Email 通知（支援 cron 或 `--loop`）|
| `config.example.py` | 設定範例（搜尋條件 + SMTP）|
| `templates/` | 前端頁面 |

## 已知限制

- **1111 API**：本專案在受限網路環境開發，無法對 1111 實際連線驗證欄位對應。
  `scraper_1111.py` 以「多欄位名稱容忍」的方式解析，若對不上，請依實際回應調整
  `_extract_jobs` 內的欄位。104 則為已驗證的正式 API 參數。
- 請遵守各站服務條款與 `robots.txt`，控制頻率（已內建每頁 0.6 秒延遲），僅供個人求職／學習用途。

## 可延伸方向

- 加入更多來源（CakeResume、Yourator…）只要再寫一支 `scraper_xxx.py` 並註冊進 `sources.SOURCES`
- 趨勢頁加入分來源比較、薪資分布直方圖
- 改用 APScheduler / Celery 做更完整的排程與重試
