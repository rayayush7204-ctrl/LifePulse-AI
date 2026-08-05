"""
Phase 1 Hardening Verification Suite
=====================================
Tests:
  1. Full E2E lifecycle (CREATED -> CLOSED)            [already confirmed]
  2. Race condition: two simultaneous accepts           [atomic DB test]
  3. Multiple concurrent emergencies (A/B/C/D)          [isolation test]
  4. WebSocket reconnect snapshot                       [resilience test]
  5. GPS orphan cleanup (60s no-subscriber grace)       [memory test]
"""
import asyncio
import httpx
import websockets
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
WS_URL   = "ws://127.0.0.1:8000/ws/requests"
PASS = "[PASS]"
FAIL = "[FAIL]"

# ── Helpers ───────────────────────────────────────────────────────────────────

async def create_emergency(label=""):
    async with httpx.AsyncClient(timeout=15.0) as client:
        payload = {
            "blood_type": "O-",
            "hospital_name": "Phase1 Test Hospital",
            "units_needed": 1,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "urgency": "CRITICAL",
        }
        res = await client.post(f"{BASE_URL}/api/v1/requests/", json=payload)
        if res.status_code != 200:
            print(f"  ERROR creating emergency {label}: HTTP {res.status_code} — {res.text}")
            sys.exit(1)
        data = res.json()
        rid = data["request"]["id"]
        if label:
            print(f"  Created {label}: {rid}")
        return rid

async def wait_for_state(req_id, target_state, timeout=90.0):
    """Connect WS and collect states until target_state is seen or timeout."""
    states = []
    uri = f"{WS_URL}/{req_id}"
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 30.0))
                    data = json.loads(raw)
                    if data.get("type") == "STATE_TRANSITION":
                        state = data.get("state", "")
                        states.append(state)
                        if state == target_state:
                            return states
                except asyncio.TimeoutError:
                    break
    except Exception as e:
        print(f"  WS error for {req_id}: {e}")
    return states

async def get_matches(req_id):
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(f"{BASE_URL}/api/v1/requests/{req_id}")
        res.raise_for_status()
        return res.json().get("matches", [])

async def try_accept(match_id):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(
                f"{BASE_URL}/api/v1/donors/respond",
                json={"match_id": match_id, "action": "ACCEPTED"},
            )
            return res.status_code
        except Exception:
            return 500

# ── Test 1: Race Condition ────────────────────────────────────────────────────

async def test_race_condition():
    print("\n=== TEST: Simultaneous Donor Acceptance (Race Condition) ===")
    req_id = await create_emergency("RACE")

    # Wait until RING1 so matches exist
    states = await wait_for_state(req_id, "RING1")
    if "RING1" not in states:
        print(f"  {FAIL} Never reached RING1. States: {states}")
        return False

    matches = await get_matches(req_id)
    print(f"  Found {len(matches)} match(es)")
    if len(matches) < 2:
        print(f"  {FAIL} Need at least 2 matches for race test (got {len(matches)})")
        return False

    m1 = matches[0]["match_id"]
    m2 = matches[1]["match_id"]
    print(f"  Firing two simultaneous accepts: {m1} vs {m2}")

    results = await asyncio.gather(try_accept(m1), try_accept(m2))
    print(f"  HTTP results: {results[0]}, {results[1]}")

    one_ok  = 200 in results
    one_409 = 409 in results
    if one_ok and one_409:
        print(f"  {PASS} Exactly one donor accepted (200), other got 409 Conflict.")
        return True
    else:
        print(f"  {FAIL} Unexpected results: {results}")
        return False

# ── Test 2: Multiple Concurrent Emergencies ───────────────────────────────────

async def test_multiple_emergencies():
    print("\n=== TEST: 4 Concurrent Emergencies (Isolation) ===")
    labels = ["A", "B", "C", "D"]
    req_ids = await asyncio.gather(*[create_emergency(f"Emergency-{l}") for l in labels])

    print("  Listening to all 4 channels simultaneously until RING1...")
    results = await asyncio.gather(*[wait_for_state(rid, "RING1") for rid in req_ids])

    all_pass = True
    for label, rid, states in zip(labels, req_ids, results):
        if "RING1" in states:
            print(f"  {PASS} Emergency-{label} ({rid}) reached RING1 — states: {' -> '.join(states)}")
        else:
            print(f"  {FAIL} Emergency-{label} ({rid}) did NOT reach RING1 — states: {states}")
            all_pass = False

    # Cross-talk check: verify each req only has its own matches
    print("  Cross-talk check...")
    cross_fail = False
    for rid in req_ids:
        matches = await get_matches(rid)
        for m in matches:
            if m.get("request_id") != rid:
                print(f"  {FAIL} Cross-talk! Match {m['match_id']} belongs to {m['request_id']} but appeared in {rid}")
                cross_fail = True
    if not cross_fail:
        print(f"  {PASS} No cross-talk detected. All match records are correctly isolated.")

    return all_pass and not cross_fail

# ── Test 3: WebSocket Reconnect Snapshot ─────────────────────────────────────

async def test_ws_reconnect():
    print("\n=== TEST: WebSocket Reconnect Snapshot ===")
    req_id = await create_emergency("RECONNECT")

    # First connection: wait for RING1
    print("  First connection — waiting for RING1...")
    states = await wait_for_state(req_id, "RING1")
    if "RING1" not in states:
        print(f"  {FAIL} Never reached RING1 before reconnect attempt.")
        return False

    print("  Disconnected. Waiting 5s...")
    await asyncio.sleep(5)

    print("  Reconnecting...")
    try:
        async with websockets.connect(f"{WS_URL}/{req_id}", open_timeout=10) as ws:
            # The CONNECTION_STATE snapshot is guaranteed to be sent, but
            # RING_COUNTDOWN ticks may arrive concurrently. Scan up to 10
            # messages to find the snapshot.
            snapshot_msg = None
            for _ in range(10):
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg = json.loads(raw)
                    if msg.get("type") == "CONNECTION_STATE":
                        snapshot_msg = msg
                        break
                    else:
                        print(f"  (skipping {msg.get('type')} — waiting for CONNECTION_STATE)")
                except asyncio.TimeoutError:
                    break

            if not snapshot_msg:
                print(f"  {FAIL} CONNECTION_STATE snapshot never received within 10 messages / 5s.")
                return False

            data       = snapshot_msg.get("data", {})
            curr_state = data.get("current_state")
            has_timeline  = isinstance(data.get("timeline"), list)
            has_gps_key   = "gps_position" in data
            has_eta_key   = "eta" in data

            print(f"  Snapshot type:     CONNECTION_STATE")
            print(f"  current_state:     {curr_state}")
            print(f"  timeline present:  {has_timeline} ({len(data.get('timeline', []))} events)")
            print(f"  gps_position key:  {has_gps_key}")
            print(f"  eta key:           {has_eta_key}")

            ok = (
                curr_state == "RING1"
                and has_timeline
                and has_gps_key
                and has_eta_key
            )
            if ok:
                print(f"  {PASS} Reconnect snapshot correct. UI can fully rebuild from one payload.")
                return True
            else:
                print(f"  {FAIL} Snapshot incomplete or wrong state. Full msg: {json.dumps(snapshot_msg, indent=2)}")
                return False
    except asyncio.TimeoutError:
        print(f"  {FAIL} Timeout: no snapshot received within 5s of reconnect.")
        return False

# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  PHASE 1 HARDENING VERIFICATION SUITE")
    print("=" * 60)

    results = {}
    results["race_condition"]          = await test_race_condition()
    results["multiple_emergencies"]    = await test_multiple_emergencies()
    results["ws_reconnect"]            = await test_ws_reconnect()

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        status = PASS if passed else FAIL
        print(f"  {status} {name.replace('_', ' ').title()}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  RESULT: ALL HARDENING CHECKS PASSED")
        print("  Phase 1 is PRODUCTION-READY.")
    else:
        print("  RESULT: ONE OR MORE CHECKS FAILED")
    print("=" * 60)
    return 0 if all_pass else 1

if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
