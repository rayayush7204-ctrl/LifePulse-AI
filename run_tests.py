"""
CI Test Runner — Phase 1 Regression Guard
==========================================
Runs the full Phase 1 verification suite in sequence:
  0. Test fixture seed  (inserts deterministic test donors into the backend)
  1. E2E lifecycle test (CREATED -> CLOSED)
  2. Hardening suite (race condition, 4 concurrent emergencies, WS reconnect)
  3. Test fixture teardown (deactivates all TEST_ donors)

Usage:
  python -u run_tests.py

Requirements:
  Backend must be running on port 8000:
    docker compose --env-file backend/.env -f docker-compose.yml -f docker-compose.prod.yml up -d

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

def run_seed(action="seed"):
    """Run the test fixture seed or teardown step."""
    label = "Test Fixture Seed" if action == "seed" else "Test Fixture Teardown"
    print(f"\n{'='*60}")
    print(f"  {label.upper()}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-u", "test_seed.py", action],
        cwd=BACKEND_DIR,
    )
    return result.returncode == 0

def main():
    print("=" * 60)
    print("  LIFEPULSE CI — PHASE 1 REGRESSION GUARD")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\nNOTE: Backend must be running on port 8000 before invoking this runner.")

    # ── Step 0: Seed test fixtures ──────────────────────────────
    seed_ok = run_seed("seed")
    if not seed_ok:
        print("\n  [ABORT] Test fixture seeding failed. Cannot proceed without donor data.")
        print("  Ensure the backend is running: docker compose ... up -d")
        return 1

    # ── Step 1 & 2: Run tests ───────────────────────────────────
    results = {
        "E2E Lifecycle (CREATED -> CLOSED)":
            run_test("E2E Lifecycle", "e2e_test.py"),
        "Hardening Suite (race / concurrent / reconnect)":
            run_test("Hardening Suite", "test_concurrent.py"),
    }

    # ── Step 3: Teardown test fixtures ──────────────────────────
    run_seed("teardown")

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
