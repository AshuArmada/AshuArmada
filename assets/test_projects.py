"""Offline checks for repository discovery and generated gallery updates."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class GalleryTests(unittest.TestCase):
    def test_external_contributions_statuses_and_scope(self):
        from urllib.parse import parse_qs, urlparse
        fetch = module('fetch')
        items = [dict(repository_url='https://api.github.com/repos/other/project', number=i,
                      title='Fix & improve', html_url=f'https://github.com/other/project/pull/{i}',
                      state=state, pull_request=pull)
                 for i, (state, pull) in enumerate([
                     ('open', {'merged_at': None}),
                     ('closed', {'merged_at': '2026-01-01'}),
                     ('closed', {'url': 'https://api.github.com/repos/other/project/pulls/2'}),
                 ], 1)]
        with patch.object(fetch, 'api', side_effect=[{'total_count': 3, 'items': items}, {'merged_at': None}]) as api:
            result = fetch.fetch_contributions('example')
        self.assertEqual([p['state'] for p in result['items']], ['open', 'merged', 'closed'])
        query = parse_qs(urlparse(api.call_args_list[0].args[0]).query)['q'][0]
        self.assertIn('author:example', query)
        self.assertIn('-user:example', query)
        self.assertIn('is:public', query)
        self.assertEqual(result['total'], 3)
        with patch.object(fetch, 'api', return_value={'incomplete_results': True}):
            with self.assertRaises(ValueError):
                fetch.fetch_contributions('example')

    def test_contribution_empty_and_populated_rendering(self):
        gen = module('generate')
        for snapshot in (None, {'total': 0, 'items': []}, {'total': 1, 'items': [
                {'repo': 'other/project', 'number': 1, 'title': 'Fix <bug>', 'state': 'merged',
                 'url': 'https://github.com/other/project/pull/1'}]}):
            with patch.object(gen, 'DATA', {**gen.DATA, 'contributions': snapshot}):
                for theme in gen.THEMES.values():
                    output = gen.contributions(theme)
                    ET.fromstring(output)
                    if snapshot is None:
                        self.assertIn('AWAITING FIRST REFRESH', output)
                    elif snapshot['total']:
                        self.assertIn('MERGED', output)
                        self.assertIn('Fix &lt;bug&gt;', output)
                    else:
                        self.assertIn('No public pull requests', output)

    def test_readme_excerpt_skips_decoration(self):
        fetch = module('fetch')
        markdown = '\n'.join([
            '# Project', '[![Build](badge.svg)](https://example.com)',
            '<!-- hidden -->', '<picture><img src="hero.svg"></picture>',
            '```python', 'print("ignore")', '```', 'Overview', '--------',
            '**Build** tools with [Python](https://python.org).',
            'Works with `Git` &amp; automation.', 'Do not include this third line.',
        ])
        self.assertEqual(fetch.readme_excerpt(markdown),
                         'Build tools with Python. Works with Git & automation.')
        self.assertEqual(fetch.readme_excerpt('# Title\n![Logo](logo.svg)'), '')
        self.assertEqual(fetch.readme_excerpt('Only one line.'), 'Only one line.')
        self.assertLessEqual(len(fetch.readme_excerpt('A long description. ' * 100)), 240)

    def test_readme_detection_and_api_failures(self):
        fetch = module('fetch')
        for name in ('README.md', 'readme.rst', 'README'):
            with patch.object(fetch, 'api', return_value={'name': name, 'encoding': 'base64', 'content': base64.b64encode(b'# Title\nFirst line.\nSecond line.').decode()}):
                self.assertEqual(fetch.readme_description('example', 'project'), 'First line. Second line.')
        for status in (404, 403, 429, 500):
            error = urllib.error.HTTPError('https://api.github.com', status, 'error', {}, None)
            with patch.object(fetch, 'api', side_effect=error):
                if status == 404:
                    self.assertIsNone(fetch.readme_description('example', 'project'))
                else:
                    with self.assertRaises(urllib.error.HTTPError):
                        fetch.readme_description('example', 'project')

    def test_refresh_saves_readme_excerpt_with_description_fallback(self):
        fetch = module('fetch')
        repos = [dict(id=i, name=f'project-{i}', html_url=f'https://github.com/example/project-{i}',
                      description='Repository fallback.', languages_url='languages', pushed_at='2026-01-01')
                 for i in range(3)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.json'
            with patch.object(fetch, 'fetch_contributions', return_value={'total': 0, 'items': []}), patch.object(fetch, 'DATA', path), patch.object(fetch, 'fetch_repositories', return_value=repos), patch.object(fetch, 'readme_description', side_effect=['README introduction.', '', None]), patch.object(fetch, 'api', side_effect=[{}, {}, {}, [], [], []]):
                fetch.main()
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual([p['description'] for p in data['projects']],
                             ['README introduction.', 'Repository fallback.'])
            self.assertEqual(data['user']['repos'], 3)

    def test_readme_api_failure_preserves_gallery_metadata(self):
        fetch = module('fetch')
        repo = {'name': 'project', 'languages_url': 'languages', 'pushed_at': '2026-01-01'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.json'
            cached = json.dumps({'fetched': '2026-01-01', 'projects': [{'id': 1, 'has_readme': True}]})
            path.write_text(cached, encoding='utf-8')
            with patch.object(fetch, 'fetch_contributions', return_value={'total': 0, 'items': []}), patch.object(fetch, 'DATA', path), patch.object(fetch, 'fetch_repositories', return_value=[repo]), patch.object(fetch, 'readme_description', side_effect=OSError('timeout')), patch.object(fetch, 'api', side_effect=[{}, []]):
                fetch.main()
            self.assertEqual(path.read_text(encoding='utf-8'), cached)

    def test_repository_pagination_includes_forks(self):
        fetch = module('fetch')
        first = [{'id': i, 'name': f'repo-{i}', 'fork': True} for i in range(100)]
        with patch.object(fetch, 'api', side_effect=[first, [{'id': 100, 'name': 'new-project'}]]) as api:
            repos = fetch.fetch_repositories('example')
        self.assertEqual(len(repos), 101)
        self.assertIn('page=2', api.call_args.args[0])

    def test_incomplete_fetch_preserves_cache(self):
        fetch = module('fetch')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.json'
            cached = json.dumps({'fetched': '2026-01-01', 'projects': [{'id': 1}]})
            path.write_text(cached, encoding='utf-8')
            with patch.object(fetch, 'fetch_contributions', return_value={'total': 0, 'items': []}), patch.object(fetch, 'DATA', path), patch.object(fetch, 'api', side_effect=OSError('offline')):
                fetch.main()
            self.assertEqual(path.read_text(encoding='utf-8'), cached)

    def test_gallery_addition_removal_and_idempotence(self):
        gen = module('generate')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            assets = root / 'assets'
            assets.mkdir()
            readme = root / 'README.md'
            readme.write_text('Intro\n<!-- PROJECTS:START -->\nold\n<!-- PROJECTS:END -->\nOutro', encoding='utf-8')
            data = {**gen.DATA, 'projects': [{'id': 1, 'name': 'first', 'has_readme': True, 'url': 'https://github.com/example/first'}]}
            with patch.object(gen, 'OUT', assets), patch.object(gen, 'DATA', data):
                gen.build()
                data['projects'].append({'id': 2, 'name': 'new-project', 'has_readme': False, 'url': 'https://github.com/example/new-project', 'description': '<hello> & "world" ' * 40})
                gen.build()
                self.assertNotIn('project-2-dark.svg', readme.read_text(encoding='utf-8'))
                data['projects'][1]['has_readme'] = True
                gen.build()
                content = readme.read_text(encoding='utf-8')
                self.assertIn('project-2-dark.svg', content)
                self.assertTrue(content.startswith('Intro\n'))
                self.assertTrue(content.endswith('\nOutro'))
                for file in assets.glob('*.svg'):
                    ET.parse(file)
                gen.build()
                self.assertEqual(content, readme.read_text(encoding='utf-8'))
                data['projects'][0]['has_readme'] = False
                data['projects'][1]['has_readme'] = False
                gen.build()
                self.assertFalse(list(assets.glob('project-*.svg')))
                self.assertIn('No public repositories', readme.read_text(encoding='utf-8'))

    def test_missing_markers_fail_without_writing(self):
        gen = module('generate')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'assets').mkdir()
            readme = root / 'README.md'
            readme.write_text('Manual content', encoding='utf-8')
            with patch.object(gen, 'OUT', root / 'assets'), patch.object(gen, 'DATA', {**gen.DATA, 'projects': []}):
                with self.assertRaises(ValueError):
                    gen.build()
            self.assertEqual(readme.read_text(encoding='utf-8'), 'Manual content')
            self.assertEqual(list((root / 'assets').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
