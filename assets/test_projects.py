"""Offline checks for repository discovery and generated gallery updates."""
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
    def test_readme_detection_and_api_failures(self):
        fetch = module('fetch')
        for name in ('README.md', 'readme.rst', 'README'):
            with patch.object(fetch, 'api', return_value={'name': name}):
                self.assertTrue(fetch.has_readme('example', 'project'))
        for status in (404, 403, 429, 500):
            error = urllib.error.HTTPError('https://api.github.com', status, 'error', {}, None)
            with patch.object(fetch, 'api', side_effect=error):
                if status == 404:
                    self.assertFalse(fetch.has_readme('example', 'project'))
                else:
                    with self.assertRaises(urllib.error.HTTPError):
                        fetch.has_readme('example', 'project')

    def test_readme_api_failure_preserves_gallery_metadata(self):
        fetch = module('fetch')
        repo = {'name': 'project', 'languages_url': 'languages', 'pushed_at': '2026-01-01'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.json'
            cached = json.dumps({'fetched': '2026-01-01', 'projects': [{'id': 1, 'has_readme': True}]})
            path.write_text(cached, encoding='utf-8')
            with patch.object(fetch, 'DATA', path), patch.object(fetch, 'fetch_repositories', return_value=[repo]), patch.object(fetch, 'has_readme', side_effect=OSError('timeout')), patch.object(fetch, 'api', side_effect=[{}, []]):
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
            with patch.object(fetch, 'DATA', path), patch.object(fetch, 'api', side_effect=OSError('offline')):
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
