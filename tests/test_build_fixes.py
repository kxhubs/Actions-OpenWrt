"""Exercise the upstream failures without downloading firmware dependencies."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import apply_build_fixes as fixes

SMARTDNS = '''PKG_NAME:=smartdns
PKG_VERSION:=48.5-RC1
PKG_RELEASE:=2
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/pymumu/smartdns/tar.gz/Release$(PKG_VERSION)?
PKG_HASH:=unchanged
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-Release$(PKG_VERSION)
MAKE_VARS+= VER=$(PKG_VERSION)
'''


class BuildFixTests(unittest.TestCase):
    def test_smartdns_metadata_changes_but_source_inputs_stay_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / 'feeds/kenzo/smartdns/Makefile'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(SMARTDNS)

            def values():
                result = subprocess.run(['make', '--no-print-directory', '-f', str(recipe),
                                         '-f', '-', 'print'], input='''
print:
	@printf '%s\\n' '$(PKG_VERSION)-r$(PKG_RELEASE)' '$(PKG_SOURCE)' '$(PKG_SOURCE_URL)' '$(PKG_BUILD_DIR)' '$(MAKE_VARS)' '$(PKG_HASH)'
''', capture_output=True, text=True, check=True)
                return result.stdout.splitlines()

            before = values()
            fixes.fix_smartdns(root)
            after = values()
            self.assertEqual(after[0], '48.5_rc1-r2')
            self.assertEqual(after[1:], before[1:])
            first = recipe.read_text()
            fixes.fix_smartdns(root)
            self.assertEqual(recipe.read_text(), first)

    def test_smartdns_changed_recipe_is_left_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / 'feeds/kenzo/smartdns/Makefile'
            recipe.parent.mkdir(parents=True)
            original = SMARTDNS + 'EXTRA_VERSION=$(PKG_VERSION)\n'
            recipe.write_text(original)
            with self.assertRaisesRegex(ValueError, 'recipe changed'):
                fixes.fix_smartdns(root)
            self.assertEqual(recipe.read_text(), original)

    def test_new_smartdns_version_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe = root / 'feeds/kenzo/smartdns/Makefile'
            recipe.parent.mkdir(parents=True)
            original = SMARTDNS.replace('48.5-RC1', '49')
            recipe.write_text(original)
            fixes.fix_smartdns(root)
            self.assertEqual(recipe.read_text(), original)

    def test_rockchip_only_removes_known_duplicate_on_affected_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version = root / 'target/linux/generic/kernel-6.12'
            version.parent.mkdir(parents=True)
            backports = []
            digests = {}
            for name in fixes.ROCKCHIP_PATCHES:
                backport = root / fixes.ROCKCHIP_PATCH_DIR / name
                backport.parent.mkdir(parents=True, exist_ok=True)
                backport.write_text('known duplicate ' + name)
                backports.append(backport)
                digests[name] = hashlib.sha256(backport.read_bytes()).hexdigest()
            with patch.object(fixes, 'ROCKCHIP_PATCHES', digests):
                version.write_text('LINUX_VERSION-6.12 = .115\n')
                fixes.fix_rockchip(root)
                self.assertTrue(all(p.exists() for p in backports))
                version.write_text('LINUX_VERSION-6.12 = .116\n')
                fixes.fix_rockchip(root)
                self.assertFalse(any(p.exists() for p in backports))
                fixes.fix_rockchip(root)

    def test_unknown_rockchip_patch_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version = root / 'target/linux/generic/kernel-6.12'
            version.parent.mkdir(parents=True)
            version.write_text('LINUX_VERSION-6.12 = .116\n')
            backports = []
            digests = {}
            for name in fixes.ROCKCHIP_PATCHES:
                backport = root / fixes.ROCKCHIP_PATCH_DIR / name
                backport.parent.mkdir(parents=True, exist_ok=True)
                backport.write_text('known duplicate')
                backports.append(backport)
                digests[name] = hashlib.sha256(backport.read_bytes()).hexdigest()
            backports[-1].write_text('changed upstream patch')
            with patch.object(fixes, 'ROCKCHIP_PATCHES', digests):
                with self.assertRaisesRegex(ValueError, 'Rockchip patch changed'):
                    fixes.fix_rockchip(root)
            self.assertTrue(all(p.exists() for p in backports))
            self.assertEqual(backports[-1].read_text(), 'changed upstream patch')


if __name__ == '__main__':
    unittest.main()
