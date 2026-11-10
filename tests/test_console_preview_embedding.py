from __future__ import annotations
import copy
import json
import shutil
import socket
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
import yaml
from packages.prototype_preview.runtime import PreviewError, PreviewRuntime, _embedding_origins, _preview_security_headers, _validate, _validator, PROFILE_SCHEMA

ROOT = Path(__file__).resolve().parents[1]

class PreviewEmbeddingTests(unittest.TestCase):
    def test_default_stays_denied_and_opt_in_does_not_relax_other_headers(self):
        denied = _preview_security_headers({})
        self.assertEqual(denied['X-Frame-Options'], 'DENY')
        self.assertIn("frame-ancestors 'none'", denied['Content-Security-Policy'])
        allowed = _preview_security_headers({'embedding': {'allowed_origins': ['http://localhost:4317', 'http://127.0.0.1:4317']}})
        self.assertNotIn('X-Frame-Options', allowed)
        self.assertIn('frame-ancestors http://localhost:4317 http://127.0.0.1:4317', allowed['Content-Security-Policy'])
        for directive in ["connect-src 'none'", "form-action 'none'", "worker-src 'none'", "object-src 'none'"]:
            self.assertIn(directive, allowed['Content-Security-Policy'])

    def test_origin_admission_rejects_scope_expansion_and_header_injection(self):
        profile = yaml.safe_load((ROOT / 'records/prototype-preview-profiles/client-review-portal.yaml').read_text())
        validator = _validator(ROOT, PROFILE_SCHEMA)
        for origin in ['https://example.com', 'http://localhost:*', 'http://localhost:4317/path', 'http://user@localhost:4317', 'http://localhost:4317?x=y', 'http://localhost:80', 'http://localhost:99999', 'http://localhost:4317\n', 'http://localhost:4317\r\nX-Test: yes', 'http://localhost.evil:4317']:
            with self.subTest(origin=origin), self.assertRaises(PreviewError):
                candidate = copy.deepcopy(profile); candidate['embedding'] = {'allowed_origins': [origin]}
                _validate(validator, candidate, 'profile'); _embedding_origins(candidate)
        for origins in [['http://localhost:4317'] * 2, [f'http://localhost:{4317+i}' for i in range(9)]]:
            with self.assertRaises(PreviewError):
                _validate(validator, {**profile, 'embedding': {'allowed_origins': origins}}, 'profile')

    def test_native_http_uses_exact_profile_origins_and_reports_source_binding(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as state:
            root = Path(folder)
            for name in ['schemas', 'packages/prototype_preview']:
                shutil.copytree(ROOT / name, root / name)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/prototype_preview.py', root / 'scripts/prototype_preview.py')
            shutil.copyfile(ROOT / 'prototypes.yaml', root / 'prototypes.yaml')
            (root / '.gitignore').write_text('__pycache__/\n*.pyc\n')
            profile = yaml.safe_load((ROOT / 'records/prototype-preview-profiles/client-review-portal.yaml').read_text())
            source = root / profile['runtime']['source_root']; source.mkdir(parents=True)
            (source / 'index.html').write_text('<!doctype html><title>Isolated preview</title><h1>Preview</h1>')
            profile['embedding'] = {'allowed_origins': ['http://localhost:4317']}
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0)); profile['runtime']['port'] = probe.getsockname()[1]
            path = root / 'records/prototype-preview-profiles/client-review-portal.yaml'; path.parent.mkdir(parents=True); path.write_text(yaml.safe_dump(profile))
            def git(*args): return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            git('init', '-q'); git('config', 'user.name', 'Agent Gary'); git('config', 'user.email', '327854141+mfshaf7-agent-gary[bot]@users.noreply.github.com'); git('add', '.'); git('commit', '-qm', 'Create isolated Preview Runtime test fixture')
            runtime = PreviewRuntime(root, path, Path(state))
            def expected(): return {key: runtime.projection()[key] for key in ['instance_id','profile_digest','runtime_state','source_digest','source_revision']}
            try:
                runtime.command('start', 'embedding-native-start', expected())
                projection = runtime.projection()
                self.assertEqual(projection['embedding'], profile['embedding'])
                self.assertEqual(projection['source_revision'], git('rev-parse','HEAD').stdout.decode().strip())
                with urllib.request.urlopen(projection['endpoint'], timeout=3) as response:
                    self.assertIn(b'Isolated preview', response.read())
                    self.assertIsNone(response.headers.get('X-Frame-Options'))
                    self.assertIn('frame-ancestors http://localhost:4317', response.headers['Content-Security-Policy'])
            finally:
                if runtime.projection()['runtime_state'] == 'running': runtime.command('stop', 'embedding-native-stop', expected())
