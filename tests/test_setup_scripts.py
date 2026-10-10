"""Run router-script failure paths against fake services in a temporary directory."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class UpdateTests(unittest.TestCase):
    def run_update(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            etc = root / 'etc'
            (etc / 'init.d').mkdir(parents=True)
            (etc / 'config').mkdir()
            target = etc / 'config/smartdns'
            target.write_text('old configuration\n')
            tools = root / 'bin'
            tools.mkdir()
            commands = {
                'id': 'echo 0',
                'curl': 'while [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then shift; out=$1; fi; shift; done\nprintf "config smartdns\\n" > "$out"\n[ "$MODE" != download ]',
                'uci': '[ "$MODE" != invalid ] || exit 1\necho "config smartdns"',
                'jsonfilter': 'cat >/dev/null; echo true',
                'ubus': 'echo "{}"',
                'cp': '[ "$MODE" != backup ] || exit 1\nexec /bin/cp "$@"',
            }
            for name, body in commands.items():
                file = tools / name
                file.write_text('#!/bin/sh\n' + body + '\n')
                file.chmod(0o755)
            service = etc / 'init.d/smartdns'
            service.write_text('#!/bin/sh\n' + f'echo restart >> "{root}/restarts"\n' + '[ "$MODE" != restart ]\n')
            service.chmod(0o755)
            script = (REPO / 'scripts/update_config.sh').read_text()
            script = script.replace('/tmp/', directory + '/').replace('/etc/', str(etc) + '/')
            local = root / 'update.sh'
            local.write_text(script)
            result = subprocess.run(['sh', str(local)], env={**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'], 'MODE': mode}, capture_output=True, text=True)
            restarts = (root / 'restarts').read_text().splitlines() if (root / 'restarts').exists() else []
            return result, target.read_text(), restarts, list((etc / 'config').glob('*.update.*'))

    def test_success(self):
        result, content, restarts, pending = self.run_update('success')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(content, 'config smartdns\n')
        self.assertEqual(len(restarts), 1)
        self.assertFalse(pending)

    def test_failed_download_keeps_original(self):
        result, content, restarts, _ = self.run_update('download')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content, 'old configuration\n')
        self.assertEqual(restarts, [])

    def test_invalid_config_keeps_original(self):
        result, content, restarts, _ = self.run_update('invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content, 'old configuration\n')
        self.assertEqual(restarts, [])

    def test_backup_failure_keeps_original(self):
        result, content, restarts, _ = self.run_update('backup')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content, 'old configuration\n')
        self.assertEqual(restarts, [])

    def test_failed_restart_restores_and_restarts(self):
        result, content, restarts, pending = self.run_update('restart')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(content, 'old configuration\n')
        self.assertEqual(len(restarts), 2)
        self.assertFalse(pending)


class CustomizationTests(unittest.TestCase):
    def test_customization_handles_multiple_collections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                '.config': 'CONFIG_VERSION_REPO="https://downloads.openwrt.org/releases/25.12"\nCONFIG_FEED_kenzo=y\n',
                'feeds/luci/collections/luci/Makefile': 'DEPENDS:=luci-theme-bootstrap\n',
                'feeds/luci/collections/other/Makefile': 'unchanged\n',
                'package/base-files/files/bin/config_generate': "ipaddr='192.168.1.1'\n",
                'feeds/luci/modules/luci-mod-system/flash.js': '192.168.1.1\n',
                'feeds/luci/modules/luci-mod-status/htdocs/luci-static/resources/view/status/include/10_system.js': "(luciversion || '')\n",
            }
            for name, content in files.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
            (root / 'package/luci-theme-aurora').mkdir()
            subprocess.run(['bash', str(REPO / 'scripts/diy-part2.sh')], cwd=root, check=True)
            self.assertIn('luci-theme-aurora', (root / 'feeds/luci/collections/luci/Makefile').read_text())
            self.assertEqual((root / 'feeds/luci/collections/other/Makefile').read_text(), 'unchanged\n')
            self.assertNotIn('CONFIG_VERSION_REPO=', (root / '.config').read_text())
            self.assertNotIn('CONFIG_FEED_kenzo=y', (root / '.config').read_text())
            self.assertIn('192.168.1.2', (root / 'package/base-files/files/bin/config_generate').read_text())


if __name__ == '__main__':
    unittest.main()
