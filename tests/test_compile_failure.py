"""Keep build failures visible without hiding their exit status or unsafe log text."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from report_compile_failure import annotation, error_summary


class CompileFailureTests(unittest.TestCase):
    def test_selects_compiler_error_among_build_noise(self):
        summary = error_summary(['compile 1\n', 'foo.c: fatal error: missing.h\n', 'compile 2\n',
                                 'make: *** [package/foo/compile] Error 2\n'])
        self.assertIn('missing.h', summary)
        self.assertIn('package/foo/compile', summary)
        self.assertNotIn('compile 1', summary)

    def test_bounds_large_failure_output(self):
        summary = error_summary(['error: ' + 'x' * 1000 + '\n'] * 10000)
        self.assertLessEqual(len(summary), 6000)

    def test_escapes_log_text_as_annotation_data(self):
        value = annotation('error 100%\n::notice::example\r')
        self.assertNotIn('\n', value)
        self.assertIn('100%25%0A', value)
        self.assertIn('%0D', value)

    def test_tee_does_not_mask_failed_compile(self):
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c',
                                 'if ! (exit 2) | tee /dev/null; then (exit 3) | tee -a /dev/null; fi'],
                                capture_output=True)
        self.assertEqual(result.returncode, 3)


if __name__ == '__main__':
    unittest.main()
