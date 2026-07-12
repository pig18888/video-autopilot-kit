"""104 人力銀行職缺爬蟲（使用官方 JSON API，不需 Selenium）。

104 的搜尋頁其實是打一支 JSON API 拿資料，這裡直接呼叫該 API，
比用瀏覽器自動化穩定且快很多。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from typing import Iterable

import requests

SEARCH_API = "https://www.104.com.tw/jobs/search/api/jobs"

# 常用地區代碼（104 area code）。可自行擴充。
AREA_CODES = {
    "全部": "",
    "台北市": "6001001000",
    "新北市": "6001002000",
    "基隆市": "6001003000",
    "桃園市": "6001005000",
    "新竹市": "6001006000",
    "新竹縣": "6001007000",
    "台中市": "6001008000",
    "台南市": "6001014000",
    "高雄市": "6001016000",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    # 104 API 會檢查 Referer，沒帶會回空資料。
    "Referer": "https://www.104.com.tw/jobs/search/",
}


@dataclass
class Job:
    title: str
    company: str
    salary: str
    salary_min: int | None  # 解析出的月薪下限（無法解析為 None）
    location: str
    description: str
    date: str
    job_url: str
    company_url: str
    source: str = "104"  # 來源網站：104 / 1111

    def as_dict(self) -> dict:
        return asdict(self)


def _parse_min_salary(salary_desc: str) -> int | None:
    """從薪資字串抓出月薪下限（新台幣/月）。

    範例：
      "月薪 40,000~60,000元" -> 40000
      "年薪 600,000元以上"   -> 50000  (換算成月)
      "時薪 176元"           -> None   (時薪不換算)
      "待遇面議"             -> None
    """
    text = salary_desc.replace(",", "")
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if not nums:
        return None
    low = min(nums)
    if "年薪" in salary_desc:
        return low // 12
    if "月薪" in salary_desc:
        return low
    # 時薪 / 面議 / 論件計酬等一律視為無法比較
    return None


def _build_params(keyword: str, area_code: str, page: int) -> dict:
    return {
        "ro": 0,          # 0=不限, 1=全職
        "kwop": 7,        # 關鍵字比對模式
        "keyword": keyword,
        "order": 15,      # 15=依日期排序（最新）
        "asc": 0,
        "page": page,
        "mode": "s",
        "jobsource": "2018indexpoc",
        **({"area": area_code} if area_code else {}),
    }


def _job_list(payload: dict) -> list:
    """新版 API 的 data 直接是職缺陣列；相容舊版的 data.list。"""
    data = payload.get("data", [])
    if isinstance(data, dict):
        return data.get("list", [])
    return data if isinstance(data, list) else []


def _total_page(payload: dict) -> int | None:
    meta = payload.get("metadata") or {}
    pag = meta.get("pagination") or {}
    for key in ("lastPage", "totalPage", "total_page"):
        v = pag.get(key)
        if isinstance(v, int):
            return v
    return None


def _extract_jobs(payload: dict) -> list[Job]:
    jobs: list[Job] = []
    for item in _job_list(payload):
        salary_desc = item.get("salaryDesc", "") or ""
        link = item.get("link", {}) or {}
        job_url = link.get("job", "") or ""
        if job_url.startswith("//"):
            job_url = "https:" + job_url
        cust_url = link.get("cust", "") or ""
        if cust_url.startswith("//"):
            cust_url = "https:" + cust_url
        jobs.append(
            Job(
                title=item.get("jobName", ""),
                company=item.get("custName", ""),
                salary=salary_desc,
                salary_min=_parse_min_salary(salary_desc),
                location=item.get("jobAddrNoDesc", ""),
                description=(item.get("description", "") or "").strip(),
                date=item.get("appearDate", ""),
                job_url=job_url,
                company_url=cust_url,
                source="104",
            )
        )
    return jobs


def search_104(
    keyword: str,
    area: str = "全部",
    min_salary: int = 0,
    max_pages: int = 3,
    delay: float = 0.6,
    session: requests.Session | None = None,
) -> list[Job]:
    """搜尋 104 職缺。

    keyword    關鍵字（必填）
    area       地區名稱，需為 AREA_CODES 的 key
    min_salary 最低月薪過濾（0 表示不過濾；面議/時薪一律保留）
    max_pages  最多抓幾頁（每頁約 20 筆）
    """
    if not keyword.strip():
        raise ValueError("keyword 不可為空")

    area_code = AREA_CODES.get(area, "")
    sess = session or requests.Session()
    results: list[Job] = []

    for page in range(1, max_pages + 1):
        params = _build_params(keyword, area_code, page)
        resp = sess.get(SEARCH_API, params=params, headers=DEFAULT_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        page_jobs = _extract_jobs(payload)
        if not page_jobs:
            break  # 沒資料代表已到底
        results.extend(page_jobs)

        total_page = _total_page(payload)
        if total_page is not None and page >= total_page:
            break
        time.sleep(delay)  # 禮貌性延遲，避免打太快

    if min_salary > 0:
        results = [
            j for j in results
            if j.salary_min is None or j.salary_min >= min_salary
        ]
    return results


def to_csv_rows(jobs: Iterable[Job]) -> list[list[str]]:
    header = ["來源", "職缺", "公司", "薪資", "地區", "工作內容", "刊登日", "職缺連結"]
    rows = [header]
    for j in jobs:
        rows.append([
            j.source, j.title, j.company, j.salary, j.location,
            j.description, j.date, j.job_url,
        ])
    return rows


if __name__ == "__main__":
    # 簡易 CLI 測試：python scraper.py python 台北市 40000
    import sys

    kw = sys.argv[1] if len(sys.argv) > 1 else "python"
    ar = sys.argv[2] if len(sys.argv) > 2 else "全部"
    ms = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    for job in search_104(kw, ar, ms):
        print(f"{job.title} | {job.company} | {job.salary} | {job.location}")
