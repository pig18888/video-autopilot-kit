"""整合多個人力銀行來源（104 + 1111）。"""

from __future__ import annotations

import re

from scraper import Job, search_104
from scraper_1111 import search_1111
from scraper_yourator import search_yourator

SOURCES = {
    "104": search_104,
    "Yourator": search_yourator,
    "1111": search_1111,
}

# 常見查詢快速預設：關鍵字比對是死板的字串比對，「AI」查不到「人工智慧」
# 「機器學習」這類同義詞，所以用多個關鍵字合併查詢來補齊涵蓋範圍。
PRESETS: dict[str, str] = {
    "AI 職缺": "AI、人工智慧、機器學習、Machine Learning、Deep Learning、資料科學、LLM",
}

_SPLIT_RE = re.compile(r"[,，、;；]+")


def split_keywords(raw: str) -> list[str]:
    """把「AI、人工智慧、機器學習」這類多關鍵字字串拆成不重複的關鍵字清單。"""
    seen: set[str] = set()
    result: list[str] = []
    for part in _SPLIT_RE.split(raw):
        term = part.strip()
        if term and term not in seen:
            seen.add(term)
            result.append(term)
    return result


def search_all(
    keyword: str,
    area: str = "全部",
    min_salary: int = 0,
    max_pages: int = 3,
    sources: list[str] | None = None,
    job_type: str = "不限",
) -> tuple[list[Job], dict[str, str]]:
    """同時查詢多個來源。

    回傳 (jobs, errors)：
      jobs   合併並依 job_url 去重後的職缺清單
      errors {來源: 錯誤訊息}，某來源失敗不影響其他來源
    """
    chosen = sources or list(SOURCES.keys())
    all_jobs: list[Job] = []
    errors: dict[str, str] = {}

    for name in chosen:
        fn = SOURCES.get(name)
        if fn is None:
            continue
        try:
            all_jobs.extend(fn(keyword, area, min_salary, max_pages=max_pages, job_type=job_type))
        except Exception as exc:  # noqa: BLE001 - 記錄後繼續
            errors[name] = str(exc)

    # 依 job_url 去重（保留先出現的）
    seen: set[str] = set()
    deduped: list[Job] = []
    for j in all_jobs:
        key = j.job_url or f"{j.source}:{j.title}:{j.company}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(j)

    return deduped, errors


def search_multi_keywords(
    raw_keyword: str,
    area: str = "全部",
    min_salary: int = 0,
    max_pages: int = 3,
    sources: list[str] | None = None,
    job_type: str = "不限",
) -> tuple[list[Job], dict[str, str]]:
    """支援「AI、人工智慧、機器學習」這種多關鍵字輸入：逐一查詢後合併去重。

    只有一個關鍵字時等同 search_all。errors 以來源分組，同一來源多次
    查詢若有失敗只記錄一次（同一原因通常重複，不需重複列出）。
    """
    keywords = split_keywords(raw_keyword)
    if len(keywords) <= 1:
        return search_all(raw_keyword, area, min_salary, max_pages,
                          sources=sources, job_type=job_type)

    all_jobs: list[Job] = []
    errors: dict[str, str] = {}
    for kw in keywords:
        jobs, errs = search_all(kw, area, min_salary, max_pages,
                                sources=sources, job_type=job_type)
        all_jobs.extend(jobs)
        errors.update(errs)

    seen: set[str] = set()
    deduped: list[Job] = []
    for j in all_jobs:
        key = j.job_url or f"{j.source}:{j.title}:{j.company}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(j)

    return deduped, errors
