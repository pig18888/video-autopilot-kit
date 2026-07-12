# 104 職缺自動查詢網站

靈感來自 [kobojp/scraper_104_1111](https://github.com/kobojp/scraper_104_1111)（用 Selenium 爬 104／1111）。
這裡改用 **104 官方 JSON API**（`requests` 直接呼叫），不需要 Selenium／瀏覽器，
更穩定也更快，並做成一個可以在瀏覽器操作的網站。

## 功能

- 網頁輸入 **關鍵字 / 地區 / 最低月薪 / 抓取頁數**，即時查詢 104 職缺
- 自動 **分頁抓取**（每頁約 20 筆）
- **薪資解析**：把「月薪 40,000~60,000元」「年薪 600,000元」換算成可比較的月薪下限，用來過濾
  （時薪、面議無法比較，一律保留）
- 一鍵 **匯出 CSV**（含 BOM，Excel 直接開不亂碼）
- 純命令列也能用：`python scraper.py python 台北市 40000`

## 安裝與啟動

```bash
cd job-scraper
pip install -r requirements.txt
python app.py
# 瀏覽器開 http://127.0.0.1:5000
```

> 注意：此程式需要能連到 `www.104.com.tw`。若在受限網路（如某些 CI／沙箱）會連不到。

## 檔案

| 檔案 | 說明 |
|------|------|
| `scraper.py` | 104 API 客戶端：查詢、分頁、薪資解析、過濾、CSV 轉換 |
| `app.py` | Flask 網站：`/` 查詢頁、`/export.csv` 匯出 |
| `templates/index.html` | 前端頁面 |
| `requirements.txt` | 相依套件（Flask、requests）|

## 可延伸方向

- 加入 **1111 人力銀行**（另寫一支 `scraper_1111.py` 合併結果）
- **排程自動抓取 + Email 通知**（搭配 cron／APScheduler + smtplib/yagmail，複刻原專案的 Heroku 定時寄信）
- 存進資料庫做歷史追蹤、去重、薪資趨勢圖表

## 地區代碼

`scraper.py` 的 `AREA_CODES` 內建常用縣市，可依 104 的 area code 自行擴充。

## 注意事項

請遵守 104 的服務條款與 `robots.txt`，控制抓取頻率（程式已內建每頁 0.6 秒延遲），
僅供個人求職／學習用途。
