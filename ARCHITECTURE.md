# LifePulse AI — Backend Architecture Reference
## Phase 1 Stable Baseline · Tag: `v1.0.0-phase1`

---

## 1. Emergency State Machine

**File:** `backend/app/services/emergency_state_machine.py`

The `EmergencyStateMachine` is the single source of truth for all lifecycle transitions. Every state change:
1. Validates the transition against `VALID_TRANSITIONS`
2. Updates `EmergencyRequestDB.status` in the database
3. Writes an immutable `TimelineEventDB` record
4. Broadcasts a `STATE_TRANSITION` event over WebSocket

### State Graph

```
CREATED
  └─► AI_PROCESSING
        └─► VALIDATING
              └─► SEARCHING ──► SEARCHING (re-entry for progress updates)
                    └─► MATCHING
                          └─► RING1
                                ├─► RING2
                                │     ├─► DONOR_ACCEPTED
                                │     └─► WAITING
                                ├─► DONOR_ACCEPTED
                                └─► WAITING
                                      ├─► DONOR_ACCEPTED
                                      └─► CLOSED (timeout)

DONOR_ACCEPTED
  └─► TRACKING
        ├─► ARRIVING
        │     └─► ARRIVED
        │           └─► DONATION_STARTED
        │                 └─► DONATION_COMPLETED
        │                       └─► CLOSED
        └─► ARRIVED (direct if < 1km on connect)
```

### Valid Transitions Table

| From              | Allowed To                              |
|-------------------|-----------------------------------------|
| `CREATED`         | `AI_PROCESSING`, `SEARCHING`            |
| `AI_PROCESSING`   | `VALIDATING`, `SEARCHING`               |
| `VALIDATING`      | `SEARCHING`                             |
| `SEARCHING`       | `SEARCHING` (re-entry), `MATCHING`      |
| `MATCHING`        | `RING1`                                 |
| `RING1`           | `RING2`, `DONOR_ACCEPTED`, `WAITING`    |
| `RING2`           | `WAITING`, `DONOR_ACCEPTED`             |
| `WAITING`         | `DONOR_ACCEPTED`, `CLOSED`              |
| `DONOR_ACCEPTED`  | `TRACKING`                              |
| `TRACKING`        | `ARRIVING`, `ARRIVED`                   |
| `ARRIVING`        | `ARRIVED`                               |
| `ARRIVED`         | `DONATION_STARTED`                      |
| `DONATION_STARTED`| `DONATION_COMPLETED`                    |
| `DONATION_COMPLETED`| `CLOSED`                             |
| `CLOSED`          | *(terminal)*                            |

---

## 2. Matching Engine Flow

**Files:** `matching_engine.py` (orchestrator), `matching/hard_filters.py`, `matching/scorer.py`, `matching/blood_matrix.py`

### Pipeline

```
POST /api/v1/requests/
  │
  ▼
asyncio.create_task(run_matching_cycle(request_id))
  │
  ▼
[1] await manager.wait_for_connection(request_id, timeout=5.0)
    → blocks until WebSocket client connects, or proceeds headlessly
  │
  ▼
[2] AI_PROCESSING   — parse urgency, blood type, location
[3] VALIDATING      — blood matrix compatibility check
[4] SEARCHING       — hard filter pipeline:
      ├── blood type compatibility  (SEARCH_PROGRESS broadcast)
      ├── 56-day donation window    (SEARCH_PROGRESS broadcast)
      ├── distance radius           (SEARCH_PROGRESS broadcast)
      └── DONOR_MARKERS broadcast (eligible donors)
[5] MATCHING        — multi-factor rank: ETA + reliability + blood scarcity
[6] RING1           — top-N donors notified
                      asyncio.create_task(RingEscalationService.monitor_ring(id, 1))
```

---

## 3. WebSocket Event Protocol

**Endpoint:** `ws://host:8000/ws/requests/{request_id}`

### Event Types

| Type | Persisted | Frequency | Description |
|------|-----------|-----------|-------------|
| `CONNECTION_STATE` | — | On connect | Full snapshot for UI rebuild |
| `STATE_TRANSITION` | Yes | Per transition | Lifecycle state change |
| `SEARCH_PROGRESS` | No | Per filter pass | Filter count updates |
| `DONOR_MARKERS` | No | 2× during search | Map pin positions |
| `RING_COUNTDOWN` | No | Every 5s | Ring timer tick |
| `GPS_UPDATE` | No | ~1.5s/tick | Donor location during tracking |
| `ETA_UPDATE` | No | Per tick | ETA refinement |

### `CONNECTION_STATE` Payload

```json
{
  "type": "CONNECTION_STATE",
  "request_id": "req-xxxxxxxx",
  "data": {
    "current_state": "RING1",
    "timeline": [...],
    "accepted_match": null,
    "gps_position": {"lat": 37.77, "lng": -122.41},
    "eta": 3,
    "countdown_remaining": null
  }
}
```

### `STATE_TRANSITION` Payload

```json
{
  "type": "STATE_TRANSITION",
  "request_id": "req-xxxxxxxx",
  "state": "DONOR_ACCEPTED",
  "message": "A donor has accepted the emergency request.",
  "metadata": {},
  "timestamp": "2026-08-05T10:30:00Z"
}
```

### `GPS_UPDATE` Payload

```json
{
  "type": "GPS_UPDATE",
  "request_id": "req-xxxxxxxx",
  "step": 20,
  "total_steps": 49,
  "distance_km": 0.98,
  "eta_minutes": 1,
  "donor_lat": 37.771,
  "donor_lng": -122.419
}
```

---

## 4. Reconnect Protocol

```
Client reconnects
  │
  ▼
manager.connect(ws, request_id)
  → accepts socket, adds to active_connections
  → does NOT set asyncio.Event yet
  │
  ▼
main.py sends CONNECTION_STATE snapshot
  → current_state, timeline, accepted_match, gps_position, eta
  │
  ▼
manager.signal_connected(request_id)
  → sets asyncio.Event
  → ring escalation broadcasts now enabled for this connection
```

**Guarantee:** `CONNECTION_STATE` always arrives as the first message. `signal_connected()` is called only after the snapshot send completes, so no `RING_COUNTDOWN` or `GPS_UPDATE` broadcast can preempt it.

---

## 5. Atomic Donor Acceptance

**File:** `database.py` → `DatabaseRepository.try_accept_emergency()`

```python
def try_accept_emergency(self, req_id: str) -> bool:
    updated_count = self.session.query(EmergencyRequestDB).filter(
        EmergencyRequestDB.id == req_id,
        EmergencyRequestDB.status.in_(["RING1", "RING2", "WAITING"])
    ).update({"status": "DONOR_ACCEPTED"}, synchronize_session=False)
    self.session.commit()
    return updated_count > 0
```

- Returns `True` (lock acquired) → proceed with state transition
- Returns `False` (lock taken) → `POST /donors/respond` returns `HTTP 409 Conflict`

**Verified:** Two simultaneous accepts produce exactly `200` + `409`.

---

## 6. GPS Simulation Service

**File:** `app/services/gps_service.py`

- Haversine geodesic route from donor origin to hospital
- Tick interval: ~1.5s/step (configurable via `GPS_SIMULATION_SPEED`)
- Auto-transitions: `TRACKING` → `ARRIVING` (< 1km) → `ARRIVED` → `DONATION_STARTED` → `DONATION_COMPLETED` → `CLOSED`
- 60-second subscriber grace period before self-termination
- Clean `asyncio.CancelledError` handling

---

## 7. Test Suite

| Script | Scope |
|--------|-------|
| `backend/e2e_test.py` | Full lifecycle CREATED → CLOSED (73 events, 49 GPS ticks) |
| `backend/test_concurrent.py` | Race condition + 4 concurrent emergencies + WS reconnect snapshot |
| `run_tests.py` | CI runner — runs both suites, exits 0 on pass |

### Roll back to Phase 1 baseline

```bash
git checkout v1.0.0-phase1
```

---

## 8. Phase 2 Scope Boundary

> **Do NOT modify during Phase 2:**
> - `EmergencyStateMachine` state graph or `VALID_TRANSITIONS`
> - `matching_engine.py` pipeline order or filter logic
> - `try_accept_emergency()` atomic acceptance
> - `wait_for_connection()` / `signal_connected()` synchronization
> - `ring_escalation.py` escalation timer
> - `e2e_test.py`, `test_concurrent.py`, `run_tests.py`

> **Phase 2 targets (frontend UX only):**
> - Live GPS map with animated donor marker
> - Route polyline rendering
> - ETA countdown accuracy and display
> - Cinematic state transition animations
> - Tracking screen navigation polish
