"""整合多個人力銀行來源（104 + 1111）。"""

from __future__ import annotations

from scraper import Job, search_104
from scraper_1111 import search_1111
from scraper_yourator import search_yourator

SOURCES = {
    "104": search_104,
    "Yourator": search_yourator,
    "1111": search_1111,
}


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
