"""Flask 網站：查詢 104 + 1111 職缺、歷史追蹤、薪資趨勢圖。

啟動：
    pip install -r requirements.txt
    python app.py
    瀏覽器開 http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import io

from flask import Flask, render_template, request, Response

from db import get_history, list_keywords, salary_trend, save_jobs
from scraper import AREA_CODES, to_csv_rows
from sources import SOURCES, search_all

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    keyword = (request.args.get("keyword") or "").strip()
    area = request.args.get("area") or "全部"
    min_salary = _to_int(request.args.get("min_salary"), 0)
    max_pages = min(_to_int(request.args.get("max_pages"), 3), 10)
    chosen = request.args.getlist("source") or ["104"]

    jobs = []
    error = None
    if keyword:
        try:
            jobs, errors = search_all(keyword, area, min_salary, max_pages, sources=chosen)
            save_jobs(jobs, keyword)  # 存進 DB 做歷史追蹤
            if errors:
                error = "部分來源查詢失敗：" + "；".join(f"{k}({v})" for k, v in errors.items())
        except Exception as exc:  # noqa: BLE001
            error = f"查詢失敗：{exc}"

    return render_template(
        "index.html",
        areas=list(AREA_CODES.keys()),
        all_sources=list(SOURCES.keys()),
        chosen_sources=chosen,
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
    chosen = request.args.getlist("source") or ["104"]

    if not keyword:
        return Response("缺少 keyword", status=400)

    jobs, _ = search_all(keyword, area, min_salary, max_pages, sources=chosen)

    buf = io.StringIO()
    buf.write("﻿")  # BOM，讓 Excel 正確辨識 UTF-8
    writer = csv.writer(buf)
    writer.writerows(to_csv_rows(jobs))

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="jobs_{keyword}.csv"'},
    )


@app.route("/history")
def history():
    keyword = (request.args.get("keyword") or "").strip() or None
    rows = get_history(keyword)
    return render_template(
        "history.html",
        rows=rows,
        keyword=keyword or "",
        keywords=list_keywords(),
    )


@app.route("/trends")
def trends():
    keyword = (request.args.get("keyword") or "").strip() or None
    points = salary_trend(keyword)
    return render_template(
        "trends.html",
        points=points,
        svg=_render_trend_svg(points),
        keyword=keyword or "",
        keywords=list_keywords(),
    )


def _render_trend_svg(points: list[dict], width: int = 760, height: int = 280) -> str:
    """把每日平均月薪畫成內建 SVG 折線圖（不需前端套件）。"""
    if not points:
        return "<p style='color:#889'>尚無資料，先到查詢頁跑幾次查詢累積歷史。</p>"

    pad = 48
    vals = [p["avg_min"] for p in points]
    vmax, vmin = max(vals), min(vals)
    span = (vmax - vmin) or 1
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad
    n = len(points)

    def x(i: int) -> float:
        return pad + (plot_w * (i / (n - 1)) if n > 1 else plot_w / 2)

    def y(v: float) -> float:
        return pad + plot_h * (1 - (v - vmin) / span)

    line = " ".join(f"{x(i):.1f},{y(p['avg_min']):.1f}" for i, p in enumerate(points))
    dots = "".join(
        f"<circle cx='{x(i):.1f}' cy='{y(p['avg_min']):.1f}' r='3.5' fill='#0066cc'>"
        f"<title>{p['date']}：平均 {int(p['avg_min']):,} 元 ({p['count']} 筆)</title></circle>"
        for i, p in enumerate(points)
    )
    y_labels = "".join(
        f"<text x='{pad - 8}' y='{pad + plot_h * t + 4:.0f}' text-anchor='end' "
        f"font-size='11' fill='#889'>{int(vmax - span * t):,}</text>"
        f"<line x1='{pad}' y1='{pad + plot_h * t:.0f}' x2='{width - pad}' "
        f"y2='{pad + plot_h * t:.0f}' stroke='#eef' />"
        for t in (0, 0.25, 0.5, 0.75, 1)
    )
    x_labels = "".join(
        f"<text x='{x(i):.0f}' y='{height - pad + 18}' text-anchor='middle' "
        f"font-size='10' fill='#889'>{points[i]['date'][5:]}</text>"
        for i in range(0, n, max(1, n // 6))
    )
    return (
        f"<svg viewBox='0 0 {width} {height}' width='100%' style='max-width:{width}px'>"
        f"{y_labels}"
        f"<polyline points='{line}' fill='none' stroke='#0066cc' stroke-width='2' />"
        f"{dots}{x_labels}</svg>"
    )


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    app.run(debug=True, port=5000)
