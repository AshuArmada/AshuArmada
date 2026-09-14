#!/usr/bin/env python3
"""
Pulls the real numbers and the real commit history into assets/data.json.

    python assets/fetch.py [username]

Unauthenticated GitHub allows 60 requests/hr and this makes roughly two per
repository, so throttled runs are normal. Anything short of a clean sweep keeps
the previous data.json rather than overwriting good data with a partial read.

Set GITHUB_TOKEN for a higher limit; .github/workflows/refresh.yml does.
"""

import base64
import collections
import re
import textwrap
from html import unescape
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).parent
DATA = OUT / "data.json"
USER = sys.argv[1] if len(sys.argv) > 1 else "AshuArmada"

LANES = 3      # recent repositories sampled for the build log
COMMITS = 5    # entries displayed by the build log


def api(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "profile-assets", "Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def tidy(message):
    """First line of a commit message, trimmed to something a lane can hold."""
    line = message.splitlines()[0].strip()
    return line if len(line) <= 44 else line[:43].rstrip() + "…"


def fetch_repositories(username):
    """Read every page so the gallery also works for accounts with 100+ repos."""
    repos, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{username}/repos?per_page=100&type=owner&page={page}")
        repos.extend(r for r in batch if not r.get("private"))
        if len(batch) < 100:
            return sorted(repos, key=lambda r: r["name"].casefold())
        page += 1


def readme_excerpt(markdown):
    """First two prose lines, with common Markdown/HTML decoration removed."""
    markdown = re.sub(r'<!--.*?-->', '', markdown, flags=re.S)
    markdown = re.sub(r'<(picture|svg|script|style|pre|h[1-6])\b[^>]*>.*?</\1>',
                      '', markdown, flags=re.S | re.I)
    source = markdown.splitlines()
    lines, fence = [], None
    for i, raw in enumerate(source):
        line = raw.strip()
        marker = re.match(r'^(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence or not line or raw.startswith(('    ', '\t')):
            continue
        if re.match(r'^(#{1,6}\s|[=*_~-]{3,}\s*$|\[[^]]+\]:|\|)', line):
            continue
        if i + 1 < len(source) and re.fullmatch(r'\s*[=-]+\s*', source[i+1]):
            continue
        line = re.sub(r'\[!\[[^]]*\]\([^)]*\)\]\([^)]*\)', '', line)
        line = re.sub(r'!\[[^]]*\](?:\([^)]*\)|\[[^]]*\])', '', line)
        line = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', line)
        line = re.sub(r'\[([^]]+)\]\[[^]]*\]', r'\1', line)
        line = re.sub(r'<[^>]+>', '', line)
        line = re.sub(r'^(?:>\s*|[-*+]\s+|\d+[.)]\s+)', '', line)
        line = unescape(re.sub(r'[*`~]', '', line))
        line = ' '.join(line.split())
        if line and re.search(r'\w', line):
            lines.append(line)
        if len(lines) == 2:
            break
    return textwrap.shorten(' '.join(lines), width=240, placeholder='...')


def readme_description(username, name):
    """None means no README; an empty string means a README without prose."""
    try:
        readme = api(f"https://api.github.com/repos/{username}/{name}/readme")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if readme.get('encoding') != 'base64':
        raise ValueError('GitHub did not return readable README content')
    content = base64.b64decode(readme['content']).decode('utf-8', errors='replace')
    return readme_excerpt(content)


def fetch_contributions(username):
    """Recently updated public PRs authored outside the user's repositories."""
    query = urlencode({'q': f'is:pr is:public author:{username} -user:{username}',
                       'sort': 'updated', 'order': 'desc', 'per_page': 6})
    result = api('https://api.github.com/search/issues?' + query)
    if result.get('incomplete_results'):
        raise ValueError('GitHub returned an incomplete contribution search')
    items = []
    for item in result['items']:
        repo = item['repository_url'].split('/repos/', 1)[1]
        if repo.split('/')[0].casefold() == username.casefold():
            continue
        pull = item['pull_request']
        # Search results may omit merged_at; resolve closed PRs when needed.
        if item['state'] == 'closed' and 'merged_at' not in pull:
            pull = api(pull['url'])
        state = 'merged' if pull.get('merged_at') else item['state']
        items.append({'repo': repo, 'number': item['number'], 'title': item['title'],
                      'url': item['html_url'], 'state': state})
    return {'total': result['total_count'], 'items': items}


def main():
    previous = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None
    failed = []

    try:
        repos = fetch_repositories(USER)
        contributions = fetch_contributions(USER)
    except (OSError, ValueError) as e:
        if not previous:
            raise SystemExit(f"cannot reach the GitHub API and no cached data.json: {e}")
        print(f"  ! {e} — keeping data.json from {previous['fetched']}", file=sys.stderr)
        return

    languages = collections.Counter()
    for r in repos:
        try:
            excerpt = readme_description(USER, r['name'])
            r['has_readme'] = excerpt is not None
            r['readme_description'] = excerpt or ''
        except (OSError, ValueError) as e:
            failed.append(f"{r['name']} README: {e}")
        try:
            languages.update(api(r["languages_url"]))
        except (OSError, ValueError) as e:
            failed.append(f"{r['name']} languages: {e}")

    # real commit history, walking repositories newest-push first until we have
    # enough lanes. A 409 just means the repository is empty, so skip past it.
    active = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)
    commits, lanes = [], 0
    for r in active:
        if lanes >= LANES:
            break
        try:
            found = api(f"https://api.github.com/repos/{USER}/{r['name']}/commits?per_page=3")
        except urllib.error.HTTPError as e:
            if e.code == 409:
                print(f"  · {r['name']} is empty, skipping", file=sys.stderr)
                continue
            failed.append(f"{r['name']} commits: {e}")
            continue
        except (OSError, ValueError) as e:
            failed.append(f"{r['name']} commits: {e}")
            continue
        if not found:
            continue
        lanes += 1
        for c in found:
            commits.append({
                "repo": r["name"],
                "sha": c["sha"][:7],
                "message": tidy(c["commit"]["message"]),
                "date": c["commit"]["author"]["date"],
            })

    if failed:
        for f in failed:
            print(f"  ! {f}", file=sys.stderr)
        if previous:
            print(f"  ! incomplete read — keeping data.json from {previous['fetched']}", file=sys.stderr)
            return
        raise SystemExit("incomplete read and no cached data.json to fall back on")

    commits.sort(key=lambda c: c["date"])
    commits = commits[-COMMITS:]

    DATA.write_text(json.dumps({
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "user": {"repos": len(repos)},
        "languages": dict(languages.most_common()),
        "projects": [{
            "id": r["id"], "name": r["name"], "url": r["html_url"],
            "description": r["readme_description"] or r.get("description") or "",
            "language": r.get("language") or "",
            "fork": bool(r.get("fork")), "archived": bool(r.get("archived")),
            "has_readme": r['has_readme'],
        } for r in repos if r['has_readme']],
        "commits": commits,
        "contributions": contributions,
    }, indent=1), encoding="utf-8")

    print(f"wrote data.json — {len(repos)} repos, {len(languages)} languages, "
          f"{len(commits)} commits across {len({c['repo'] for c in commits})} repos")


if __name__ == "__main__":
    main()
