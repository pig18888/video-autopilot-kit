"""診斷 104 / 1111 API：找出正確端點與回應格式。

在有網路的機器上跑：  python3 diag.py
把完整輸出貼回給開發者即可據以修正。
"""

from __future__ import annotations

import json
import ssl
import urllib.request

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


def show(label: str, resp: requests.Response) -> None:
    body = resp.text
    print(f"  status      = {resp.status_code}")
    print(f"  content-type= {resp.headers.get('content-type')}")
    print(f"  length      = {len(body)}")
    is_json = False
    try:
        data = resp.json()
        is_json = True
        top = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        print(f"  JSON OK, top-level keys = {top}")
        # 嘗試印出第一筆職缺的 keys 幫助對應欄位
        node = data
        for k in ("data", "list"):
            if isinstance(node, dict) and k in node:
                node = node[k]
        if isinstance(node, list) and node:
            print(f"  first item keys = {list(node[0].keys())[:20]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  JSON parse FAILED: {exc}")
    if not is_json:
        print(f"  first 200 chars: {body[:200]!r}")
    print()


def try_104() -> None:
    print("=" * 60)
    print("104 端點測試")
    print("=" * 60)
    headers = {"User-Agent": UA, "Referer": "https://www.104.com.tw/jobs/search/"}
    params = {
        "ro": 0, "kwop": 7, "keyword": "python", "order": 15, "asc": 0,
        "page": 1, "mode": "s", "jobsource": "2018indexpoc",
    }
    for url in (
        "https://www.104.com.tw/jobs/search/api/jobs",
        "https://www.104.com.tw/jobs/search/list",
    ):
        print(f"[104] GET {url}")
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            show("104", r)
        except Exception as exc:  # noqa: BLE001
            print(f"  請求失敗: {exc}\n")


def try_1111() -> None:
    print("=" * 60)
    print("1111 端點測試")
    print("=" * 60)
    headers = {"User-Agent": UA, "Referer": "https://www.1111.com.tw/search/job",
               "Accept": "application/json"}

    # 1) 先看憑證問題：verify=True vs verify=False
    url = "https://www.1111.com.tw/api/v1/search/job/"
    print(f"[1111] GET {url}  (verify=True)")
    try:
        r = requests.get(url, params={"ks": "python", "page": 1}, headers=headers, timeout=15)
        show("1111", r)
    except Exception as exc:  # noqa: BLE001
        print(f"  verify=True 失敗: {exc}\n")

    print(f"[1111] GET {url}  (verify=False)")
    try:
        import urllib3
        urllib3.disable_warnings()
        r = requests.get(url, params={"ks": "python", "page": 1}, headers=headers,
                         timeout=15, verify=False)
        show("1111", r)
    except Exception as exc:  # noqa: BLE001
        print(f"  verify=False 也失敗: {exc}\n")

    # 2) 抓搜尋頁 HTML，找出頁面實際呼叫的 API 路徑
    print("[1111] 抓搜尋頁 HTML，尋找內含的 api 路徑線索")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://www.1111.com.tw/search/job?ks=python", headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=15, context=ctx).read().decode("utf-8", "ignore")
        print(f"  HTML 長度 = {len(html)}")
        import re
        hits = sorted(set(re.findall(r"[\"'](/api/[^\"']+)[\"']", html)))[:15]
        print(f"  頁面內出現的 /api/ 路徑: {hits}")
    except Exception as exc:  # noqa: BLE001
        print(f"  HTML 抓取失敗: {exc}")
    print()


def try_yourator() -> None:
    print("=" * 60)
    print("Yourator 端點測試")
    print("=" * 60)
    headers = {"User-Agent": UA, "Accept": "application/json",
               "Referer": "https://www.yourator.co/jobs"}
    url = "https://www.yourator.co/api/v4/jobs"
    print(f"[Yourator] GET {url}?term[]=python&page=1")
    try:
        r = requests.get(url, params={"term[]": "python", "page": 1},
                         headers=headers, timeout=15)
        print(f"  status = {r.status_code}, content-type = {r.headers.get('content-type')}")
        data = r.json()
        print(f"  top-level keys = {list(data.keys()) if isinstance(data, dict) else type(data)}")
        inner = data.get("payload") if isinstance(data.get("payload"), dict) else data
        print(f"  payload keys = {list(inner.keys()) if isinstance(inner, dict) else type(inner)}")
        items = inner.get("jobs") or inner.get("data") or []
        print(f"  職缺數 = {len(items)}")
        if items:
            import json as _json
            print("  第一筆職缺內容：")
            print(_json.dumps(items[0], ensure_ascii=False, indent=2)[:2000])
    except Exception as exc:  # noqa: BLE001
        print(f"  失敗: {exc}")
    print()


if __name__ == "__main__":
    print("requests version:", requests.__version__)
    try_104()
    try_yourator()
    try_1111()
    print("診斷完成，請把以上完整輸出貼回。")
