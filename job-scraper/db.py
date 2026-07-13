"""儲存層：職缺歷史追蹤、去重、薪資趨勢統計。

兩種後端，依環境變數自動切換：
  - 預設：SQLite（本機檔案，零設定）
  - 雲端：Supabase Postgres（設 SUPABASE_URL + SUPABASE_KEY 即啟用），
    透過 PostgREST HTTP API 存取，無需額外套件（只用 requests）。

在 Vercel 等無法寫入本地磁碟的環境，若未設 Supabase，SQLite 會落在 /tmp
（可運作，但歷史資料在機器回收時會重置）。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from scraper import Job


def _default_sqlite_path() -> str:
    if os.environ.get("JOB_DB_PATH"):
        return os.environ["JOB_DB_PATH"]
    if os.environ.get("VERCEL"):  # Vercel 檔案系統唯讀，只有 /tmp 可寫
        return "/tmp/jobs.db"
    return os.path.join(os.path.dirname(__file__), "jobs.db")


DB_PATH = _default_sqlite_path()

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or ""


def _use_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_key(j: Job) -> str:
    return j.job_url or f"{j.source}:{j.title}:{j.company}"


def _job_row(j: Job, keyword: str, now: str) -> dict:
    return {
        "job_url": _job_key(j),
        "source": j.source,
        "title": j.title,
        "company": j.company,
        "salary": j.salary,
        "salary_min": j.salary_min,
        "location": j.location,
        "description": j.description,
        "date": j.date,
        "company_url": j.company_url,
        "keyword": keyword,
        "first_seen": now,
        "last_seen": now,
    }


# ---------------------------------------------------------------- Supabase 後端

def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _sb_get(params: dict) -> list[dict]:
    import requests

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/jobs", params=params, headers=_sb_headers(), timeout=15
    )
    resp.raise_for_status()
    return resp.json()


def _sb_save_jobs(jobs: list[Job], keyword: str) -> list[Job]:
    import requests

    now = _now()
    keys = [_job_key(j) for j in jobs]

    # 分批查出已存在的 job_url（避免 URL 過長）
    existing: set[str] = set()
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        quoted = ",".join('"' + k.replace('"', '') + '"' for k in chunk)
        rows = _sb_get({"select": "job_url", "job_url": f"in.({quoted})"})
        existing.update(r["job_url"] for r in rows)

    new_jobs = [j for j in jobs if _job_key(j) not in existing]

    # upsert：新職缺插入（first_seen=now）；舊職缺更新 last_seen / salary
    if new_jobs:
        payload = [_job_row(j, keyword, now) for j in new_jobs]
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/jobs",
            json=payload,
            headers=_sb_headers({"Prefer": "resolution=merge-duplicates"}),
            timeout=20,
        )
        resp.raise_for_status()

    for j in jobs:
        if _job_key(j) in existing:
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/jobs",
                params={"job_url": f"eq.{_job_key(j)}"},
                json={"last_seen": now, "salary": j.salary, "salary_min": j.salary_min},
                headers=_sb_headers(),
                timeout=15,
            )
            resp.raise_for_status()

    return new_jobs


def _sb_get_history(keyword: str | None, limit: int) -> list[dict]:
    params = {"select": "*", "order": "first_seen.desc", "limit": str(limit)}
    if keyword:
        params["keyword"] = f"eq.{keyword}"
    return _sb_get(params)


def _sb_salary_trend(keyword: str | None) -> list[dict]:
    params = {"select": "salary_min,first_seen", "salary_min": "not.is.null",
              "limit": "10000"}
    if keyword:
        params["keyword"] = f"eq.{keyword}"
    rows = _sb_get(params)

    buckets: dict[str, list[int]] = {}
    for r in rows:
        day = str(r.get("first_seen") or "")[:10]
        if day and r.get("salary_min") is not None:
            buckets.setdefault(day, []).append(int(r["salary_min"]))
    return [
        {"date": day, "avg_min": round(sum(v) / len(v)), "count": len(v)}
        for day, v in sorted(buckets.items())
    ]


def _sb_list_keywords() -> list[str]:
    rows = _sb_get({"select": "keyword", "limit": "10000"})
    return sorted({r["keyword"] for r in rows if r.get("keyword")})


# ---------------------------------------------------------------- SQLite 後端

def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str = None) -> None:
    if _use_supabase():
        return  # 資料表由雲端一次性建立
    path = path or DB_PATH
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_url     TEXT PRIMARY KEY,
                source      TEXT,
                title       TEXT,
                company     TEXT,
                salary      TEXT,
                salary_min  INTEGER,
                location    TEXT,
                description TEXT,
                date        TEXT,
                company_url TEXT,
                keyword     TEXT,
                first_seen  TEXT,
                last_seen   TEXT
            );
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT,
                keyword   TEXT,
                total     INTEGER,
                new_count INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_keyword ON jobs(keyword);
            CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
            """
        )


def save_jobs(jobs: Iterable[Job], keyword: str, path: str = None) -> list[Job]:
    """寫入/更新職缺，回傳「本次新出現」的職缺清單（用於通知）。

    已存在的職缺只更新 last_seen；不存在的視為新職缺並記 first_seen。
    """
    jobs = list(jobs)
    if _use_supabase():
        return _sb_save_jobs(jobs, keyword)

    path = path or DB_PATH
    init_db(path)
    now = _now()
    new_jobs: list[Job] = []

    with _connect(path) as conn:
        for j in jobs:
            key = _job_key(j)
            row = conn.execute("SELECT job_url FROM jobs WHERE job_url = ?", (key,)).fetchone()
            if row is None:
                new_jobs.append(j)
                conn.execute(
                    """INSERT INTO jobs
                       (job_url, source, title, company, salary, salary_min, location,
                        description, date, company_url, keyword, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (key, j.source, j.title, j.company, j.salary, j.salary_min, j.location,
                     j.description, j.date, j.company_url, keyword, now, now),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET last_seen = ?, salary = ?, salary_min = ? WHERE job_url = ?",
                    (now, j.salary, j.salary_min, key),
                )

        conn.execute(
            "INSERT INTO scrape_runs (ts, keyword, total, new_count) VALUES (?,?,?,?)",
            (now, keyword, len(jobs), len(new_jobs)),
        )
    return new_jobs


def get_history(keyword: str | None = None, limit: int = 300, path: str = None) -> list[dict]:
    if _use_supabase():
        return _sb_get_history(keyword, limit)

    path = path or DB_PATH
    init_db(path)
    with _connect(path) as conn:
        if keyword:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE keyword = ? ORDER BY first_seen DESC LIMIT ?",
                (keyword, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY first_seen DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def salary_trend(keyword: str | None = None, path: str = None) -> list[dict]:
    """依「首次出現日期」統計每日新職缺的平均月薪下限與數量。

    回傳 [{date, avg_min, count}, ...]（依日期由舊到新）。
    """
    if _use_supabase():
        return _sb_salary_trend(keyword)

    path = path or DB_PATH
    init_db(path)
    where = "WHERE salary_min IS NOT NULL"
    params: tuple = ()
    if keyword:
        where += " AND keyword = ?"
        params = (keyword,)
    with _connect(path) as conn:
        rows = conn.execute(
            f"""SELECT substr(first_seen, 1, 10) AS date,
                       ROUND(AVG(salary_min)) AS avg_min,
                       COUNT(*) AS count
                FROM jobs {where}
                GROUP BY date ORDER BY date""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def list_keywords(path: str = None) -> list[str]:
    if _use_supabase():
        return _sb_list_keywords()

    path = path or DB_PATH
    init_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT keyword FROM jobs WHERE keyword != '' ORDER BY keyword"
        ).fetchall()
    return [r["keyword"] for r in rows]
