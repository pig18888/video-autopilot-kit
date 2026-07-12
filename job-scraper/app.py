"""Flask 網站：輸入關鍵字/地區/最低薪資，即時查詢 104 職缺。

啟動：
    pip install -r requirements.txt
    python app.py
    瀏覽器開 http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import io

from flask import Flask, render_template, request, Response

from scraper import AREA_CODES, search_104, to_csv_rows

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    keyword = (request.args.get("keyword") or "").strip()
    area = request.args.get("area") or "全部"
    min_salary = _to_int(request.args.get("min_salary"), 0)
    max_pages = min(_to_int(request.args.get("max_pages"), 3), 10)

    jobs = []
    error = None
    if keyword:
        try:
            jobs = search_104(keyword, area, min_salary, max_pages=max_pages)
        except Exception as exc:  # noqa: BLE001 - 顯示給使用者即可
            error = f"查詢失敗：{exc}"

    return render_template(
        "index.html",
        areas=list(AREA_CODES.keys()),
        keyword=keyword,
        area=area,
        min_salary=min_salary,
        max_pages=max_pages,
        jobs=jobs,
        error=error,
    )


@app.route("/export.csv")
def export_csv():
    keyword = (request.args.get("keyword") or "").strip()
    area = request.args.get("area") or "全部"
    min_salary = _to_int(request.args.get("min_salary"), 0)
    max_pages = min(_to_int(request.args.get("max_pages"), 3), 10)

    if not keyword:
        return Response("缺少 keyword", status=400)

    jobs = search_104(keyword, area, min_salary, max_pages=max_pages)

    buf = io.StringIO()
    buf.write("﻿")  # BOM，讓 Excel 正確辨識 UTF-8
    writer = csv.writer(buf)
    writer.writerows(to_csv_rows(jobs))

    filename = f"104_{keyword}.csv"
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    app.run(debug=True, port=5000)
