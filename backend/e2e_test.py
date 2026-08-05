"""
End-to-End Emergency Dispatch Flow Test
Tests the complete lifecycle:
  CREATED -> AI_PROCESSING -> VALIDATING -> SEARCHING -> MATCHING -> RING1
  -> DONOR_ACCEPTED -> TRACKING -> ARRIVING -> ARRIVED
  -> DONATION_STARTED -> DONATION_COMPLETED

Usage: python -u e2e_test.py
Requires: backend running on port 8000 (python -m uvicorn app.main:app --port 8000)
"""
import asyncio
import httpx
import websockets
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/requests"

# Terminal states that signal end of the lifecycle
TERMINAL_STATES = {"CLOSED", "CANCELLED"}

# All expected states in order
EXPECTED_STATES = [
    "VALIDATING", "SEARCHING", "MATCHING", "RING1",
    "DONOR_ACCEPTED", "TRACKING", "ARRIVING", "ARRIVED",
    "DONATION_STARTED", "DONATION_COMPLETED", "CLOSED"
]


async def run_e2e_test():
    start_time = time.time()
    print("=" * 60)
    print("  LIFEPULSE E2E DISPATCH FLOW TEST")
    print("=" * 60)

    # ----------------------------------------------------------------
    # STEP 1: Create emergency request payload
    # ----------------------------------------------------------------
    payload = {
        "hospital_name": "UCSF Medical Center",
        "latitude": 37.7631,
        "longitude": -122.4578,
        "blood_type": "O-",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "patient_name": "Test Patient",
        "requester_phone": "1234567890",
        "notes": "E2E Test"
    }

    # ----------------------------------------------------------------
    # STEP 2: POST request (but do NOT connect WS yet — we need the ID first)
    # ----------------------------------------------------------------
    print("\n[STEP 1] Creating emergency request...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{BASE_URL}/api/v1/requests/", json=payload)
        if response.status_code != 200:
            print(f"  [FAIL] HTTP {response.status_code}")
            print(f"  Response body: {response.text}")
            return False
        data = response.json()
        req_id = data["request"]["id"]
        print(f"  [OK] Request created. ID: {req_id}")

    # ----------------------------------------------------------------
    # STEP 3: Connect WebSocket IMMEDIATELY after getting request ID.
    # The matching engine runs as an async background task, so we have
    # a small window to connect before AI_PROCESSING fires.
    # ----------------------------------------------------------------
    print("\n[STEP 2] Connecting WebSocket...")
    events_received = []
    state_transitions = []
    accept_triggered = False

    uri = f"{WS_URL}/{req_id}"

    async with websockets.connect(uri) as websocket:
        print(f"  [OK] WebSocket connected to {uri}")

        async def do_accept():
            """Fetch matches and accept the first one."""
            nonlocal accept_triggered
            if accept_triggered:
                return
            accept_triggered = True

            # Small delay to let Ring1 settle and matches to be queryable
            await asyncio.sleep(1.5)
            print("\n[STEP 3] Fetching matches for donor acceptance...")

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BASE_URL}/api/v1/requests/{req_id}")
                if resp.status_code != 200:
                    print(f"  [FAIL] GET /requests/{req_id} returned HTTP {resp.status_code}")
                    print(f"  Response body: {resp.text}")
                    return

                status_data = resp.json()
                matches = status_data.get("matches", [])
                print(f"  Found {len(matches)} match(es)")

                if not matches:
                    print("  [FAIL] No matches returned. Cannot accept.")
                    return

                # Use match_id (not id) — match_id is what get_match() queries by
                first_match = matches[0]
                mid = first_match.get("match_id")
                donor_id = first_match.get("donor_id", "?")
                donor_name = first_match.get("donor_name", "?")
                distance = first_match.get("distance_km", "?")
                print(f"  Selected match: match_id={mid}, donor_id={donor_id}, "
                      f"name={donor_name}, distance={distance}km")

                if not mid:
                    print("  [FAIL] match_id is None. Match dict keys: " + str(list(first_match.keys())))
                    return

                accept_payload = {
                    "match_id": mid,
                    "action": "ACCEPTED",
                    "eta_minutes": 15
                }
                print(f"\n[STEP 4] Accepting match {mid}...")
                accept_resp = await client.post(
                    f"{BASE_URL}/api/v1/donors/respond", json=accept_payload
                )
                print(f"  HTTP {accept_resp.status_code}")
                if accept_resp.status_code != 200:
                    print(f"  [FAIL] Accept response body: {accept_resp.text}")
                else:
                    accept_data = accept_resp.json()
                    print(f"  [OK] {accept_data.get('message', '')}")

        # Listen for WebSocket events with a generous timeout
        # GPS simulation at 120km/h for ~5km = ~150 steps + donation = ~160s max
        MAX_WAIT_SECONDS = 180
        overall_deadline = time.time() + MAX_WAIT_SECONDS

        while time.time() < overall_deadline:
            try:
                remaining = max(1, overall_deadline - time.time())
                message = await asyncio.wait_for(websocket.recv(), timeout=min(remaining, 30.0))
                evt = json.loads(message)
                events_received.append(evt)

                evt_type = evt.get("type", "?")

                if evt_type == "STATE_TRANSITION":
                    state = evt.get("state", "?")
                    msg = evt.get("message", "")
                    state_transitions.append(state)
                    print(f"  >> STATE: {state} -- {msg}")

                    # Trigger donor accept when RING1 is reached
                    if state == "RING1" and not accept_triggered:
                        asyncio.create_task(do_accept())

                    # Stop when we reach a terminal state
                    if state in TERMINAL_STATES:
                        print(f"\n  [OK] Reached terminal state: {state}")
                        break

                elif evt_type == "SEARCH_PROGRESS":
                    phase = evt.get("data", {}).get("phase", "")
                    label = evt.get("data", {}).get("label", "")
                    print(f"  >> PROGRESS: {phase} -- {label}")

                elif evt_type == "DONOR_MARKERS":
                    phase = evt.get("data", {}).get("phase", "")
                    count = len(evt.get("data", {}).get("markers", []))
                    print(f"  >> MARKERS: {phase} ({count} donors)")

                elif evt_type == "RING_COUNTDOWN":
                    secs = evt.get("data", {}).get("seconds_remaining", "?")
                    # Print countdown sparingly
                    if secs in (45, 40, 30, 20, 10, 5):
                        print(f"  >> COUNTDOWN: {secs}s remaining")

                elif evt_type == "GPS_UPDATE":
                    dist = evt.get("distance_km", "?")
                    eta = evt.get("eta_minutes", "?")
                    step_num = evt.get("step", "?")
                    total = evt.get("total_steps", "?")
                    # Print GPS updates sparingly
                    if isinstance(step_num, int) and step_num % 20 == 0:
                        print(f"  >> GPS: step {step_num}/{total}, {dist}km remaining, ETA {eta}min")

                else:
                    pass  # Ignore other event types silently

            except asyncio.TimeoutError:
                print(f"\n  [TIMEOUT] No event received for 30s. Stopping.")
                break
            except websockets.exceptions.ConnectionClosed as e:
                print(f"\n  [WS CLOSED] {e}")
                break
            except Exception as e:
                print(f"\n  [ERROR] {e}")
                break

    # ----------------------------------------------------------------
    # VALIDATION
    # ----------------------------------------------------------------
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  VALIDATION RESULTS")
    print("=" * 60)

    print(f"\nStates observed: {' -> '.join(state_transitions)}")
    print(f"Total events received: {len(events_received)}")
    print(f"Elapsed time: {elapsed:.1f}s")

    all_pass = True
    for s in EXPECTED_STATES:
        if s in state_transitions:
            print(f"  [PASS] {s}")
        else:
            print(f"  [FAIL] {s} -- NOT OBSERVED")
            all_pass = False

    # Check progress events
    progress_phases = [
        e.get("data", {}).get("phase")
        for e in events_received
        if e.get("type") == "SEARCH_PROGRESS"
    ]
    if "distance_filter" in progress_phases:
        print(f"  [PASS] SEARCH_PROGRESS events ({len(progress_phases)} phases)")
    else:
        print(f"  [FAIL] SEARCH_PROGRESS events missing distance_filter. Got: {progress_phases}")
        all_pass = False

    # Check donor markers
    marker_events = [e for e in events_received if e.get("type") == "DONOR_MARKERS"]
    if marker_events:
        print(f"  [PASS] DONOR_MARKERS events ({len(marker_events)} broadcasts)")
    else:
        print(f"  [FAIL] DONOR_MARKERS events missing")
        all_pass = False

    # Check GPS updates
    gps_events = [e for e in events_received if e.get("type") == "GPS_UPDATE"]
    if gps_events:
        print(f"  [PASS] GPS_UPDATE events ({len(gps_events)} ticks)")
    else:
        print(f"  [FAIL] GPS_UPDATE events missing")
        all_pass = False

    print("\n" + "=" * 60)
    if all_pass:
        print("  RESULT: ALL CHECKS PASSED")
    else:
        print("  RESULT: SOME CHECKS FAILED")
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    success = asyncio.run(run_e2e_test())
    sys.exit(0 if success else 1)
