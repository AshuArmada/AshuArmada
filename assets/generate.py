#!/usr/bin/env python3
"""
Generates every animated SVG in the README from one set of design tokens.

    python assets/generate.py

Everything is pure SMIL + CSS: GitHub serves these through its image proxy,
where <script> never runs, so the animation has to be declarative.

Produces header, terminal, git-graph, divider and footer. stats.svg is built by
stats.py, which imports the tokens below so it stays on-system.
"""

import random
from pathlib import Path

OUT = Path(__file__).parent

# ---------------------------------------------------------------------------
# design tokens — the single source of truth for every asset
# ---------------------------------------------------------------------------

MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

INK = "#e6edf3"   # primary text           16.0:1 on the card
DIM = "#8b949e"   # secondary text          6.2:1 on the card
CYAN = "#22d3ee"  # accent 1 — primary
VIOLET = "#a78bfa"  # accent 2 — secondary
PINK = "#f472b6"  # accent 3 — highlight
SKY = "#7dd3fc"   # accent 4 — supporting tint

SURFACE = ("#0d1224", "#0b1020", "#141a30")  # card gradient stops
LINE = "#8ab4ff"                             # grid + border hue

# motion tokens. One easing family, one ambient period, so every card shares a
# rhythm instead of each asset inventing its own.
EASE = "cubic-bezier(.16,1,.3,1)"    # expo-out — entrances
SPRING = "cubic-bezier(.2,1.5,.4,1)"  # overshoot — things that "pop" in
EDGE_DUR = 9                          # ambient border light, all cards

BASE_CSS = (
    "@keyframes edge{to{stroke-dashoffset:-100}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)
REDUCED = ""  # kept for import compatibility; the reduced-motion rule lives in BASE_CSS


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def dedupe(frames):
    """Collapse frames sharing a timestamp, keeping the last one."""
    out = []
    for f in sorted(frames, key=lambda f: f[0]):
        if out and abs(out[-1][0] - f[0]) < 1e-9:
            out[-1] = f
        else:
            out.append(list(f))
    return out


def animate(attr, dur, frames, index):
    """A discrete <animate> over (time, v0, v1, ...) frames."""
    times = ";".join(fmt(f[0] / dur) for f in frames)
    values = ";".join(fmt(f[index]) for f in frames)
    return (
        f'<animate attributeName="{attr}" dur="{fmt(dur)}s" repeatCount="indefinite"'
        f' calcMode="discrete" keyTimes="{times}" values="{values}"/>'
    )


# --------------------------------------------------------------------------
# typewriter timelines
# --------------------------------------------------------------------------

def rotator(phrases, size, x, y, type_cps=0.075, hold=1.9, del_cps=0.032, gap=0.45):
    """Type each phrase, hold, delete it, move to the next. Loops forever.

    A phrase is hidden simply by clipping it to zero width, so no separate
    visibility track is needed.
    """
    adv = size * 0.6
    slots, t = [], 0.0
    for p in phrases:
        t_in, t_del = len(p) * type_cps, len(p) * del_cps
        slots.append((t, t_in, t_del, p))
        t += t_in + hold + t_del + gap
    total = t

    clips, texts, caret_frames = [], [], []
    for i, (t0, t_in, t_del, phrase) in enumerate(slots):
        n = len(phrase)
        frames = [(0.0, 0.0), (t0, 0.0)]
        for k in range(1, n + 1):
            frames.append((t0 + k * t_in / n, k * adv))
        frames.append((t0 + t_in + hold, n * adv))
        for k in range(n - 1, -1, -1):
            frames.append((t0 + t_in + hold + (n - k) * t_del / n, k * adv))
        frames.append((total, 0.0))
        frames = dedupe(frames)
        caret_frames += [(f[0], x + f[1]) for f in frames]

        clips.append(
            f'<clipPath id="rot{i}"><rect x="{fmt(x)}" y="{fmt(y - size)}" '
            f'height="{fmt(size * 1.45)}" width="0">{animate("width", total, frames, 1)}'
            f"</rect></clipPath>"
        )
        texts.append(
            f'<text x="{fmt(x)}" y="{fmt(y)}" clip-path="url(#rot{i})" font-family="{MONO}" '
            f'font-size="{fmt(size)}" fill="{INK}">{esc(phrase)}</text>'
        )

    caret = (
        f'<rect y="{fmt(y - size * 0.78)}" width="{fmt(adv * 0.9)}" height="{fmt(size)}" '
        f'rx="1" fill="{CYAN}" opacity=".85">'
        f'{animate("x", total, dedupe(caret_frames), 1)}'
        f'<animate attributeName="opacity" values=".9;.9;0;0;.9" dur="1.06s" repeatCount="indefinite"/>'
        f"</rect>"
    )
    return "".join(clips) + "".join(texts) + caret


def typed_lines(lines, size, x, y0, line_h, type_cps=0.045, pause=0.55, tail=2.6):
    """Type lines one after another; they stay on screen until the loop restarts."""
    adv = size * 0.6
    starts, t = [], 0.4
    for text, _ in lines:
        starts.append(t)
        t += len(text) * type_cps + pause
    total = t + tail

    clips, texts, caret = [], [], []
    for i, ((text, fill), t0) in enumerate(zip(lines, starts)):
        n = max(len(text), 1)
        t_in = n * type_cps
        y = y0 + i * line_h
        frames = [(0.0, 0.0), (t0, 0.0)]
        for k in range(1, n + 1):
            frames.append((t0 + k * t_in / n, k * adv))
        frames.append((total, n * adv))
        frames = dedupe(frames)
        caret += [(f[0], x + f[1], y) for f in frames]

        clips.append(
            f'<clipPath id="ln{i}"><rect x="{fmt(x)}" y="{fmt(y - size)}" '
            f'height="{fmt(size * 1.5)}" width="0">{animate("width", total, frames, 1)}'
            f"</rect></clipPath>"
        )
        texts.append(
            f'<text x="{fmt(x)}" y="{fmt(y)}" clip-path="url(#ln{i})" font-family="{MONO}" '
            f'font-size="{fmt(size)}" fill="{fill}" xml:space="preserve">{esc(text)}</text>'
        )

    caret = dedupe(caret)
    cursor = (
        f'<rect width="{fmt(adv * 0.9)}" height="{fmt(size)}" rx="1" fill="{CYAN}">'
        f'{animate("x", total, caret, 1)}'
        + animate("y", total, [(f[0], f[2] - size * 0.78) for f in caret], 1)
        + '<animate attributeName="opacity" values=".9;.9;0;0;.9" dur="1.06s" repeatCount="indefinite"/>'
        "</rect>"
    )
    return "".join(clips) + "".join(texts) + cursor


# --------------------------------------------------------------------------
# shared card chrome
# --------------------------------------------------------------------------

def card(w, h, rx=18):
    """Defs every card shares: clip, surface gradient, grid, accent ramp."""
    a, b, c = SURFACE
    return (
        f'<clipPath id="card"><rect width="{w}" height="{h}" rx="{rx}"/></clipPath>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{a}"/><stop offset=".55" stop-color="{b}"/>'
        f'<stop offset="1" stop-color="{c}"/></linearGradient>'
        f'<pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">'
        f'<path d="M34 0H0v34" fill="none" stroke="{LINE}" stroke-opacity=".055"/></pattern>'
        f'<linearGradient id="ramp" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{VIOLET}"/>'
        f'<stop offset="1" stop-color="{PINK}"/></linearGradient>'
    )


def frame(w, h, rx=18):
    """Static hairline border plus the ambient light that travels around it.

    This is the one motion signature shared by every card — it's what makes the
    separate images read as a single system rather than five unrelated banners.
    """
    inset = f'x=".75" y=".75" width="{fmt(w - 1.5)}" height="{fmt(h - 1.5)}" rx="{rx}"'
    return (
        f'<rect {inset} fill="none" stroke="{LINE}" stroke-opacity=".18"/>'
        f'<rect {inset} fill="none" stroke="url(#ramp)" stroke-width="1.5" opacity=".75" '
        f'pathLength="100" stroke-dasharray="5 95" stroke-linecap="round" '
        f'style="animation:edge {EDGE_DUR}s linear infinite"/>'
    )


def svg(w, h, title, body, style=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><style>{style}{BASE_CSS}</style>{body}</svg>\n"
    )


def node(x, y, color, delay, r=9, core=False):
    """A commit: a ring that pops in, plus a one-shot ping the moment it lands."""
    inner = f'<circle r="{fmt(r * 0.34)}" fill="{color}"/>' if core else ""
    return (
        f'<g transform="translate({fmt(x)},{fmt(y)})">'
        f'<g class="ping" style="animation-delay:{fmt(delay)}s">'
        f'<circle r="{fmt(r)}" fill="none" stroke="{color}" stroke-width="2"/></g>'
        f'<g class="n" style="animation-delay:{fmt(delay)}s">'
        f'<circle r="{fmt(r)}" fill="{SURFACE[1]}" stroke="{color}" stroke-width="3"/>{inner}</g>'
        "</g>"
    )


# --------------------------------------------------------------------------
# header.svg
# --------------------------------------------------------------------------

def build_header():
    W, H = 900, 260
    rnd = random.Random(7)

    motes = []
    for _ in range(22):
        cx, cy = rnd.uniform(20, W - 20), rnd.uniform(16, H - 16)
        motes.append(
            f'<circle class="mote" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(rnd.uniform(0.9, 2.3))}" '
            f'fill="{rnd.choice([CYAN, VIOLET, PINK, SKY])}" '
            f'style="animation-duration:{fmt(rnd.uniform(7, 15))}s;'
            f'animation-delay:-{fmt(rnd.uniform(0, 12))}s"/>'
        )

    defs = (
        "<defs>"
        + card(W, H)
        + "".join(
            f'<radialGradient id="au{i}"><stop offset="0" stop-color="{c}" stop-opacity="{o}"/>'
            f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
            for i, (c, o) in enumerate(((VIOLET, ".55"), (CYAN, ".5"), (PINK, ".38")), 1)
        )
        # a highlight that travels across the name
        + f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="-320" y1="0" x2="-60" y2="0">'
        f'<stop offset="0" stop-color="{INK}"/><stop offset=".42" stop-color="{INK}"/>'
        f'<stop offset=".5" stop-color="#ffffff"/><stop offset=".58" stop-color="{CYAN}"/>'
        f'<stop offset="1" stop-color="{INK}"/>'
        f'<animate attributeName="x1" values="-320;900" dur="4.6s" repeatCount="indefinite"/>'
        f'<animate attributeName="x2" values="-60;1160" dur="4.6s" repeatCount="indefinite"/>'
        "</linearGradient>"
        f'<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{CYAN}"/><stop offset=".5" stop-color="{VIOLET}"/>'
        f'<stop offset="1" stop-color="{PINK}" stop-opacity="0"/></linearGradient>'
        "</defs>"
    )

    style = (
        "@keyframes drift{to{transform:translate(-34px,-34px)}}"
        "@keyframes mote{0%,100%{transform:translateY(0);opacity:.25}"
        "50%{transform:translateY(-22px);opacity:.9}}"
        "@keyframes blob{0%,100%{transform:translate(0,0) scale(1)}"
        "33%{transform:translate(70px,-26px) scale(1.18)}"
        "66%{transform:translate(-52px,20px) scale(.88)}}"
        f"@keyframes rule{{0%{{stroke-dashoffset:260}}45%,100%{{stroke-dashoffset:0}}}}"
        "@keyframes bracket{0%,100%{opacity:.25}50%{opacity:.9}}"
        "@keyframes ping{0%{r:4;opacity:.9}75%,100%{r:13;opacity:0}}"
        ".mote{animation:mote ease-in-out infinite}"
        ".blob{animation:blob 19s ease-in-out infinite;transform-origin:center}"
    )

    body = (
        defs
        + '<g clip-path="url(#card)">'
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        f'<g class="blob"><ellipse cx="150" cy="60" rx="210" ry="150" fill="url(#au1)"/></g>'
        f'<g class="blob" style="animation-delay:-7s"><ellipse cx="760" cy="210" rx="230" ry="160" fill="url(#au2)"/></g>'
        f'<g class="blob" style="animation-delay:-13s"><ellipse cx="470" cy="20" rx="180" ry="120" fill="url(#au3)"/></g>'
        f'<rect x="-40" y="-40" width="{W + 80}" height="{H + 80}" fill="url(#grid)" '
        'style="animation:drift 6s linear infinite"/>'
        + "".join(motes)
        + "</g>"
        + f'<path d="M28 62V34h30" fill="none" stroke="{CYAN}" stroke-width="2" stroke-linecap="round" '
        'style="animation:bracket 3.4s ease-in-out infinite"/>'
        + f'<path d="M872 198v28h-30" fill="none" stroke="{PINK}" stroke-width="2" stroke-linecap="round" '
        'style="animation:bracket 3.4s ease-in-out infinite;animation-delay:-1.7s"/>'
        + f'<text x="56" y="112" font-family="{SANS}" font-size="52" font-weight="700" '
        f'letter-spacing="-1" fill="url(#shine)">Ashutosh Thakur</text>'
        + f'<path d="M56 132h260" stroke="url(#rule)" stroke-width="2.5" stroke-linecap="round" '
        f'stroke-dasharray="260" stroke-dashoffset="260" style="animation:rule 4.5s {EASE} infinite"/>'
        + f'<text x="56" y="184" font-family="{MONO}" font-size="22" fill="{CYAN}">&#10095;</text>'
        + rotator(
            ["full-stack developer", "AI / ML engineer", "building Gitify",
             "LLM-backed developer tools"],
            22, 84, 184,
        )
        + f'<circle cx="820" cy="52" r="4" fill="{CYAN}"/>'
        + f'<circle cx="820" cy="52" r="4" fill="none" stroke="{CYAN}" stroke-width="1.5" '
        'style="animation:ping 2.2s ease-out infinite"/>'
        + f'<text x="806" y="56" text-anchor="end" font-family="{MONO}" font-size="12" '
        f'fill="{DIM}">open to collab</text>'
        + f'<text x="56" y="222" font-family="{MONO}" font-size="13" fill="{DIM}">'
        "building tools that make hard things visible</text>"
        + frame(W, H)
    )
    (OUT / "header.svg").write_text(svg(W, H, "Ashutosh Thakur", body, style), encoding="utf-8")


# --------------------------------------------------------------------------
# terminal.svg
# --------------------------------------------------------------------------

def build_terminal():
    W, H = 900, 264
    lines = [
        ("$ git checkout -b feat/animated-commit-tree", INK),
        ("  Switched to a new branch 'feat/animated-commit-tree'", DIM),
        ("$ git rebase -i HEAD~3", INK),
        ("  pick a1c9e2f  render tree     squash 4f10bd3  fix layout", DIM),
        ("$ gitify lesson --open interactive-rebase", CYAN),
        ("  ✓ sandbox ready · real git, real objects, animated", VIOLET),
    ]

    style = (
        "@keyframes scan{0%{transform:translateY(-60px)}100%{transform:translateY(300px)}}"
        "@keyframes glow{0%,100%{opacity:.35}50%{opacity:.85}}"
    )
    # window controls on the accent ramp — macOS red/amber/green would drag a
    # third palette into the README
    dots = "".join(
        f'<circle cx="{28 + i * 20}" cy="26" r="6" fill="{c}" opacity=".9" '
        f'style="animation:glow 3s ease-in-out infinite;animation-delay:-{i * 0.4}s"/>'
        for i, c in enumerate([PINK, VIOLET, CYAN])
    )

    body = (
        "<defs>" + card(W, H, 14) + "</defs>"
        + '<g clip-path="url(#card)">'
        + f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        + f'<rect width="{W}" height="{H}" fill="url(#grid)"/>'
        + f'<rect width="{W}" height="52" fill="#ffffff" fill-opacity=".04"/>'
        + f'<rect y="52" width="{W}" height="1" fill="{LINE}" fill-opacity=".16"/>'
        + dots
        + f'<text x="{W // 2}" y="31" text-anchor="middle" font-family="{MONO}" font-size="13" '
        f'fill="{DIM}">ashutosh@gitify — zsh</text>'
        + typed_lines(lines, 15, 28, 92, 29)
        + f'<rect width="{W}" height="60" fill="{CYAN}" fill-opacity=".035" '
        'style="animation:scan 5.5s linear infinite"/>'
        + "</g>"
        + frame(W, H, 14)
    )
    (OUT / "terminal.svg").write_text(svg(W, H, "Terminal session", body, style), encoding="utf-8")


# --------------------------------------------------------------------------
# git-graph.svg
# --------------------------------------------------------------------------

def build_graph():
    W, H = 900, 250
    MAIN, FEAT = 180, 110  # lane baselines

    segs = [
        ("M46 180H250", CYAN, "1", 0.05),
        ("M250 180H690", CYAN, ".45", 1.7),
        ("M690 180H858", CYAN, "1", 5.5),
        ("M250 180C300 180 306 110 360 110", VIOLET, "1", 1.8),
        ("M360 110H600", VIOLET, "1", 2.3),
        ("M600 110C652 110 660 180 690 180", PINK, "1", 4.6),
    ]
    lanes = "".join(
        f'<path class="seg" fill="none" d="{d}" pathLength="100" stroke="{c}" '
        f'stroke-opacity="{o}" style="animation-delay:{fmt(t)}s"/>'
        for d, c, o, t in segs
    )

    commits = (
        "".join(node(x, MAIN, CYAN, t) for x, t in ((90, 0.3), (170, 0.85), (250, 1.4)))
        + "".join(node(x, FEAT, VIOLET, t) for x, t in ((400, 2.9), (480, 3.5), (560, 4.1)))
        + node(690, MAIN, PINK, 5.2, r=12, core=True)
        + node(780, MAIN, CYAN, 6.0)
    )

    labels = "".join(
        f'<text x="{x}" y="{y}" class="lbl" fill="{c}" style="animation-delay:{fmt(t)}s">{esc(s)}</text>'
        for x, y, c, t, s in (
            (28, 36, DIM, 0.0, "git log --graph --oneline"),
            (46, 160, CYAN, 0.15, "main"),
            (360, 88, VIOLET, 2.4, "feat/animated-commit-tree"),
            (706, 154, PINK, 5.4, "merge --no-ff"),
        )
    )

    # packets tracing each lane, so both branches read as live
    packets = (
        f'<circle r="3" fill="{CYAN}" style="animation:flow 4.5s linear infinite">'
        f'<animateMotion dur="4.5s" repeatCount="indefinite" path="M46 180H858"/></circle>'
        f'<circle r="2.6" fill="{VIOLET}" style="animation:flow 4.5s linear infinite;animation-delay:-2.2s">'
        f'<animateMotion dur="4.5s" repeatCount="indefinite" begin="-2.2s" '
        f'path="M250 180C300 180 306 110 360 110H600C652 110 660 180 690 180"/></circle>'
    )

    # HEAD walks the graph — SMIL, because CSS transforms on <g> are less
    # reliably supported by the renderers that serve README images
    head = (
        f'<g opacity="0" transform="translate(250,180)">'
        '<animateTransform attributeName="transform" type="translate" dur="12s" repeatCount="indefinite"'
        ' keyTimes="0;0.13;0.24;0.25;0.29;0.30;0.34;0.35;0.43;0.442;0.50;0.508;1"'
        ' values="250 180;250 180;250 180;400 110;400 110;480 110;480 110;560 110;560 110;'
        '690 180;690 180;780 180;780 180"/>'
        '<animate attributeName="opacity" dur="12s" repeatCount="indefinite"'
        ' keyTimes="0;0.12;0.14;0.96;1" values="0;0;1;1;0"/>'
        f'<path d="M0 12v10" stroke="{INK}" stroke-width="1.5" stroke-opacity=".5"/>'
        f'<rect x="-29" y="22" width="58" height="22" rx="7" fill="{INK}" fill-opacity=".1" '
        f'stroke="{INK}" stroke-opacity=".45"/>'
        f'<text x="0" y="37" text-anchor="middle" font-family="{MONO}" font-size="12" '
        f'fill="{INK}">HEAD</text></g>'
    )

    style = (
        "@keyframes draw{0%{stroke-dashoffset:100}6%,100%{stroke-dashoffset:0}}"
        "@keyframes pop{0%{transform:scale(0);opacity:0}4%{transform:scale(1.35);opacity:1}"
        "7%,100%{transform:scale(1);opacity:1}}"
        "@keyframes ping{0%{transform:scale(.5);opacity:.85}9%{transform:scale(2.9);opacity:0}"
        "9.01%,100%{opacity:0}}"
        "@keyframes fade{0%{opacity:0}5%,100%{opacity:1}}"
        "@keyframes flow{0%,100%{opacity:0}10%,90%{opacity:.9}}"
        ".seg{stroke-dasharray:100;stroke-dashoffset:100;stroke-width:3;stroke-linecap:round;"
        f"animation:draw 12s {EASE} infinite}}"
        f".n{{opacity:0;transform-origin:0 0;animation:pop 12s {SPRING} infinite}}"
        ".ping{opacity:0;transform-origin:0 0;animation:ping 12s ease-out infinite}"
        f".lbl{{opacity:0;animation:fade 12s {EASE} infinite;font-family:{MONO};font-size:13px}}"
    )

    body = (
        "<defs>" + card(W, H) + "</defs>"
        + '<g clip-path="url(#card)">'
        + f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        + f'<rect width="{W}" height="{H}" fill="url(#grid)"/>'
        + lanes + packets + labels + commits + head
        + "</g>"
        + frame(W, H)
    )
    (OUT / "git-graph.svg").write_text(
        svg(W, H, "Animated commit graph: a feature branch is created, takes three "
                  "commits, and is merged back into main", body, style), encoding="utf-8")


# --------------------------------------------------------------------------
# divider.svg / footer.svg
# --------------------------------------------------------------------------

def build_divider():
    W, H = 900, 20
    style = (
        "@keyframes sweep{0%{transform:translateX(-300px)}100%{transform:translateX(900px)}}"
        "@keyframes pulse{0%,100%{opacity:.35;transform:scale(.8)}50%{opacity:1;transform:scale(1.25)}}"
        f".beam{{animation:sweep 6s {EASE} infinite}}"
        ".dot{transform-origin:450px 10px;animation:pulse 3s ease-in-out infinite}"
    )
    body = (
        "<defs>"
        f'<linearGradient id="rail" x1="0" x2="1">'
        f'<stop offset="0" stop-color="{LINE}" stop-opacity="0"/>'
        f'<stop offset=".2" stop-color="{LINE}" stop-opacity=".3"/>'
        f'<stop offset=".8" stop-color="{LINE}" stop-opacity=".3"/>'
        f'<stop offset="1" stop-color="{LINE}" stop-opacity="0"/></linearGradient>'
        f'<linearGradient id="glow" x1="0" x2="1">'
        f'<stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{VIOLET}"/>'
        f'<stop offset="1" stop-color="{PINK}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="strip"><rect width="{W}" height="{H}"/></clipPath>'
        "</defs>"
        f'<rect y="9" width="{W}" height="1.6" rx="1" fill="url(#rail)"/>'
        '<g clip-path="url(#strip)">'
        '<rect class="beam" y="8" width="300" height="3.5" rx="2" fill="url(#glow)"/></g>'
        f'<circle class="dot" cx="450" cy="10" r="3" fill="{VIOLET}"/>'
    )
    (OUT / "divider.svg").write_text(svg(W, H, "Divider", body, style), encoding="utf-8")


def build_footer():
    W, H = 900, 140
    wave = "q75 {a} 150 0" + "t150 0" * 10
    style = (
        "@keyframes roll{from{transform:translateX(0)}to{transform:translateX(-300px)}}"
        "@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}"
        "@keyframes ping{0%{transform:scale(1);opacity:.8}80%,100%{transform:scale(3.2);opacity:0}}"
        ".w1{animation:roll 9s linear infinite}"
        ".w2{animation:roll 14s linear infinite reverse}"
        ".w3{animation:roll 20s linear infinite}"
        ".bob{animation:bob 5s ease-in-out infinite}"
        ".rng{transform-origin:450px 44px;animation:ping 2.6s ease-out infinite}"
    )
    waves = "".join(
        f'<g transform="translate(-300,0)"><path class="w{i}" '
        f'd="M0 {y}{wave.format(a=a)}V{H}H0Z" fill="url(#{g})" fill-opacity="{o}"/></g>'
        for i, y, a, g, o in ((3, 96, -22, "g2", ".14"), (2, 104, -26, "g1", ".2"), (1, 112, -20, "g1", ".35"))
    )
    body = (
        "<defs>"
        f'<linearGradient id="g1" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/>'
        f'<stop offset=".5" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>'
        f'<linearGradient id="g2" x1="1" x2="0"><stop offset="0" stop-color="{SKY}"/>'
        f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
        f'<clipPath id="clip"><rect width="{W}" height="{H}"/></clipPath>'
        "</defs>"
        '<g clip-path="url(#clip)">'
        f'<g class="bob"><circle class="rng" cx="450" cy="44" r="5" fill="none" stroke="{VIOLET}" '
        'stroke-width="2"/><circle cx="450" cy="44" r="5" fill="url(#g1)"/></g>'
        + waves + "</g>"
    )
    (OUT / "footer.svg").write_text(svg(W, H, "Footer", body, style), encoding="utf-8")


if __name__ == "__main__":
    build_header()
    build_terminal()
    build_graph()
    build_divider()
    build_footer()
    print("wrote header, terminal, git-graph, divider, footer")
