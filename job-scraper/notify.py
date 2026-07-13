"""定時抓取 + 新職缺 Email 通知。

用法：
  1) cp config.example.py config.py 並填好設定
  2) 手動跑一次（不寄信、只印出）：  python notify.py --dry-run
     實際執行（依 config 決定是否寄信）： python notify.py
  3) 排程：用系統 cron 或下方的 --loop 內建排程

  # crontab 範例：每天早上 9 點跑一次
  0 9 * * *  cd /path/to/job-scraper && python notify.py >> notify.log 2>&1

  # 或用內建迴圈（每 N 分鐘跑一次，需保持程式常駐）
  python notify.py --loop 720
"""

from __future__ import annotations

import argparse
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.utils import formataddr

from db import save_jobs
from scraper import Job
from sources import search_all

try:
    import config
except ImportError:
    config = None


def _build_email_html(keyword: str, new_jobs: list[Job]) -> str:
    rows = "".join(
        f"<tr>"
        f"<td>{j.source}</td>"
        f"<td><a href='{j.job_url}'>{j.title}</a></td>"
        f"<td>{j.company}</td>"
        f"<td>{j.salary}</td>"
        f"<td>{j.location}</td>"
        f"</tr>"
        for j in new_jobs
    )
    return (
        f"<h3>「{keyword}」新增 {len(new_jobs)} 筆職缺</h3>"
        f"<table border='1' cellpadding='6' cellspacing='0' "
        f"style='border-collapse:collapse;font-family:sans-serif'>"
        f"<tr><th>來源</th><th>職缺</th><th>公司</th><th>薪資</th><th>地區</th></tr>"
        f"{rows}</table>"
    )


def _send_email(subject: str, html: str) -> None:
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("職缺通知", config.EMAIL_FROM))
    msg["To"] = ", ".join(config.EMAIL_TO)

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())


def run_once(dry_run: bool = False) -> None:
    if config is None:
        sys.exit("找不到 config.py，請先 `cp config.example.py config.py` 並填好設定。")

    for spec in config.SEARCHES:
        keyword = spec["keyword"]
        jobs, errors = search_all(
            keyword,
            area=spec.get("area", "全部"),
            min_salary=spec.get("min_salary", 0),
            max_pages=getattr(config, "MAX_PAGES", 3),
            sources=getattr(config, "SOURCES", None),
            job_type=spec.get("job_type", "不限"),
        )
        for src, err in errors.items():
            print(f"[warn] {src} 查詢失敗：{err}")

        new_jobs = save_jobs(jobs, keyword)
        print(f"[{keyword}] 共 {len(jobs)} 筆，其中新職缺 {len(new_jobs)} 筆")

        if not new_jobs:
            continue

        html = _build_email_html(keyword, new_jobs)
        subject = f"[職缺通知] 「{keyword}」新增 {len(new_jobs)} 筆"

        if dry_run or not getattr(config, "EMAIL_ENABLED", False):
            print(f"  (未寄信) 主旨：{subject}")
        else:
            _send_email(subject, html)
            print(f"  已寄信給 {config.EMAIL_TO}")


def main() -> None:
    parser = argparse.ArgumentParser(description="定時抓取職缺並寄送新職缺通知")
    parser.add_argument("--dry-run", action="store_true", help="只抓取與存檔，不實際寄信")
    parser.add_argument("--loop", type=int, metavar="MINUTES", help="每 N 分鐘重複執行（常駐）")
    args = parser.parse_args()

    if args.loop:
        print(f"啟動內建排程：每 {args.loop} 分鐘執行一次（Ctrl+C 停止）")
        while True:
            run_once(dry_run=args.dry_run)
            time.sleep(args.loop * 60)
    else:
        run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
