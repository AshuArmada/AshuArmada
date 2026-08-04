#!/usr/bin/env python3
"""
Generates the animated SVGs used by the profile README.

    python assets/generate.py

Everything is pure SMIL + CSS: GitHub serves these through its image proxy,
where <script> never runs, so the animation has to be declarative.

Produces:
    header.svg    hero card, shimmering name, rotating typewriter
    terminal.svg  a git session typing itself out
"""

import random
from pathlib import Path

OUT = Path(__file__).parent

MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

INK = "#e6edf3"
DIM = "#8b949e"
CYAN = "#22d3ee"
VIOLET = "#a78bfa"
PINK = "#f472b6"

REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


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
# shared chrome
# --------------------------------------------------------------------------

def card(w, h, rx=18):
    return (
        f'<clipPath id="card"><rect width="{w}" height="{h}" rx="{rx}"/></clipPath>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#0d1224"/><stop offset=".55" stop-color="#0b1020"/>'
        f'<stop offset="1" stop-color="#141a30"/></linearGradient>'
        f'<pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">'
        f'<path d="M34 0H0v34" fill="none" stroke="#8ab4ff" stroke-opacity=".055"/></pattern>'
    )


def frame(w, h, rx=18):
    return (
        f'<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="{rx}" fill="none" '
        f'stroke="#8ab4ff" stroke-opacity=".18"/>'
    )


def svg(w, h, title, body, style=""):
    css = f"<style>{REDUCED}{style}</style>" if (style or REDUCED) else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title>{css}{body}</svg>\n"
    )


# --------------------------------------------------------------------------
# header.svg
# --------------------------------------------------------------------------

def build_header():
    W, H = 900, 260
    rnd = random.Random(7)

    motes = []
    for i in range(22):
        cx, cy = rnd.uniform(20, W - 20), rnd.uniform(16, H - 16)
        r = rnd.uniform(0.9, 2.3)
        col = rnd.choice([CYAN, VIOLET, PINK, "#7dd3fc"])
        motes.append(
            f'<circle class="mote" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="{col}" '
            f'style="animation-duration:{fmt(rnd.uniform(7, 15))}s;'
            f'animation-delay:-{fmt(rnd.uniform(0, 12))}s"/>'
        )

    defs = (
        "<defs>"
        + card(W, H)
        + f'<radialGradient id="au1"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="au2"><stop offset="0" stop-color="{CYAN}" stop-opacity=".5"/>'
        f'<stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="au3"><stop offset="0" stop-color="{PINK}" stop-opacity=".38"/>'
        f'<stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>'
        # a highlight that travels across the name
        f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" x1="-320" y1="0" x2="-60" y2="0">'
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
        "@keyframes rule{0%{stroke-dashoffset:260}45%,100%{stroke-dashoffset:0}}"
        "@keyframes bracket{0%,100%{opacity:.25}50%{opacity:.9}}"
        "@keyframes ping{0%{r:4;opacity:.9}75%,100%{r:13;opacity:0}}"
        ".mote{animation:mote ease-in-out infinite}"
        ".blob{animation:blob 19s ease-in-out infinite;transform-origin:center}"
        + REDUCED
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
        # corner brackets
        + f'<path d="M28 62V34h30" fill="none" stroke="{CYAN}" stroke-width="2" stroke-linecap="round" '
        'style="animation:bracket 3.4s ease-in-out infinite"/>'
        + f'<path d="M872 198v28h-30" fill="none" stroke="{PINK}" stroke-width="2" stroke-linecap="round" '
        'style="animation:bracket 3.4s ease-in-out infinite;animation-delay:-1.7s"/>'
        # name
        + f'<text x="56" y="112" font-family="{SANS}" font-size="52" font-weight="700" '
        f'letter-spacing="-1" fill="url(#shine)">Ashutosh Thakur</text>'
        + f'<path d="M56 132h260" stroke="url(#rule)" stroke-width="2.5" stroke-linecap="round" '
        'stroke-dasharray="260" stroke-dashoffset="260" style="animation:rule 4.5s ease-out infinite"/>'
        # prompt + rotating role
        + f'<text x="56" y="184" font-family="{MONO}" font-size="22" fill="{CYAN}">&#10095;</text>'
        + rotator(
            [
                "full-stack developer",
                "AI / ML engineer",
                "building Gitify",
                "LLM-backed developer tools",
            ],
            22,
            84,
            184,
        )
        # live dot
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

    defs = "<defs>" + card(W, H, 14) + "</defs>"
    style = (
        "@keyframes scan{0%{transform:translateY(-60px)}100%{transform:translateY(300px)}}"
        "@keyframes glow{0%,100%{opacity:.35}50%{opacity:.85}}" + REDUCED
    )

    dots = "".join(
        f'<circle cx="{28 + i * 20}" cy="26" r="6" fill="{c}" opacity=".9" '
        f'style="animation:glow 3s ease-in-out infinite;animation-delay:-{i * 0.4}s"/>'
        for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"])
    )

    body = (
        defs
        + '<g clip-path="url(#card)">'
        + f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
        + f'<rect width="{W}" height="{H}" fill="url(#grid)"/>'
        + f'<rect x="0" y="0" width="{W}" height="52" fill="#ffffff" fill-opacity=".04"/>'
        + f'<rect x="0" y="52" width="{W}" height="1" fill="#8ab4ff" fill-opacity=".16"/>'
        + dots
        + f'<text x="{W // 2}" y="31" text-anchor="middle" font-family="{MONO}" font-size="13" '
        f'fill="{DIM}">ashutosh@gitify — zsh</text>'
        + typed_lines(lines, 15, 28, 92, 29)
        # CRT sweep
        + f'<rect width="{W}" height="60" fill="{CYAN}" fill-opacity=".035" '
        'style="animation:scan 5.5s linear infinite"/>'
        + "</g>"
        + frame(W, H, 14)
    )
    (OUT / "terminal.svg").write_text(svg(W, H, "Terminal session", body, style), encoding="utf-8")


if __name__ == "__main__":
    build_header()
    build_terminal()
    print("wrote header.svg, terminal.svg")
