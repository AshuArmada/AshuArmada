#!/usr/bin/env python3
"""
Builds stats.svg from the GitHub API — a self-hosted replacement for the
third-party stats cards, which go dark whenever their free deployment is paused.

    python assets/stats.py [username]

Runs unauthenticated (60 req/hr) or with GITHUB_TOKEN set for a higher limit.
Refreshed daily by .github/workflows/stats.yml.
"""

import collections
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate import CYAN, DIM, INK, MONO, PINK, REDUCED, SANS, VIOLET, card, esc, fmt, frame, svg

OUT = Path(__file__).parent
USER = sys.argv[1] if len(sys.argv) > 1 else "AshuArmada"
TOP_N = 6

# Loosely GitHub's language colours, but pulled apart so neighbouring segments in
# the stacked bar stay distinguishable (GitHub's TypeScript and Python are both blue).
COLORS = {
    "TypeScript": "#4f9df7", "Python": "#56d364", "JavaScript": "#f1e05a",
    "CSS": "#a970ff", "C#": "#ff7b72", "HTML": "#ffa657", "C++": "#f778ba",
    "C": "#8f9bab", "Java": "#d0a441", "Shell": "#7ee787", "Dockerfile": "#5f7f8c",
    "Jinja": "#d1553f", "Mako": "#9aa1ab", "Jupyter Notebook": "#ff9f45",
    "SCSS": "#e07aa5", "Go": "#39c5cf", "Rust": "#e08a5a", "Ruby": "#e0575b",
    "PHP": "#8f92d0", "Vue": "#41b883", "Svelte": "#ff5c2b", "Makefile": "#a6b0bf",
}
FALLBACK = ["#22d3ee", "#a78bfa", "#f472b6", "#7dd3fc", "#facc15", "#4ade80"]


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats", "Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def collect():
    user = api(f"https://api.github.com/users/{USER}")
    repos = api(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    langs = collections.Counter()
    for r in repos:
        if r.get("fork"):
            continue
        try:
            langs.update(api(r["languages_url"]))
        except urllib.error.HTTPError as e:
            print(f"  ! skipped {r['name']}: {e}", file=sys.stderr)
    return user, [r for r in repos if not r.get("fork")], langs


def human_bytes(n):
    for unit, div in (("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def tile(x, value, label, accent, delay):
    return (
        f'<g class="tile" style="animation-delay:{fmt(delay)}s">'
        f'<g transform="translate({fmt(x)},64)">'
        f'<rect width="196" height="64" rx="12" fill="#ffffff" fill-opacity=".035" '
        f'stroke="{accent}" stroke-opacity=".28"/>'
        f'<rect x="1" y="14" width="3" height="36" rx="2" fill="{accent}"/>'
        f'<text x="20" y="34" font-family="{SANS}" font-size="23" font-weight="700" fill="{INK}">{esc(value)}</text>'
        f'<text x="20" y="52" font-family="{MONO}" font-size="10.5" letter-spacing="1.1" '
        f'fill="{DIM}">{esc(label.upper())}</text>'
        "</g></g>"
    )


def build():
    user, repos, langs = collect()
    total = sum(langs.values()) or 1
    ranked = langs.most_common()
    top = ranked[:TOP_N]
    rest = sum(v for _, v in ranked[TOP_N:])
    if rest:
        top.append(("Other", rest))

    def color(i, name):
        return COLORS.get(name, FALLBACK[i % len(FALLBACK)]) if name != "Other" else "#6b7688"

    W, H = 900, 262
    BAR_X, BAR_Y, BAR_W, BAR_H = 40, 168, 820, 24

    # stacked bar: each segment scales out from its own left edge
    segs, x = [], 0.0
    for i, (name, val) in enumerate(top):
        w = BAR_W * val / total
        segs.append(
            f'<g transform="translate({fmt(BAR_X + x)},{BAR_Y})">'
            f'<g class="grow" style="animation-delay:{fmt(0.25 + i * 0.13)}s">'
            f'<rect width="{fmt(max(w, 1.5))}" height="{BAR_H}" fill="{color(i, name)}"/>'
            "</g></g>"
        )
        x += w

    # legend
    legend, lx = [], 0.0
    for i, (name, val) in enumerate(top):
        pct = 100 * val / total
        label = f"{name} {pct:.1f}%"
        legend.append(
            f'<g class="rise" style="animation-delay:{fmt(0.55 + i * 0.09)}s">'
            f'<g transform="translate({fmt(BAR_X + lx)},220)">'
            f'<circle cx="5" cy="14" r="5" fill="{color(i, name)}"/>'
            f'<text x="17" y="18" font-family="{SANS}" font-size="13" fill="{INK}" fill-opacity=".85">'
            f'{esc(name)} <tspan fill="{DIM}">{pct:.1f}%</tspan></text>'
            "</g></g>"
        )
        lx += 34 + len(label) * 7.1

    created = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    tiles = (
        tile(40, str(len(repos)), "public repos", CYAN, 0.05)
        + tile(248, str(len(langs)), "languages", VIOLET, 0.15)
        + tile(456, human_bytes(total), "of source", PINK, 0.25)
        + tile(664, created.strftime("%b %Y"), "first push", "#7dd3fc", 0.35)
    )

    style = (
        "@keyframes tile{0%{opacity:0;transform:translateY(10px)}9%,100%{opacity:1;transform:translateY(0)}}"
        "@keyframes grow{0%{transform:scaleX(0)}14%,100%{transform:scaleX(1)}}"
        "@keyframes rise{0%{opacity:0;transform:translateY(6px)}11%,100%{opacity:1;transform:translateY(0)}}"
        "@keyframes sheen{0%,42%{transform:translateX(-220px)}70%,100%{transform:translateX(900px)}}"
        ".tile{opacity:0;animation:tile 11s cubic-bezier(.2,.9,.3,1) infinite}"
        ".grow{transform-origin:0 0;animation:grow 11s cubic-bezier(.2,.9,.3,1) infinite}"
        ".rise{opacity:0;animation:rise 11s ease-out infinite}"
        ".sheen{animation:sheen 11s ease-in-out infinite}" + REDUCED
    )

    body = (
        "<defs>"
        + card(W, H)
        + f'<clipPath id="bar"><rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" rx="{BAR_H // 2}"/></clipPath>'
        + '<linearGradient id="sheen" x1="0" x2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity=".45"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        "</defs>"
        + '<g clip-path="url(#card)">'
        + f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        + f'<rect width="{W}" height="{H}" fill="url(#grid)"/>'
        + f'<text x="40" y="40" font-family="{MONO}" font-size="14" fill="{DIM}">'
        f"language breakdown &#183; {len(repos)} public repositories</text>"
        + tiles
        + f'<rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" rx="{BAR_H // 2}" '
        'fill="#ffffff" fill-opacity=".05"/>'
        + f'<g clip-path="url(#bar)">{"".join(segs)}'
        f'<rect class="sheen" x="0" y="{BAR_Y}" width="220" height="{BAR_H}" fill="url(#sheen)"/></g>'
        + "".join(legend)
        + "</g>"
        + frame(W, H)
    )
    (OUT / "stats.svg").write_text(svg(W, H, f"{USER} language breakdown", body, style), encoding="utf-8")
    print(f"wrote stats.svg — {len(repos)} repos, {len(langs)} languages, {human_bytes(total)}")


if __name__ == "__main__":
    build()
