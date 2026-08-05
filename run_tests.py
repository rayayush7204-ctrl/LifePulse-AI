"""
CI Test Runner — Phase 1 Regression Guard
==========================================
Runs the full Phase 1 verification suite in sequence:
  1. E2E lifecycle test (CREATED -> CLOSED)
  2. Hardening suite (race condition, 4 concurrent emergencies, WS reconnect)

Usage:
  python -u backend/run_tests.py

Requirements:
  Backend must be running on port 8000:
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

Exit codes:
  0  — All tests passed
  1  — One or more tests failed
"""
import subprocess
import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

def run_test(label, script):
    print(f"\n{'='*60}")
    print(f"  RUNNING: {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-u", script],
        cwd=BACKEND_DIR,
    )
    return result.returncode == 0

def main():
    print("=" * 60)
    print("  LIFEPULSE CI — PHASE 1 REGRESSION GUARD")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\nNOTE: Backend must be running on port 8000 before invoking this runner.")

    results = {
        "E2E Lifecycle (CREATED -> CLOSED)":
            run_test("E2E Lifecycle", "e2e_test.py"),
        "Hardening Suite (race / concurrent / reconnect)":
            run_test("Hardening Suite", "test_concurrent.py"),
    }

    print(f"\n{'='*60}")
    print("  CI SUMMARY")
    print(f"{'='*60}")
    all_pass = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  RESULT: ALL PHASE 1 TESTS PASSED")
        print("  Phase 1 baseline is intact.")
    else:
        print("  RESULT: REGRESSION DETECTED")
        print("  Do not merge Phase 2 changes until all tests pass.")
    print("=" * 60)
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
