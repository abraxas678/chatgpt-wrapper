#!/usr/bin/env python3

import json
import math
import os
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
API_VERSION = "2026-03-10"

OUT_DIR = Path("site")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_star_dates():
    dates = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/repos/{REPO}/stargazers"
            f"?per_page=100&page={page}"
        )

        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/vnd.github.star+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "llm-workflow-engine-star-history",
            },
        )

        with urlopen(req, timeout=30) as response:
            batch = json.load(response)

        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected GitHub response: {batch!r}")

        for item in batch:
            timestamp = item.get("starred_at")
            if timestamp:
                d = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).date()
                dates.append(d)

        if len(batch) < 100:
            break

        page += 1

    return sorted(dates)


def build_points(star_dates):
    per_day = {}

    for d in star_dates:
        per_day[d] = per_day.get(d, 0) + 1

    running = 0
    points = []

    for d in sorted(per_day):
        running += per_day[d]
        points.append((d, running))

    today = datetime.now(timezone.utc).date()

    if not points:
        points = [(today, 0)]
    elif points[-1][0] < today:
        points.append((today, running))

    return points


def generate_svg(points):
    width = 1200
    height = 630

    left = 90
    right = 40
    top = 70
    bottom = 75

    plot_w = width - left - right
    plot_h = height - top - bottom

    start = points[0][0]
    end = points[-1][0]

    span_days = max(1, (end - start).days)
    stars = points[-1][1]

    y_step = max(1, math.ceil(max(stars, 1) / 5))
    y_max = y_step * 5

    def x(d):
        return left + ((d - start).days / span_days) * plot_w

    def y(value):
        return top + plot_h - (value / y_max) * plot_h

    polyline = " ".join(
        f"{x(d):.2f},{y(count):.2f}"
        for d, count in points
    )

    y_grid = []

    for i in range(6):
        value = y_step * i
        yy = y(value)

        y_grid.append(
            f"""
            <line class="grid" x1="{left}" y1="{yy:.2f}"
                  x2="{width-right}" y2="{yy:.2f}" />
            <text class="label" x="{left-14}" y="{yy+5:.2f}"
                  text-anchor="end">{value}</text>
            """
        )

    x_grid = []

    for i in range(6):
        offset = round(span_days * i / 5)
        d = start + timedelta(days=offset)
        xx = x(d)

        x_grid.append(
            f"""
            <line class="grid" x1="{xx:.2f}" y1="{top}"
                  x2="{xx:.2f}" y2="{top+plot_h}" />
            <text class="label" x="{xx:.2f}" y="{height-35}"
                  text-anchor="middle">{d.isoformat()}</text>
            """
        )

    title = escape(f"Star history · {REPO}")

    return f"""\
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}" height="{height}"
     viewBox="0 0 {width} {height}"
     role="img"
     aria-label="{title}">

<style>
  .bg {{ fill: #ffffff; }}
  .grid {{ stroke: #d0d7de; stroke-width: 1; }}
  .axis {{ stroke: #57606a; stroke-width: 1.5; }}
  .line {{ fill: none; stroke: #0969da; stroke-width: 4;
           stroke-linejoin: round; stroke-linecap: round; }}
  .title {{ fill: #24292f; font: 600 25px system-ui, sans-serif; }}
  .count {{ fill: #57606a; font: 16px system-ui, sans-serif; }}
  .label {{ fill: #57606a; font: 13px system-ui, sans-serif; }}

  @media (prefers-color-scheme: dark) {{
    .bg {{ fill: #0d1117; }}
    .grid {{ stroke: #30363d; }}
    .axis {{ stroke: #8b949e; }}
    .line {{ stroke: #58a6ff; }}
    .title {{ fill: #f0f6fc; }}
    .count, .label {{ fill: #8b949e; }}
  }}
</style>

<rect class="bg" width="100%" height="100%" />

<text class="title" x="{left}" y="35">{title}</text>
<text class="count" x="{width-right}" y="35" text-anchor="end">
  {stars:,} stars
</text>

{"".join(y_grid)}
{"".join(x_grid)}

<line class="axis"
      x1="{left}" y1="{top+plot_h}"
      x2="{width-right}" y2="{top+plot_h}" />

<line class="axis"
      x1="{left}" y1="{top}"
      x2="{left}" y2="{top+plot_h}" />

<polyline class="line" points="{polyline}" />

</svg>
"""


def main():
    dates = fetch_star_dates()
    points = build_points(dates)

    svg = generate_svg(points)

    (OUT_DIR / "star-history.svg").write_text(svg, encoding="utf-8")

    (OUT_DIR / "index.html").write_text(
        """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Star History</title>
<style>
body {
    margin: 0;
    padding: 2rem;
    background: #fff;
}
img {
    display: block;
    width: min(1200px, 100%);
    height: auto;
    margin: auto;
}
</style>
</head>
<body>
<img src="star-history.svg" alt="Star history">
</body>
</html>
""",
        encoding="utf-8",
    )

    print(f"Generated chart from {len(dates)} stars")


if __name__ == "__main__":
    main()
