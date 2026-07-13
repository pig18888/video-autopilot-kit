"""Yourator（新創職缺平台）爬蟲。

Yourator 有公開的 JSON API（網站前端就是打這支），不需要瀏覽器：
    GET https://www.yourator.co/api/v4/jobs?term[]=<關鍵字>&page=<頁>

註：本檔在受限網路的沙箱中無法實際連線驗證，欄位以多種可能名稱
防禦性解析；若對不上，跑 diag.py 把實際回應貼回即可修正。
"""

from __future__ import annotations

import re
import time
from typing import Any

import requests

from scraper import Job

SEARCH_API = "https://www.yourator.co/api/v4/jobs"
BASE_URL = "https://www.yourator.co"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.yourator.co/jobs",
}


def _first(item: dict, *keys: str, default: Any = "") -> Any:
    for k in keys:
        v = item.get(k)
        if v:
            return v
    return default


def _parse_salary(text: str) -> int | None:
    """解析 Yourator 的薪資字串成月薪下限。

    範例：
      "40K ~ 70K TWD / 月"   -> 40000
      "600K ~ 1M TWD / 年"   -> 50000
      "月薪 40,000 元"        -> 40000
      "時薪 200 TWD"          -> None
      "面議"                  -> None
    """
    if not text:
        return None
    t = text.replace(",", "")
    if "時" in t:
        return None

    nums: list[int] = []
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([KkMm]?)", t):
        v = float(num)
        if unit in ("K", "k"):
            v *= 1_000
        elif unit in ("M", "m"):
            v *= 1_000_000
        nums.append(int(v))
    nums = [n for n in nums if n >= 1000]  # 過濾掉雜訊小數字
    if not nums:
        return None

    low = min(nums)
    if "年" in t:
        return low // 12
    return low if low >= 10000 else None


def _norm_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return BASE_URL + (path if path.startswith("/") else "/" + path)


def _unwrap(data: dict) -> dict:
    """Yourator 的回應包在 payload 這一層：{"payload": {"jobs": [...]}}。"""
    inner = data.get("payload")
    return inner if isinstance(inner, dict) else data


def _extract_jobs(payload: dict) -> list[Job]:
    payload = _unwrap(payload)
    items = payload.get("jobs") or payload.get("data") or []
    jobs: list[Job] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        company = item.get("company") or {}
        company_name = ""
        company_path = ""
        if isinstance(company, dict):
            company_name = _first(company, "brand", "name", "title")
            company_path = _first(company, "path", "url")
        elif isinstance(company, str):
            company_name = company

        salary = str(_first(item, "salary", "salary_range", "salaryDesc"))
        jobs.append(
            Job(
                title=_first(item, "name", "title", "jobName"),
                company=company_name,
                salary=salary or "面議",
                salary_min=_parse_salary(salary),
                location=str(_first(item, "city", "location", "area")),
                description=str(_first(item, "description", "snippet", "excerpt")).strip(),
                date=str(_first(item, "published_at", "updated_at", "date"))[:10],
                job_url=_norm_url(str(_first(item, "path", "url", "link"))),
                company_url=_norm_url(str(company_path)),
                source="Yourator",
            )
        )
    return jobs


def search_yourator(
    keyword: str,
    area: str = "全部",
    min_salary: int = 0,
    max_pages: int = 3,
    delay: float = 0.6,
    session: requests.Session | None = None,
    job_type: str = "不限",
) -> list[Job]:
    """搜尋 Yourator 職缺。介面與 search_104 一致。

    area      Yourator 沒有地區參數，改在結果端以地區名稱過濾（比對 location 字串）
    job_type  Yourator 以新創全職為主，此參數目前忽略
    """
    if not keyword.strip():
        raise ValueError("keyword 不可為空")

    sess = session or requests.Session()
    results: list[Job] = []

    for page in range(1, max_pages + 1):
        resp = sess.get(
            SEARCH_API,
            params={"term[]": keyword, "page": page},
            headers=DEFAULT_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()

        page_jobs = _extract_jobs(payload)
        if not page_jobs:
            break
        results.extend(page_jobs)

        inner = _unwrap(payload)
        if inner.get("has_more") is False or inner.get("hasMore") is False:
            break
        time.sleep(delay)

    if area and area != "全部":
        # "台北市" -> "台北"，用包含比對（Yourator 的 location 格式如「台北市大安區」或「台北」）
        needle = area.rstrip("市縣")
        results = [j for j in results if not j.location or needle in j.location]

    if min_salary > 0:
        results = [j for j in results if j.salary_min is None or j.salary_min >= min_salary]
    return results
