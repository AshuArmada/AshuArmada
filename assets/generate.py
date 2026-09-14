#!/usr/bin/env python3
"""Render GitHub-safe profile artwork. Run python assets/generate.py after fetch.py.

All graphics are local SVGs with theme-specific palettes. Motion is CSS-only,
with a complete static composition and a prefers-reduced-motion fallback.
"""
import json
import textwrap
from html import escape
from pathlib import Path

OUT = Path(__file__).parent
DATA = json.loads((OUT / 'data.json').read_text(encoding='utf-8'))
SANS = 'Arial,Helvetica,sans-serif'
MONO = 'Consolas,monospace'
THEMES = {
    'dark': dict(panel='#151c25', ink='#f0f4f8', dim='#9aaabd', line='#303d4c', accent='#b6f36a', blue='#89aaff', cards=['#a5b4fc', '#5eead4', '#f9a8d4', '#fcd34d', '#7dd3fc', '#c4b5fd']),
    'light': dict(panel='#f3f6f9', ink='#142130', dim='#526477', line='#d4dee7', accent='#416d11', blue='#315ed0', cards=['#4338ca', '#0f766e', '#be185d', '#92400e', '#0369a1', '#6d28d9']),
}


def text(x, y, value, color, size=14, weight=400, mono=False, extra=''):
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="{MONO if mono else SANS}" font-size="{size}" font-weight="{weight}" {extra}>{escape(str(value))}</text>'


def rect(x, y, w, h, fill, radius=0, stroke='none'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def svg(w, h, title, body, css=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title, quote=True)}">'
            f'<title>{escape(title)}</title><style>{css}@media(prefers-reduced-motion:reduce){{*{{animation:none!important}}}}</style>{body}</svg>\n')


def header(t):
    b = rect(1, 1, 898, 378, t['panel'], 22, t['line'])
    b += text(32, 40, 'AT / ASHUARMADA', t['ink'], 13, 700, True)
    b += '<circle cx="690" cy="35" r="4" fill="'+t['accent']+'"/>'
    b += text(705, 40, 'OPEN TO COLLAB', t['accent'], 12, 400, True)
    b += f'<path d="M32 60H868" stroke="{t["line"]}"/>'
    b += text(32, 99, 'FULL-STACK DEVELOPER  /  AI & ML', t['dim'], 12, 400, True)
    b += text(28, 164, 'Ashutosh', t['ink'], 66, 700, extra='letter-spacing="-3"')
    b += text(28, 231, 'Thakur.', t['ink'], 66, 700, extra='letter-spacing="-3"')
    b += text(32, 277, 'Turning complex ideas', t['dim'], 22)
    b += text(32, 307, 'into tools that just work.', t['ink'], 22)
    # A wireframe orbital mark: native vector art, no external image dependencies.
    b += f'<g transform="translate(718 202)" fill="none" stroke="{t["line"]}">'
    b += '<circle r="108"/><circle r="80" stroke-dasharray="2 7"/><path d="M-132 0H132M0-132V132"/>'
    b += f'<g class="orbit" stroke="{t["accent"]}" stroke-width="1.4">'
    for angle in (0, 60, 120):
        b += f'<ellipse rx="108" ry="37" transform="rotate({angle})"/>'
    b += f'</g><circle r="29" fill="{t["panel"]}" stroke="{t["blue"]}" stroke-width="2"/></g>'
    b += text(700, 210, '</>', t['blue'], 22, 700, True)
    b += f'<circle cx="718" cy="94" r="5" fill="{t["accent"]}"/>'
    b += text(32, 353, 'PYTHON + JAVASCRIPT', t['accent'], 12, 400, True)
    b += text(615, 353, 'BUILD / EXPERIMENT / REPEAT', t['dim'], 11, 400, True)
    return svg(900, 380, 'Ashutosh Thakur. Full-stack developer / AI & ML. Open to collaboration.', b,
               '@keyframes orbit{to{transform:rotate(360deg)}}.orbit{animation:orbit 60s linear infinite}')


PROJECT_START = '<!-- PROJECTS:START -->'
PROJECT_END = '<!-- PROJECTS:END -->'


def project(t, p, number):
    name = p['name']
    accent = t['cards'][int(p['id']) % len(t['cards'])]
    wash = f'card-wash-{int(p["id"])}'
    description = p.get('description') or 'Explore the code and project details on GitHub.'
    names = textwrap.wrap(name, width=32, max_lines=2, placeholder='...')
    lines = textwrap.wrap(description, width=49, max_lines=2, placeholder='...')
    status = 'ARCHIVED' if p.get('archived') else ('FORK' if p.get('fork') else 'PUBLIC REPOSITORY')
    b = f'<defs><linearGradient id="{wash}" x2="1" y2="1"><stop stop-color="{accent}" stop-opacity=".16"/><stop offset="1" stop-color="{accent}" stop-opacity=".02"/></linearGradient></defs>'
    b += rect(1, 1, 438, 231, t['panel'], 14, t['line'])
    b += rect(1, 1, 438, 231, f'url(#{wash})', 14)
    b += rect(24, 1, 88, 4, accent, 2)
    b += f'<path d="M350 16h64v64M366 16v48h48" fill="none" stroke="{accent}" stroke-opacity=".12"/>'
    b += text(24, 34, f'{number:02d} / {status}', t['dim'], 11, 400, True)
    b += text(401, 36, '\u2197', accent, 24)
    for i, line in enumerate(names):
        b += text(24, 72+i*24, line, accent, 19, 700, True)
    for i, line in enumerate(lines):
        b += text(24, 124+i*19, line, t['dim'], 12, mono=True)
    b += f'<path d="M24 184H416" stroke="{t["line"]}"/>'
    b += text(24, 211, (p.get('language') or 'CODE / EXPERIMENTS')[:40], accent, 12, 400, True)
    return svg(440, 232, f'{name}: {description}', b)


def project_gallery(projects):
    cards = []
    for p in projects:
        # GitHub's numeric repository ID survives renames and is safe in filenames.
        stem = f'assets/project-{int(p["id"])}'
        url = escape(p['url'], quote=True)
        alt = escape(f'{p["name"]}: {p.get("description") or "View repository on GitHub."}', quote=True)
        cards.append(f'<a href="{url}"><picture><source media="(prefers-color-scheme: dark)" '
                     f'srcset="{stem}-dark.svg" /><img src="{stem}-light.svg" width="49%" '
                     f'alt="{alt}" /></picture></a>')
    return '\n'.join(cards) if cards else 'No public repositories with a README to show yet.'


def updated_readme(projects):
    path = OUT.parent / 'README.md'
    content = path.read_text(encoding='utf-8')
    if content.count(PROJECT_START) != 1 or content.count(PROJECT_END) != 1:
        raise ValueError('README must contain exactly one PROJECTS:START / PROJECTS:END block')
    before, rest = content.split(PROJECT_START)
    _, after = rest.split(PROJECT_END)
    content = before + PROJECT_START + '\n' + project_gallery(projects) + '\n' + PROJECT_END + after
    start, end = '<!-- CONTRIBUTIONS:START -->', '<!-- CONTRIBUTIONS:END -->'
    if start in content or end in content:
        if content.count(start) != 1 or content.count(end) != 1:
            raise ValueError('README contribution markers must appear exactly once')
        before, rest = content.split(start)
        _, after = rest.split(end)
        links = [f'<a href="{escape(p["url"], quote=True)}">{escape(p["repo"])} #{p["number"]}</a>'
                 for p in DATA.get('contributions', {}).get('items', [])]
        content = before + start + '\n' + ' ? '.join(links) + '\n' + end + after
    return path, content


def activity(t):
    commits = DATA.get('commits', [])
    # Show the newest entries first, keeping long repository names/messages bounded.
    recent = list(reversed(commits))[:5]
    h = 107 + max(len(recent), 1)*48
    b = rect(1, 1, 898, h-2, t['panel'], 16, t['line'])
    b += text(26, 36, 'THE BUILD LOG', t['ink'], 14, 700, True)
    b += text(620, 36, 'SNAPSHOT / '+DATA['fetched'], t['dim'], 12, 400, True)
    b += f'<path d="M26 56H874" stroke="{t["line"]}"/>'
    for i, c in enumerate(recent):
        y = 89+i*48
        if i < len(recent)-1:
            b += f'<path d="M34 {y}v48" stroke="{t["line"]}" stroke-width="2"/>'
        b += f'<circle cx="34" cy="{y-4}" r="5" fill="{t["accent"] if i == 0 else t["blue"]}"/>'
        b += text(55, y, c['repo'][:24], t['ink'], 13, 700, True)
        message = c['message']
        if len(message) > 49:
            message = message[:46]+'...'
        b += text(275, y, message, t['dim'], 13)
        b += text(803, y, c['sha'][:7], t['blue'], 12, 400, True)
    if not recent:
        b += text(26, 94, 'No recent commits in this snapshot.', t['dim'])
    b += text(26, h-22, 'GITHUB API  /  Latest commits across public repositories', t['dim'], 11, 400, True)
    return svg(900, h, 'Recent GitHub commits. Snapshot from '+DATA['fetched'], b)


def contributions(t):
    data = DATA.get('contributions')
    items = data['items'] if data else []
    h = 128 + max(len(items), 1) * 76
    b = rect(1, 1, 898, h-2, t['panel'], 16, t['line'])
    b += rect(26, 1, 140, 4, t['cards'][2], 2)
    b += text(26, 38, 'BEYOND MY REPOSITORIES', t['cards'][2], 15, 700, True)
    label = f'{data["total"]} PUBLIC PULL REQUESTS' if data else 'AWAITING FIRST REFRESH'
    b += text(874, 38, label, t['dim'], 12, mono=True, extra='text-anchor="end"')
    b += f'<path d="M26 60H874" stroke="{t["line"]}"/>'
    for i, item in enumerate(items):
        y = 98 + i * 76
        color = {'merged': t['cards'][5], 'open': t['cards'][1], 'closed': t['cards'][2]}[item['state']]
        title = textwrap.shorten(item['title'], width=70, placeholder='...')
        repo = item['repo']
        if len(repo) > 69:
            repo = repo[:66] + '...'
        b += text(26, y, title, t['ink'], 14, 700, True)
        b += text(26, y+24, f'{repo} / #{item["number"]}', t['dim'], 12, mono=True)
        b += rect(776, y-19, 98, 28, t['panel'], 14, color)
        b += text(825, y, item['state'].upper(), color, 11, 700, True, extra='text-anchor="middle"')
        if i < len(items)-1:
            b += f'<path d="M26 {y+42}H874" stroke="{t["line"]}"/>'
    if not items:
        message = 'No public pull requests to other repositories found yet.' if data else 'Contribution data will appear after a successful refresh.'
        b += text(26, 105, message, t['ink'], 19)
        b += text(26, 137, 'A place for fixes, ideas, and collaboration beyond my own projects.', t['dim'], 14)
    b += text(26, h-24, 'RECENTLY UPDATED / External pull requests authored by me', t['dim'], 11, mono=True)
    b += text(874, h-24, DATA['fetched'], t['dim'], 11, mono=True, extra='text-anchor="end"')
    return svg(900, h, 'Cross-repository contributions: public pull requests to other owners. ' + label, b)


def langs(t):
    ranked = sorted(DATA.get('languages', {}).items(), key=lambda p: p[1], reverse=True)
    total = sum(v for _, v in ranked) or 1
    top = ranked[:4]
    if len(ranked) > 4:
        top.append(('Other', sum(v for _, v in ranked[4:])))
    b = text(2, 28, 'A toolkit for the whole stack.', t['ink'], 25, 700)
    b += text(0, 57, f'{DATA["user"]["repos"]} public repositories / {len(ranked)} languages', t['dim'], 13, 400, True)
    colors = [t['accent'], t['blue'], t['ink'], t['dim'], t['line']]
    x = 0
    for i, (name, val) in enumerate(top):
        w = 900*val/total
        b += rect(round(x, 3), 82, round(w, 3), 9, colors[i])
        x += w
        lx = i*180
        b += rect(lx, 112, 7, 7, colors[i], 2)
        b += text(lx+15, 120, name, t['ink'], 13)
        b += text(lx+15, 143, f'{val/total:.1%}', t['dim'], 12, 400, True)
    return svg(900, 162, 'Language breakdown by source bytes: '+', '.join(f'{k} {v/total:.1%}' for k,v in top), b)


def footer(t):
    b = rect(1, 1, 898, 136, t['panel'], 16, t['line'])
    b += text(26, 44, 'Connect with me', t['ink'], 25, 700)
    b += text(26, 76, 'Let\u2019s build it together.', t['dim'], 17)
    b += text(26, 110, 'thakurashutosh042003@gmail.com', t['accent'], 17, mono=True)
    b += text(824, 84, '\u2197', t['accent'], 45)
    return svg(900, 138, 'Connect with me: thakurashutosh042003@gmail.com', b)


def chip(t, label):
    w = max(130, len(label) * 8 + 58)
    b = rect(1, 1, w-2, 36, t['panel'], 8, t['line'])
    b += text(15, 25, label, t['ink'], 13, 700, True)
    b += text(w-29, 25, '\u2197', t['accent'], 17)
    return svg(w, 38, label, b)


def build():
    builders = dict(header=header, activity=activity, langs=langs, footer=footer, contributions=contributions)
    builders['chip-email'] = lambda t: chip(t, 'thakurashutosh042003@gmail.com')
    builders['chip-linkedin'] = lambda t: chip(t, 'LinkedIn')
    if 'projects' not in DATA:
        raise ValueError('Repository metadata is missing. Run python assets/fetch.py first.')
    if any('has_readme' not in p for p in DATA['projects']):
        raise ValueError('README metadata is missing. Run python assets/fetch.py first.')
    projects = sorted((p for p in DATA['projects'] if p['has_readme']),
                      key=lambda p: p['name'].casefold())
    readme_path, readme = updated_readme(projects)
    for number, p in enumerate(projects, 1):
        builders[f'project-{int(p["id"])}'] = lambda t, p=p, n=number: project(t, p, n)
    for theme, tokens in THEMES.items():
        for name, builder in builders.items():
            (OUT/f'{name}-{theme}.svg').write_text(builder(tokens), encoding='utf-8')
        print(f'{theme}: generated {len(builders)} assets')
    readme_path.write_text(readme, encoding='utf-8')
    expected = {f'{name}-{theme}.svg' for name in builders for theme in THEMES}
    for old in OUT.glob('project-*.svg'):
        if old.name not in expected:
            old.unlink()
    print(f'Updated README with {len(projects)} project cards')


if __name__ == '__main__':
    build()
