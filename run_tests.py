#!/usr/bin/env python3
"""
BeatVault - Automated Test Suite & Code Quality Shield
Discovers and executes all unit and integration tests under tests/ directory.
Produces formatted verbose output and returns appropriate exit codes (0 = Success, 1 = Failure).
"""

import os
import sys
import time
import unittest
from io import StringIO

# Ensure project root is at the head of sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class FormattedTestResult(unittest.TextTestResult):
    """Custom test result formatter providing clean colorized or symbol-coded console output."""

    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes = []
        self._test_start_time = None

    def startTest(self, test):
        super().startTest(test)
        self._test_start_time = time.perf_counter()

    def addSuccess(self, test):
        super().addSuccess(test)
        elapsed = (time.perf_counter() - self._test_start_time) * 1000
        self.successes.append((test, elapsed))
        if self.showAll:
            self.stream.writeln(f"  [PASS] {test._testMethodName} ({elapsed:.1f}ms)")
            self.stream.flush()

    def addFailure(self, test, err):
        super().addFailure(test, err)
        elapsed = (time.perf_counter() - self._test_start_time) * 1000
        if self.showAll:
            self.stream.writeln(f"  [FAIL] {test._testMethodName} ({elapsed:.1f}ms)")
            self.stream.flush()

    def addError(self, test, err):
        super().addError(test, err)
        elapsed = (time.perf_counter() - self._test_start_time) * 1000
        if self.showAll:
            self.stream.writeln(f"  [ERROR] {test._testMethodName} ({elapsed:.1f}ms)")
            self.stream.flush()

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.showAll:
            self.stream.writeln(f"  [SKIP] {test._testMethodName} - {reason}")
            self.stream.flush()


class FormattedTestRunner(unittest.TextTestRunner):
    """Test runner using FormattedTestResult."""
    resultclass = FormattedTestResult

    def run(self, test):
        print("=" * 75)
        print("          BEATVAULT AUTOMATED TEST SUITE & QUALITY SHIELD")
        print("=" * 75)
        print(f"Working Directory : {PROJECT_ROOT}")
        print(f"Python Version    : {sys.version.split()[0]}")
        print(f"Test Discovery Dir: {os.path.join(PROJECT_ROOT, 'tests')}")
        print("-" * 75)
        start_time = time.perf_counter()
        result = super().run(test)
        duration = time.perf_counter() - start_time

        print("\n" + "=" * 75)
        print("                             TEST SUMMARY")
        print("=" * 75)
        total = result.testsRun
        passed = len(getattr(result, "successes", []))
        failed = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)

        pass_rate = (passed / total * 100.0) if total > 0 else 0.0

        print(f" Total Tests Run : {total}")
        print(f" Passed          : {passed} ({pass_rate:.1f}%)")
        print(f" Failed          : {failed}")
        print(f" Errors          : {errors}")
        print(f" Skipped         : {skipped}")
        print(f" Total Duration  : {duration:.3f} seconds")
        print("-" * 75)

        if result.wasSuccessful():
            print(" [STATUS] ALL TESTS PASSED - CODE QUALITY SHIELD VERIFIED! [OK]")
        else:
            print(" [STATUS] TEST SUITE FAILED - PLEASE REVIEW ERRORS ABOVE. [FAIL]")
        print("=" * 75 + "\n")

        return result


def run_all_tests(pattern="test_*.py", verbosity=2):
    """Discovers all test files matching pattern and executes them."""
    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests_dir, pattern=pattern, top_level_dir=PROJECT_ROOT)

    runner = FormattedTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    pattern = "test_*.py"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        arg = sys.argv[1]
        pattern = f"*{arg}*.py" if not arg.endswith(".py") else arg

    exit_code = run_all_tests(pattern=pattern)
    sys.exit(exit_code)
