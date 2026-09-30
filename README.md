# VitalGrid — Hospital Spatial Resource Arbiter Engine

VitalGrid is a HealthTech spatial resource arbiter that solves **stale bed occupancy state** in hospital networks using hierarchical dynamic tree locking ($O(h)$ validation) and 30-second Time-To-Live (TTL) lease heartbeats.

---

## The Problem Statement

UK and US hospitals lose enormous capacity not to a genuine shortage of physical beds, but to **stale occupancy state** — beds that are physically empty but still shown as locked in the system because a discharge, transfer, or equipment release was never formally logged.

In England right now, average bed occupancy across adult general and acute beds sits at **94.5%**, well above the 85% threshold experts consider safe. **13,000 discharges are delayed every single day**, meaning roughly **1 in 10 NHS beds** at any given moment are occupied by patients who are medically fit to leave but haven't been formally released in the system.

That translates to **6.75 million bed-days lost annually**, at a cost the NHS itself now models against a bed-day price of **£562**, and it's the direct driver behind a genuinely alarming knock-on statistic: **corridor-care incidents hit 570,957 in 2025/26**, up from just 123 in 2011/12. This is a resource-tracking and stale-state problem at its core — a bed's *system status* silently drifts out of sync with its *physical status*, and nothing automatically corrects it.

VitalGrid addresses this as a distributed systems problem: hierarchical resource locks (**Hospital &rarr; Ward &rarr; Department &rarr; Room &rarr; Bed**) with TTL-based leases and heartbeat renewal ensure that a resource's system-recorded state can never silently drift from its real-world state for longer than one lease cycle (30s), auto-releasing stale locks and surfacing the failure via a real-time audit stream.

---

## Data Sources & References

- **Primary Government Portal**: [NHS England Acute Discharge Situation Report](https://www.england.nhs.uk/statistics/statistical-work-areas/discharge-delays/acute-discharge-situation-report/)
- **13,000 Daily Delayed Discharges & £562/bed-day**: The King's Fund / NHS England discharge data via [LBC News (2025/26)](https://www.lbc.co.uk/news/health/nhs-hospitals-health-latest/)
- **94.5% Occupancy, 6.75M Lost Bed-Days, 570k Corridor Care**: [Age UK Analysis of NHS Bed Occupancy Statistics (Oct 2025)](https://www.ageuk.org.uk/latest-press/age-uk-says-recent-governments-have-taken-their-eye-off-the-ball-on-delayed-discharges--up-nearly-70-in-five-years/)
- **Independent Corroboration & 85% Safe Occupancy Limit**: [The Health Foundation, "Delayed discharges from hospital" (Dec 2025)](https://www.health.org.uk/reports-and-analysis/analysis/delayed-discharges-from-hospital-comparing-performance)

> **Citation**: Sources: Primary NHS England Acute Discharge Situation Report; The King's Fund / NHS England discharge data (via LBC, 2025/26); Age UK analysis of NHS bed occupancy and delayed discharge statistics (Oct 2025); The Health Foundation, "Delayed discharges from hospital" (Dec 2025).

---

## Core System Architecture

```
[ St. Thomas' Hospital ]  (Root Node, locked_descendant_count: 1)
        │
        ├── [ Ward Alpha (Acute) ]  (locked_descendants: 1, Gold Outline)
        │         │
        │         ├── [ ICU Department ]
        │         │         │
        │         │         ├── [ Room 101 ]
        │         │         │     ├── [ Bed 101A ] ── [ Locked: nurse-jones | 30s TTL ]
        │         │         │     └── [ Bed 101B ] ── [ Available ]
        │         │         │
        │         │         └── [ Room 102 ]
        │         │               ├── [ Bed 102A ] ── [ Available ]
        │         │               └── [ Bed 102B ] ── [ Available ]
        │         │
        │         └── [ Cardiology Dept ]
        │                   └── [ Room 201 ] ── [ Bed 201A ]
        │
        └── [ Ward Beta (Surgical) ]  (All Beds Available)
                  └── [ Surgery Dept ] ── [ Room 301 ] ── [ Bed 301A ]
```

---

## Technical Features

1. **Sub-Millisecond O(h) Lock Verification**: Bounded by tree depth $h$ rather than total node count $N$.
2. **Pessimistic Thread Isolation**: Uses `threading.Lock()` to prevent race conditions during high-concurrency patient bed allocations.
3. **30s TTL Lease & Heartbeat Pulse**: Active telemetry devices / staff apps issue background pulses (`POST /api/v1/resource/heartbeat`) to extend leases.
4. **Crash-Safe Auto-Release**: If an agent crashes or a discharge goes un-logged, the 1-second background worker automatically expires the lease and releases the bed lock.
5. **Real-Time WebSockets Stream**: Broadcasts `INITIAL_STATE`, lock mutations, and `LEASE_EXPIRED` events to subscribers via `ws://localhost:8001/ws/events`.
6. **2D Interactive Hospital Ward Canvas**: HTML5 Canvas visualizing physical wards, rooms, bed bays, glowing lock overlays, and animated clinical staff movements.

---

## Technology Stack

- **Backend**: Python 3.12, FastAPI, Pydantic, Uvicorn.
- **Concurrency & Engine**: `threading.Lock`, `threading.Barrier`, `ThreadPoolExecutor`, `asyncio` lifespan workers.
- **Testing**: Pytest (16/16 multi-threaded stress & heartbeat test cases).
- **Frontend**: Vanilla JavaScript (ES6+), HTML5 Canvas 2D Context, CSS3 (Mint/Emerald HealthTech Token System).
- **Deployment**: Docker, Docker Compose, Uvicorn.

---

## Quickstart & Local Setup

### 1. Install Dependencies
```bash
cd VitalGrid
pip install -r requirements.txt
```

### 2. Run Pytest Concurrency Suite
```bash
pytest -v
```

### 3. Launch Development Server
```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
```
Open **http://localhost:8001** in your browser.

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/resource/lock` | Acquire exclusive 30s TTL lease lock on node |
| `POST` | `/api/v1/resource/unlock` | Release bed lock owned by agent |
| `POST` | `/api/v1/resource/heartbeat` | Renew 30s lease for active patient/staff agent |
| `POST` | `/api/v1/resource/upgrade` | Upgrade child locks to parent node lock |
| `GET` | `/api/v1/resource/status` | Fetch full spatial tree hierarchy & node list |
| `GET` | `/api/v1/audit` | Retrieve append-only transaction ledger |
| `WS` | `/ws/events` | Real-time WebSocket event broadcast stream |

---

## Docker Deployment

```bash
docker-compose up -d --build
```
The application will be accessible at `http://localhost:8001`.
