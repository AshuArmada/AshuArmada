#!/usr/bin/env python3
"""
Generates every animated SVG in the README, in a light and a dark colourway.

    python assets/fetch.py      # refresh assets/data.json from the GitHub API
    python assets/generate.py   # redraw the SVGs from it

Two constraints shape everything here.

GitHub renders a README on the *reader's* page background, and strips CSS from
markdown, so there is no way to set that background. A dark panel therefore sits
on a white page as a pasted-on rectangle. So nothing here draws a panel: the
artwork is transparent and the ink colour swaps per theme, and the README picks
a colourway with <picture media="(prefers-color-scheme: dark)">.

And GitHub serves these through an image proxy where <script> never runs, so all
motion is declarative SMIL + CSS.
"""

import json
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).parent
DATA = json.loads((OUT / "data.json").read_text(encoding="utf-8"))

MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# One accent ramp, two colourways. The light values are darkened until they hold
# 4.5:1 on white; build() prints the measured ratios so this stays honest.
THEMES = {
    "dark": {
        "PAGE": "#0d1117", "INK": "#e6edf3", "DIM": "#8b949e", "FAINT": "#30363d",
        "A1": "#22d3ee", "A2": "#a78bfa", "A3": "#f472b6", "A4": "#7dd3fc",
    },
    "light": {
        "PAGE": "#ffffff", "INK": "#1f2328", "DIM": "#57606a", "FAINT": "#d0d7de",
        "A1": "#0e7490", "A2": "#6d28d9", "A3": "#be185d", "A4": "#0369a1",
    },
}

EASE = "cubic-bezier(.16,1,.3,1)"     # expo-out — entrances
SPRING = "cubic-bezier(.2,1.5,.4,1)"  # overshoot — things that pop in

BASE_CSS = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def contrast(fg, bg):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + .05) / (b + .05)


def dedupe(frames):
    out = []
    for f in sorted(frames, key=lambda f: f[0]):
        if out and abs(out[-1][0] - f[0]) < 1e-9:
            out[-1] = f
        else:
            out.append(list(f))
    return out


def animate(attr, dur, frames, index):
    times = ";".join(fmt(f[0] / dur) for f in frames)
    values = ";".join(fmt(f[index]) for f in frames)
    return (f'<animate attributeName="{attr}" dur="{fmt(dur)}s" repeatCount="indefinite"'
            f' calcMode="discrete" keyTimes="{times}" values="{values}"/>')


def svg(w, h, title, body, style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{fmt(h)}" '
            f'viewBox="0 0 {w} {fmt(h)}" role="img" aria-label="{esc(title)}">'
            f"<title>{esc(title)}</title><style>{style}{BASE_CSS}</style>{body}</svg>\n")


# --------------------------------------------------------------------------
# typewriter timelines
# --------------------------------------------------------------------------

def _type_track(t0, text, adv, type_dur, hold, del_dur, total):
    """Char-by-char reveal width for one phrase inside a longer loop."""
    n = max(len(text), 1)
    frames = [(0.0, 0.0), (t0, 0.0)]
    for k in range(1, n + 1):
        frames.append((t0 + k * type_dur / n, k * adv))
    frames.append((t0 + type_dur + hold, n * adv))
    for k in range(n - 1, -1, -1):
        frames.append((t0 + type_dur + hold + (n - k) * del_dur / n, k * adv))
    frames.append((total, 0.0))
    return dedupe(frames)


def caret(x_frames, total, y, size, colour, adv):
    return (f'<rect y="{fmt(y - size * 0.78)}" width="{fmt(adv * 0.9)}" height="{fmt(size)}" '
            f'rx="1" fill="{colour}">{animate("x", total, dedupe(x_frames), 1)}'
            '<animate attributeName="opacity" values=".9;.9;0;0;.9" dur="1.06s" '
            'repeatCount="indefinite"/></rect>')


def rotator(t, phrases, size, x, y, uid="rot", cps=0.075, hold=1.9, del_cps=0.032, gap=0.45):
    """Type a phrase, hold, delete, move on. A phrase is hidden simply by being
    clipped to zero width, so no separate visibility track is needed."""
    adv = size * 0.6
    slots, clock = [], 0.0
    for p in phrases:
        t_in, t_del = len(p) * cps, len(p) * del_cps
        slots.append((clock, t_in, t_del, p))
        clock += t_in + hold + t_del + gap
    total = clock

    parts, carets = [], []
    for i, (t0, t_in, t_del, phrase) in enumerate(slots):
        fr = _type_track(t0, phrase, adv, t_in, hold, t_del, total)
        carets += [(f[0], x + f[1]) for f in fr]
        parts.append(
            f'<clipPath id="{uid}{i}"><rect x="{fmt(x)}" y="{fmt(y - size)}" '
            f'height="{fmt(size * 1.45)}" width="0">{animate("width", total, fr, 1)}'
            f'</rect></clipPath>'
            f'<text x="{fmt(x)}" y="{fmt(y)}" clip-path="url(#{uid}{i})" font-family="{MONO}" '
            f'font-size="{fmt(size)}" fill="{t["INK"]}">{esc(phrase)}</text>')
    return "".join(parts) + caret(carets, total, y, size, t["A1"], adv)


def commit_line(t, entries, slots, total, size, x, y, uid="cl"):
    """One monospace line that retypes itself for whichever commit is landing."""
    adv = size * 0.6
    parts, carets = [], []
    for i, ((sha, msg, colour), t0) in enumerate(zip(entries, slots)):
        end = slots[i + 1] if i + 1 < len(slots) else total
        text = f"{sha}  {msg}"
        t_in = min(len(text) * 0.028, (end - t0) * 0.5)
        t_del = 0.18
        hold = max(end - t0 - t_in - t_del - 0.12, 0.1)
        fr = _type_track(t0, text, adv, t_in, hold, t_del, total)
        carets += [(f[0], x + f[1]) for f in fr]
        parts.append(
            f'<clipPath id="{uid}{i}"><rect x="{fmt(x)}" y="{fmt(y - size)}" '
            f'height="{fmt(size * 1.5)}" width="0">{animate("width", total, fr, 1)}'
            f'</rect></clipPath>'
            f'<text x="{fmt(x)}" y="{fmt(y)}" clip-path="url(#{uid}{i})" font-family="{MONO}" '
            f'font-size="{fmt(size)}" xml:space="preserve" fill="{t["INK"]}">'
            f'<tspan fill="{colour}">{esc(sha)}</tspan>  {esc(msg)}</text>')
    return "".join(parts) + caret(carets, total, y, size, t["A1"], adv)


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------

def build_header(t):
    W, H = 900, 190
    ramp = (f'<linearGradient id="rule" x1="0" x2="1">'
            f'<stop offset="0" stop-color="{t["A1"]}"/><stop offset=".5" stop-color="{t["A2"]}"/>'
            f'<stop offset="1" stop-color="{t["A3"]}" stop-opacity="0"/></linearGradient>')
    shine = (f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="-320" x2="-60">'
             f'<stop offset="0" stop-color="{t["INK"]}"/><stop offset=".42" stop-color="{t["INK"]}"/>'
             f'<stop offset=".5" stop-color="{t["A2"]}"/><stop offset=".58" stop-color="{t["A1"]}"/>'
             f'<stop offset="1" stop-color="{t["INK"]}"/>'
             '<animate attributeName="x1" values="-320;900" dur="4.6s" repeatCount="indefinite"/>'
             '<animate attributeName="x2" values="-60;1160" dur="4.6s" repeatCount="indefinite"/>'
             "</linearGradient>")

    motes = "".join(
        f'<circle class="mote" cx="{cx}" cy="{cy}" r="{r}" fill="{c}" '
        f'style="animation-duration:{d}s;animation-delay:-{dl}s"/>'
        for cx, cy, r, c, d, dl in (
            (742, 44, 2.2, t["A1"], 11, 0), (795, 96, 1.6, t["A2"], 9, 3),
            (846, 58, 1.9, t["A3"], 13, 6), (700, 116, 1.4, t["A4"], 10, 1.5),
            (868, 122, 2.0, t["A2"], 12, 8), (770, 150, 1.5, t["A1"], 14, 4)))

    style = ("@keyframes mote{0%,100%{transform:translateY(0);opacity:.3}"
             "50%{transform:translateY(-16px);opacity:.95}}"
             "@keyframes rule{0%{stroke-dashoffset:300}40%,100%{stroke-dashoffset:0}}"
             "@keyframes ping{0%{transform:scale(1);opacity:.85}75%,100%{transform:scale(3);opacity:0}}"
             ".mote{animation:mote ease-in-out infinite}"
             f".rule{{stroke-dasharray:300;animation:rule 5s {EASE} infinite}}"
             ".ping{transform-origin:862px 34px;animation:ping 2.4s ease-out infinite}")

    body = (
        f"<defs>{ramp}{shine}</defs>{motes}"
        f'<text x="4" y="76" font-family="{SANS}" font-size="52" font-weight="700" '
        f'letter-spacing="-1.2" fill="url(#shine)">Ashutosh Thakur</text>'
        f'<path class="rule" d="M6 98h300" stroke="url(#rule)" stroke-width="2.5" '
        'stroke-linecap="round" fill="none"/>'
        f'<text x="4" y="140" font-family="{MONO}" font-size="21" fill="{t["A1"]}">&#10095;</text>'
        + rotator(t, ["full-stack developer", "AI / ML engineer",
                      "LLM-backed developer tools", "workflow automation"], 21, 30, 140)
        + f'<circle class="ping" cx="862" cy="34" r="4" fill="none" stroke="{t["A1"]}" stroke-width="1.5"/>'
        f'<circle cx="862" cy="34" r="4" fill="{t["A1"]}"/>'
        f'<text x="848" y="38" text-anchor="end" font-family="{MONO}" font-size="12" '
        f'fill="{t["DIM"]}">open to collab</text>'
        f'<text x="4" y="174" font-family="{MONO}" font-size="13" fill="{t["DIM"]}">'
        "building tools that make hard things visible</text>")
    return svg(W, H, "Ashutosh Thakur — full-stack developer, AI/ML", body, style)


# --------------------------------------------------------------------------
# activity — drawn from the real commit history in data.json
# --------------------------------------------------------------------------

def build_activity(t):
    commits = DATA["commits"]
    accents = [t["A1"], t["A2"], t["A3"], t["A4"]]

    lanes = []
    for c in commits:
        if c["repo"] not in lanes:
            lanes.append(c["repo"])
    lane_y = {r: 84 + i * 52 for i, r in enumerate(lanes)}
    lane_col = {r: accents[i % len(accents)] for i, r in enumerate(lanes)}

    label_w = max(len(r) for r in lanes) * 7.3 + 26
    x0, x1 = label_w + 16, 872
    step = (x1 - x0) / max(len(commits) - 1, 1)
    pos = [(x0 + i * step, lane_y[c["repo"]]) for i, c in enumerate(commits)]

    slots = [0.7 + i * 1.55 for i in range(len(commits))]
    total = slots[-1] + 2.4
    bottom = 84 + (len(lanes) - 1) * 52
    line_y = bottom + 78
    H = line_y + 34

    # a hairline per lane, then the real connections drawn over it
    rails = "".join(
        f'<path d="M{fmt(x0 - 10)} {lane_y[r]}H{x1 + 10}" stroke="{t["FAINT"]}" '
        'stroke-width="1.5" fill="none"/>' for r in lanes)

    links, last = [], {}
    for i, c in enumerate(commits):
        if c["repo"] in last:
            j = last[c["repo"]]
            links.append(
                f'<path class="seg" d="M{fmt(pos[j][0])} {pos[j][1]}H{fmt(pos[i][0])}" '
                f'pathLength="100" stroke="{lane_col[c["repo"]]}" fill="none" '
                f'style="animation-delay:{fmt(slots[i] - 0.3)}s"/>')
        last[c["repo"]] = i

    labels = "".join(
        f'<text x="4" y="{lane_y[r] + 4}" font-family="{MONO}" font-size="12.5" '
        f'fill="{lane_col[r]}">{esc(r)}</text>' for r in lanes)

    nodes = "".join(
        f'<g transform="translate({fmt(x)},{y})">'
        f'<g class="ping" style="animation-delay:{fmt(slots[i])}s">'
        f'<circle r="8" fill="none" stroke="{lane_col[commits[i]["repo"]]}" stroke-width="2"/></g>'
        f'<g class="n" style="animation-delay:{fmt(slots[i])}s">'
        f'<circle r="8" fill="{t["PAGE"]}" stroke="{lane_col[commits[i]["repo"]]}" stroke-width="2.5"/>'
        "</g></g>"
        for i, (x, y) in enumerate(pos))

    # marker that steps from commit to commit as each one lands
    keytimes, values = ["0"], [f"{fmt(pos[0][0])} {pos[0][1]}"]
    for i, (x, y) in enumerate(pos):
        keytimes.append(fmt(slots[i] / total))
        values.append(f"{fmt(x)} {y}")
    keytimes.append("1")
    values.append(values[-1])
    marker = (f'<g opacity="0"><animateTransform attributeName="transform" type="translate" '
              f'dur="{fmt(total)}s" repeatCount="indefinite" calcMode="discrete" '
              f'keyTimes="{";".join(keytimes)}" values="{";".join(values)}"/>'
              f'<animate attributeName="opacity" dur="{fmt(total)}s" repeatCount="indefinite" '
              f'keyTimes="0;{fmt(slots[0] / total)};{fmt((slots[0] + 0.2) / total)};0.97;1" '
              f'values="0;0;1;1;0"/>'
              f'<circle r="14" fill="none" stroke="{t["INK"]}" stroke-opacity=".45" '
              'stroke-width="1.5" stroke-dasharray="3 4"/></g>')

    entries = [(c["sha"], c["message"], lane_col[c["repo"]]) for c in commits]
    dates = f'{commits[0]["date"][:10]} → {commits[-1]["date"][:10]}'

    style = ("@keyframes draw{0%{stroke-dashoffset:100}7%,100%{stroke-dashoffset:0}}"
             "@keyframes pop{0%{transform:scale(0);opacity:0}3%{transform:scale(1.4);opacity:1}"
             "6%,100%{transform:scale(1);opacity:1}}"
             "@keyframes ping{0%{transform:scale(.5);opacity:.8}8%{transform:scale(3);opacity:0}"
             "8.01%,100%{opacity:0}}"
             f".seg{{stroke-dasharray:100;stroke-dashoffset:100;stroke-width:2.5;stroke-linecap:round;"
             f"animation:draw {fmt(total)}s {EASE} infinite}}"
             f".n{{opacity:0;transform-origin:0 0;animation:pop {fmt(total)}s {SPRING} infinite}}"
             f".ping{{opacity:0;transform-origin:0 0;animation:ping {fmt(total)}s ease-out infinite}}")

    body = (
        f'<text x="4" y="30" font-family="{MONO}" font-size="13" fill="{t["DIM"]}">'
        f'git log --oneline --all  <tspan fill="{t["FAINT"]}">·</tspan>  '
        f'{esc(str(len(commits)))} most recent commits  '
        f'<tspan fill="{t["FAINT"]}">·</tspan>  {esc(dates)}</text>'
        + rails + "".join(links) + labels + nodes + marker
        + f'<path d="M4 {bottom + 46}H872" stroke="{t["FAINT"]}" stroke-width="1"/>'
        + commit_line(t, entries, slots, total, 14.5, 4, line_y))
    return svg(900, H, f"Recent commit activity across {len(lanes)} repositories", body, style)


# --------------------------------------------------------------------------
# languages
# --------------------------------------------------------------------------

def build_langs(t):
    langs = DATA["languages"]
    accents = [t["A1"], t["A2"], t["A4"], t["A3"]]
    total_bytes = sum(langs.values()) or 1

    ranked = list(langs.items())
    top = ranked[:5]
    rest = sum(v for _, v in ranked[5:])
    if rest:
        top.append(("Other", rest))

    def colour(i, name):
        return t["FAINT"] if name == "Other" else accents[i % len(accents)]

    W, BAR_Y, BAR_H = 900, 60, 22
    BAR_X, BAR_W = 4, 868

    segs, x = [], 0.0
    for i, (name, val) in enumerate(top):
        w = BAR_W * val / total_bytes
        segs.append(
            f'<g transform="translate({fmt(BAR_X + x)},{BAR_Y})">'
            f'<g class="grow" style="animation-delay:{fmt(0.2 + i * 0.11)}s">'
            f'<rect width="{fmt(max(w, 2))}" height="{BAR_H}" fill="{colour(i, name)}"/>'
            "</g></g>")
        x += w

    legend, lx = [], 0.0
    for i, (name, val) in enumerate(top):
        pct = 100 * val / total_bytes
        legend.append(
            f'<g class="rise" style="animation-delay:{fmt(0.5 + i * 0.08)}s">'
            f'<g transform="translate({fmt(BAR_X + lx)},{BAR_Y + 34})">'
            f'<circle cx="5" cy="13" r="5" fill="{colour(i, name)}"/>'
            f'<text x="17" y="17" font-family="{SANS}" font-size="13" fill="{t["INK"]}">'
            f'{esc(name)} <tspan fill="{t["DIM"]}">{pct:.1f}%</tspan></text></g></g>')
        lx += 34 + len(f"{name} {pct:.1f}%") * 7.1

    def human(n):
        return f"{n / (1 << 20):.1f} MB" if n >= 1 << 20 else f"{n / 1024:.0f} KB"

    since = datetime.strptime(DATA["user"]["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %Y")
    summary = (f'{DATA["user"]["repos"]} public repositories  ·  {len(langs)} languages  ·  '
               f'{human(total_bytes)} of source  ·  since {since}')

    style = ("@keyframes grow{0%{transform:scaleX(0)}12%,100%{transform:scaleX(1)}}"
             "@keyframes rise{0%{opacity:0;transform:translateY(6px)}10%,100%{opacity:1;transform:translateY(0)}}"
             "@keyframes sheen{0%,40%{transform:translateX(-200px)}70%,100%{transform:translateX(900px)}}"
             f".grow{{transform-origin:0 0;animation:grow 11s {EASE} infinite}}"
             f".rise{{opacity:0;animation:rise 11s {EASE} infinite}}"
             ".sheen{animation:sheen 11s ease-in-out infinite}")

    body = (
        f'<defs><clipPath id="bar"><rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" '
        f'height="{BAR_H}" rx="{BAR_H // 2}"/></clipPath>'
        '<linearGradient id="sheen" x1="0" x2="1">'
        f'<stop offset="0" stop-color="{t["INK"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{t["INK"]}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{t["INK"]}" stop-opacity="0"/></linearGradient></defs>'
        f'<text x="4" y="26" font-family="{MONO}" font-size="13" fill="{t["DIM"]}">'
        f'{esc(summary)}</text>'
        f'<rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" rx="{BAR_H // 2}" '
        f'fill="{t["FAINT"]}" fill-opacity=".55"/>'
        f'<g clip-path="url(#bar)">{"".join(segs)}'
        f'<rect class="sheen" y="{BAR_Y}" width="200" height="{BAR_H}" fill="url(#sheen)"/></g>'
        + "".join(legend))
    return svg(W, 128, "Language breakdown", body, style)


# --------------------------------------------------------------------------
# divider / footer
# --------------------------------------------------------------------------

def build_divider(t):
    W, H = 900, 18
    style = ("@keyframes sweep{0%{transform:translateX(-260px)}100%{transform:translateX(900px)}}"
             f".beam{{animation:sweep 6s {EASE} infinite}}")
    body = (
        "<defs>"
        f'<linearGradient id="glow" x1="0" x2="1">'
        f'<stop offset="0" stop-color="{t["A1"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{t["A2"]}"/>'
        f'<stop offset="1" stop-color="{t["A3"]}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="strip"><rect width="{W}" height="{H}"/></clipPath></defs>'
        f'<rect x="4" y="8" width="868" height="1.4" rx="1" fill="{t["FAINT"]}"/>'
        '<g clip-path="url(#strip)">'
        '<rect class="beam" y="7.2" width="260" height="3" rx="1.5" fill="url(#glow)"/></g>')
    return svg(W, H, "", body, style)


def build_footer(t):
    W, H = 900, 96
    wave = "q75 {a} 150 0" + "t150 0" * 10
    style = ("@keyframes roll{from{transform:translateX(0)}to{transform:translateX(-300px)}}"
             "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}"
             "@keyframes ping{0%{transform:scale(1);opacity:.8}80%,100%{transform:scale(3);opacity:0}}"
             ".w1{animation:roll 9s linear infinite}.w2{animation:roll 14s linear infinite reverse}"
             ".w3{animation:roll 20s linear infinite}.bob{animation:bob 5s ease-in-out infinite}"
             ".rng{transform-origin:450px 22px;animation:ping 2.6s ease-out infinite}")
    waves = "".join(
        f'<g transform="translate(-300,0)"><path class="w{i}" d="M0 {y}{wave.format(a=a)}V{H}H0Z" '
        f'fill="url(#{g})" fill-opacity="{o}"/></g>'
        for i, y, a, g, o in ((3, 54, -20, "g2", ".16"), (2, 62, -24, "g1", ".22"),
                              (1, 70, -18, "g1", ".38")))
    body = (
        "<defs>"
        f'<linearGradient id="g1" x1="0" x2="1"><stop offset="0" stop-color="{t["A1"]}"/>'
        f'<stop offset=".5" stop-color="{t["A2"]}"/><stop offset="1" stop-color="{t["A3"]}"/>'
        "</linearGradient>"
        f'<linearGradient id="g2" x1="1" x2="0"><stop offset="0" stop-color="{t["A4"]}"/>'
        f'<stop offset="1" stop-color="{t["A2"]}"/></linearGradient>'
        f'<clipPath id="clip"><rect width="{W}" height="{H}"/></clipPath></defs>'
        '<g clip-path="url(#clip)">'
        f'<g class="bob"><circle class="rng" cx="450" cy="22" r="4.5" fill="none" '
        f'stroke="{t["A2"]}" stroke-width="1.8"/>'
        '<circle cx="450" cy="22" r="4.5" fill="url(#g1)"/></g>' + waves + "</g>")
    return svg(W, H, "", body, style)


def chip(t, label, accent_key, glyph):
    """A contact pill. Shields.io badges can't follow the reader's theme, so a
    fixed dark badge would be the same pasted-on rectangle this file exists to
    avoid — these are drawn per colourway instead."""
    a = t[accent_key]
    w = 46 + len(label) * 7.4
    style = ("@keyframes hum{0%,100%{opacity:.55;transform:scale(.9)}50%{opacity:1;transform:scale(1.15)}}"
             "@keyframes slide{0%,55%{transform:translateX(-70px)}85%,100%{transform:translateX("
             + str(int(w) + 70) + "px)}}"
             ".dot{transform-origin:24px 18px;animation:hum 3.2s ease-in-out infinite}"
             ".sheen{animation:slide 7s " + EASE + " infinite}")
    body = (
        f'<defs><clipPath id="pill"><rect x="1" y="1" width="{fmt(w - 2)}" height="34" rx="17"/></clipPath>'
        f'<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="{a}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{a}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{a}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="1" y="1" width="{fmt(w - 2)}" height="34" rx="17" fill="{a}" fill-opacity=".07" '
        f'stroke="{a}" stroke-opacity=".55"/>'
        f'<g clip-path="url(#pill)"><rect class="sheen" y="1" width="70" height="34" fill="url(#sh)"/></g>'
        f'<circle class="dot" cx="24" cy="18" r="4" fill="{a}"/>'
        f'<text x="38" y="23" font-family="{SANS}" font-size="13" font-weight="500" '
        f'fill="{t["INK"]}">{esc(label)}</text>')
    return svg(int(w), 36, glyph, body, style)


BUILDERS = {
    "header": build_header, "activity": build_activity, "langs": build_langs,
    "divider": build_divider, "footer": build_footer,
    "chip-email": lambda t: chip(t, "thakurashutosh042003@gmail.com", "A1", "Email"),
    "chip-linkedin": lambda t: chip(t, "linkedin.com/in/ashutosh-thakur", "A2", "LinkedIn"),
}


if __name__ == "__main__":
    for theme, tok in THEMES.items():
        worst = min(((contrast(tok[k], tok["PAGE"]), k) for k in
                     ("INK", "DIM", "A1", "A2", "A3", "A4")))
        for name, fn in BUILDERS.items():
            (OUT / f"{name}-{theme}.svg").write_text(fn(tok), encoding="utf-8")
        print(f"{theme:5s} -> {len(BUILDERS)} svgs   lowest contrast on page: "
              f"{worst[1]} {worst[0]:.2f}:1 {'OK' if worst[0] >= 4.5 else 'FAILS AA'}")
    print(f"data from {DATA['fetched']} - {len(DATA['commits'])} commits, "
          f"{DATA['user']['repos']} repos")
