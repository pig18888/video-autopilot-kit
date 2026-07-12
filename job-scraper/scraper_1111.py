"""1111 人力銀行職缺爬蟲。

1111 的搜尋頁同樣是打一支 JSON API。此模組以防禦性方式解析（欄位名稱以多種
可能性嘗試），因為 1111 的 API 欄位偶爾會調整；解析不到的欄位會留空而非崩潰。

注意：本檔在受限網路的沙箱中無法對 1111 實際連線驗證，若欄位對不上，
請依實際回應調整 `_extract_jobs` 內的欄位對應。
"""

from __future__ import annotations

import time
from typing import Any

import requests

from scraper import Job, _parse_min_salary

# 1111 搜尋 API（回傳 JSON）
SEARCH_API = "https://www.1111.com.tw/api/v1/search/job/"

# 常用地區代碼（1111 city code）。可自行擴充。
AREA_CODES = {
    "全部": "",
    "台北市": "100",
    "新北市": "220",
    "基隆市": "200",
    "桃園市": "330",
    "新竹市": "300",
    "新竹縣": "302",
    "台中市": "400",
    "台南市": "700",
    "高雄市": "800",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Referer": "https://www.1111.com.tw/search/job",
    "Accept": "application/json",
}


def _first(item: dict, *keys: str, default: str = "") -> Any:
    """回傳 item 中第一個存在且非空的 key 值（容忍欄位改名）。"""
    for k in keys:
        v = item.get(k)
        if v:
            return v
    return default


def _norm_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.1111.com.tw" + url
    return url


def _iter_raw_jobs(payload: dict) -> list[dict]:
    """從各種可能的回應結構撈出職缺清單。"""
    for path in (("result", "job", "list"), ("data", "list"), ("jobs",), ("result", "list")):
        node: Any = payload
        ok = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                ok = False
                break
        if ok and isinstance(node, list):
            return node
    return []


def _extract_jobs(payload: dict) -> list[Job]:
    jobs: list[Job] = []
    for item in _iter_raw_jobs(payload):
        if not isinstance(item, dict):
            continue
        salary = _first(item, "salary", "salaryDesc", "wage")
        job_url = _norm_url(_first(item, "jobUrl", "url", "link"))
        jobs.append(
            Job(
                title=_first(item, "jobName", "title", "name"),
                company=_first(item, "companyName", "custName", "corpName", "company"),
                salary=salary,
                salary_min=_parse_min_salary(salary),
                location=_first(item, "cityName", "addressNo", "area", "location"),
                description=str(_first(item, "description", "jobDescription", "content")).strip(),
                date=_first(item, "appearDate", "updateDate", "date"),
                job_url=job_url,
                company_url=_norm_url(_first(item, "companyUrl", "custUrl", "corpUrl")),
                source="1111",
            )
        )
    return jobs


def _total_pages(payload: dict) -> int:
    for path in (("result", "job", "totalPage"), ("data", "totalPage"), ("totalPage",)):
        node: Any = payload
        ok = True
        for key in path:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                ok = False
                break
        if ok and isinstance(node, int):
            return node
    return 1


def search_1111(
    keyword: str,
    area: str = "全部",
    min_salary: int = 0,
    max_pages: int = 3,
    delay: float = 0.6,
    session: requests.Session | None = None,
) -> list[Job]:
    """搜尋 1111 職缺。介面與 scraper.search_104 一致。"""
    if not keyword.strip():
        raise ValueError("keyword 不可為空")

    area_code = AREA_CODES.get(area, "")
    sess = session or requests.Session()
    results: list[Job] = []

    for page in range(1, max_pages + 1):
        params = {"ks": keyword, "page": page, "sort": "desc"}
        if area_code:
            params["city"] = area_code
        resp = sess.get(SEARCH_API, params=params, headers=DEFAULT_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        page_jobs = _extract_jobs(payload)
        if not page_jobs:
            break
        results.extend(page_jobs)

        if page >= _total_pages(payload):
            break
        time.sleep(delay)

    if min_salary > 0:
        results = [j for j in results if j.salary_min is None or j.salary_min >= min_salary]
    return results
