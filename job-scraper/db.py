"""SQLite 儲存層：職缺歷史追蹤、去重、薪資趨勢統計。

只用 Python 內建 sqlite3，不需額外套件。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from scraper import Job

DB_PATH = os.environ.get("JOB_DB_PATH", os.path.join(os.path.dirname(__file__), "jobs.db"))


def _connect(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str = DB_PATH) -> None:
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_jobs(jobs: Iterable[Job], keyword: str, path: str = DB_PATH) -> list[Job]:
    """寫入/更新職缺，回傳「本次新出現」的職缺清單（用於通知）。

    已存在的職缺只更新 last_seen；不存在的視為新職缺並記 first_seen。
    """
    init_db(path)
    now = _now()
    jobs = list(jobs)
    new_jobs: list[Job] = []

    with _connect(path) as conn:
        for j in jobs:
            key = j.job_url or f"{j.source}:{j.title}:{j.company}"
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


def get_history(keyword: str | None = None, limit: int = 300, path: str = DB_PATH) -> list[dict]:
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


def salary_trend(keyword: str | None = None, path: str = DB_PATH) -> list[dict]:
    """依「首次出現日期」統計每日新職缺的平均月薪下限與數量。

    回傳 [{date, avg_min, count}, ...]（依日期由舊到新）。
    """
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


def list_keywords(path: str = DB_PATH) -> list[str]:
    init_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT keyword FROM jobs WHERE keyword != '' ORDER BY keyword"
        ).fetchall()
    return [r["keyword"] for r in rows]
