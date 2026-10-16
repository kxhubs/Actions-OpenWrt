"""Exercise dependency locking and cache isolation without network access."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_inputs
import ci_cache


class SourceLockTests(unittest.TestCase):
    def setUp(self):
        self.sources = json.loads((ROOT / 'config/build-sources.json').read_text())
        self.lock = {'schema': 1, **{
            group: {name: {**spec, 'commit': 'a' * 40} for name, spec in entries.items()}
            for group, entries in self.sources.items()
        }}

    def test_rejects_changed_url_branch_missing_feed_and_invalid_commit(self):
        for field, value in [('url', 'https://github.com/attacker/feed.git'),
                             ('ref', 'unreviewed'), ('commit', '--upload-pack=bad')]:
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock['feeds']['packages'][field] = value
                with self.assertRaises(ValueError):
                    build_inputs.validate_lock(lock, self.sources)
        del self.lock['feeds']['packages']
        with self.assertRaises(ValueError):
            build_inputs.validate_lock(self.lock, self.sources)

    def test_fingerprint_covers_feeds_and_is_independent_of_key_order(self):
        original = build_inputs.fingerprint(self.lock)
        reordered = dict(reversed(list(self.lock.items())))
        self.assertEqual(original, build_inputs.fingerprint(reordered))
        self.lock['feeds']['packages']['commit'] = 'b' * 40
        self.assertNotEqual(original, build_inputs.fingerprint(self.lock))

    def test_dispatch_reuses_validated_versions_without_remote_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / 'event.json'
            output = Path(directory) / 'lock.json'
            event.write_text(json.dumps({'client_payload': {'lock': self.lock}}))
            args = ['build_inputs.py', 'resolve', '--event', str(event), '--output', str(output)]
            with patch.object(sys, 'argv', args), patch.object(build_inputs, 'resolve') as resolve:
                build_inputs.main()
                resolve.assert_not_called()
            self.assertEqual(json.loads(output.read_text()), self.lock)

    def test_checkout_uses_exact_commit_and_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / 'repository'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            env = {**os.environ, 'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.com',
                   'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.com'}
            (repo / 'file').write_text('first')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'first'], check=True, env=env)
            first = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            (repo / 'file').write_text('second')
            subprocess.run(['git', '-C', str(repo), 'commit', '-qam', 'second'], check=True, env=env)
            target = Path(directory) / 'checkout'
            build_inputs.checkout({'url': repo.as_uri(), 'commit': first}, target)
            self.assertEqual((target / 'file').read_text(), 'first')
            with self.assertRaises(ValueError):
                build_inputs.checkout({'url': repo.as_uri(), 'commit': first}, target)


class CacheTests(unittest.TestCase):
    def test_configuration_preserves_packages_and_replaces_cache_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / '.config'
            config.write_text('CONFIG_PACKAGE_xray-core=y\n# CONFIG_CCACHE is not set\nCONFIG_CCACHE_DIR="old"\n')
            cache = root / 'cache'
            ci_cache.configure(root, cache)
            first = config.read_text()
            ci_cache.configure(root, cache)
            self.assertEqual(first, config.read_text())
            self.assertIn('CONFIG_PACKAGE_xray-core=y\n', first)
            self.assertIn('CONFIG_DEVEL=y\n', first)
            self.assertIn('CONFIG_CCACHE=y\n', first)
            self.assertNotIn('"old"', first)

    def test_download_eviction_removes_whole_module_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modules = root / 'go-mod-cache'
            modules.mkdir()
            for name in ('a', 'b'):
                p = modules / name
                p.write_bytes(b'x' * 4)
                os.utime(p, (10, 10))
            recent = root / 'source.tar.gz'
            recent.write_bytes(b'y' * 4)
            ci_cache.trim(root, 5, whole_entries=True)
            self.assertFalse(modules.exists())
            self.assertTrue(recent.exists())

    def test_trimming_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / 'keep'
            outside.write_bytes(b'unchanged')
            cache = root / 'cache'
            cache.mkdir()
            (cache / 'link').symlink_to(outside)
            (cache / 'regular').write_bytes(b'evict')
            ci_cache.trim(cache, 0)
            self.assertEqual(outside.read_bytes(), b'unchanged')
            self.assertFalse((cache / 'regular').exists())

    def test_toolchain_or_configuration_change_invalidates_cache_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.config').write_text('CONFIG_TARGET_x86=y\n')
            rust = root / 'feeds/packages/lang/rust/Makefile'
            rust.parent.mkdir(parents=True)
            rust.write_text('PKG_VERSION:=1\n')
            lock = {'repositories': {'golang': {'commit': 'a' * 40}}}
            def command(args, **kwargs):
                return 'toolchain-v1' if args[0] == 'git' else '12.3.0'
            with patch.object(ci_cache.subprocess, 'check_output', side_effect=command):
                first = ci_cache.scope(root, lock)
                (root / '.config').write_text('CONFIG_TARGET_arm=y\n')
                self.assertNotEqual(first, ci_cache.scope(root, lock))
                (root / '.config').write_text('CONFIG_TARGET_x86=y\n')
                rust.write_text('PKG_VERSION:=2\n')
                self.assertNotEqual(first, ci_cache.scope(root, lock))


if __name__ == '__main__':
    unittest.main()
