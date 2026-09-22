# SleepCare CPAP Ecosystem — State, Persistence & Cache Architecture

> **DISP Laboratory (Lyon) & Linde HomeCare France**  
> *Author: Pamit Duggal (Software & AI Engineering Intern)*  
> *Scope: In-Memory Singletons, Disk Ledgers, Deduplication Caches & Concurrency*

---

## 1. State Management Philosophy

In a continuous clinical telemonitoring infrastructure, state mutations must be:
1. **Idempotent**: Reprocessing a telemetry file or re-running an inference pass must never produce duplicate video prescriptions or double-count interventions.
2. **Sub-Millisecond ($O(1)$) in Memory**: Ingress verification must execute in $<1\text{ms}$ to avoid inflating end-to-end telemetry transit latency.
3. **Crash-Resilient via Atomic Disk Swapping**: File writes must survive abrupt host restarts or socket resets (`WinError 64`) without file truncation.
4. **Thread-Safe**: Mutex locks must synchronize shared structures across concurrent HTTP requests and background daemon workers.

---

## 2. In-Memory State & Singletons

### 2.1 Pre-Generation Deduplication Shield Singleton (`PreGenDeduplicationEngine`)
- **Location**: [`CPAP_Video_Server/deduplication_engine.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_Video_Server/deduplication_engine.py)
- **Lifecycle**: Initialized via factory `get_deduplication_engine()` on first `/api/vertex-generate` call.
- **Cache Invalidation Mechanism**: Tracks OS file modification timestamps (`os.path.getmtime`). When files are unchanged, zero disk I/O occurs:
  ```python
  if current_mtime == self._last_cache_mtime:
      return self._in_memory_cache
  ```
- **Lookup Cost**: $O(1)$ dictionary lookup for Level 1 MD5 prompt hashes; sub-millisecond token set intersection for Level 2 and 3.

### 2.2 AI Server Persistent Assignment Tracker (`VideoAssignmentTracker`)
- **Location**: [`CPAP_AI_Server/core/video_engine.py`](file:///c:/Users/pduggal/Downloads/CPAP%20new/CPAP_AI_Server/core/video_engine.py)
- **Data Structure**: In-memory `Set[Tuple[patient_id, video_filename]]`.
- **Active Size**: **9,676+ patient assignments** loaded into RAM at startup.
- **Thread Safety**: Wrapped in `threading.RLock()` across all `is_assigned()` and `record_assignment()` calls.

### 2.3 Real-Time Circular Log Buffers (`LogRingBuffer`)
- **Location**: Both Video Server and AI Server.
- **Data Structure**: `collections.deque(maxlen=1000)` storing timestamped structured log lines.
- **Consumption**: Polled via `/api/server/logs?since_id=X` or streamed via SSE `/api/logs/stream` directly to browser terminals without querying disk log files.

---

## 3. Disk-Backed Ledgers & Atomic Swapping Pattern

Disk state files are maintained as structured JSON. To prevent corruption during concurrent requests or power failures, all writes employ the **Atomic `.tmp` Swap Pattern**:

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. Prepare updated JSON payload in memory              │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. Write payload to temporary file:                    │
 │    metadata/assigned_video_history.json.tmp            │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 3. Flush OS buffer to disk: file.flush(); os.fsync()   │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 4. Atomic Replace:                                     │
 │    os.replace("assigned...json.tmp", "assigned...json")│
 └────────────────────────────────────────────────────────┘
```

### Core Persistent State Files

| State File Path | Server | Format | Purpose |
| :--- | :--- | :--- | :--- |
| `CPAP_Video_Server/metadata/assigned_video_history.json` | Video VM4 | JSON Object | Maps `patient_id` to assigned videos, timestamps, and step sequences. |
| `CPAP_Video_Server/metadata/generative_cache_index.json` | Video VM4 | Key-Value JSON | Maps `MD5(prompt)` to cached MP4 filename for Level 1 dedup. |
| `CPAP_Video_Server/metadata/master_video_metadata.json` | Video VM4 | Array of 39 JSONs | Consolidated master registry profiling all 39 video clips. |
| `CPAP_AI_Server/artifacts/assigned_videos_tracker.json` | AI Server VM3 | JSON Object | Stores assignment history for 9,676+ cohort patients. |
| `CPAP_AI_Server/distributed_trigger_catalog.json` | AI Server VM3 | JSON Array | Local cache of 39 video trigger criteria, boolean rules, and priorities. |
| `CPAP_Raspberry_Pi/logs/events/<event_id>.json` | Pi Edge | Individual JSON | One file per `/ingest` transaction with full metrics & RTT. |

---

## 4. Telemetry Storage & Audit Trails on Edge Pi

The Raspberry Pi edge node persists raw ingestion records for medical auditing and compliance:

1. **`data/ingest/<timestamp>_<patient_id>.csv`**:
   Every raw CSV uploaded to `POST /ingest` is saved before processing. These files serve as legal audit records of the exact device readings sent by the patient.
2. **`logs/events/<event_id>.json`**:
   Created during Phase 1 (`/ingest`) and updated during Phase 2 (`/timing`). Contains:
   - `event_id`, `patient_id`, `source`
   - Raw metrics snapshot (`leaks95`, `usage_hours`, `ahi`, wearable readings)
   - Decision details: `scenario`, `video_title`, `video_filename`
   - Latency metrics: `processing_ms`, `vm_push_ms`, `transit_latency_ms`, `total_latency_ms`
   - SLA audit: `budget_s: 60.0`, `budget_passed: true`, `backend_sync: "phase2_ok"`
3. **`logs/detected_events_and_video_requests.log`**:
   Append-only human-readable ledger of all flagged anomalies, video assignments, and dashboard clear actions.

---

## 5. Central Clinical Database Schema (`DB_Clinical` on VM2)

The Central Clinical Backend on VM2 hosts PostgreSQL database `DB_Clinical`:

### 5.1 Telemetry Event Traces Table (`telemetry.event_traces`)
Keyed on `event_id` (UUID string):
- `event_id` (VARCHAR(64), PRIMARY KEY)
- `patient_id` (VARCHAR(32), INDEXED)
- `trigger_type` (VARCHAR(64))
- `severity` (VARCHAR(16))
- `scenario` (VARCHAR(32))
- `video_filename` (VARCHAR(128))
- `pi_processing_ms` (FLOAT)
- `video_vm_push_ms` (FLOAT)
- `transit_latency_ms` (FLOAT)
- `total_latency_ms` (FLOAT)
- `budget_passed` (BOOLEAN)
- `is_test` (BOOLEAN)
- `created_at` (TIMESTAMP WITH TIME ZONE)
- `frontend_fetched_at` (TIMESTAMP WITH TIME ZONE, NULLABLE)
- `frontend_cleared_at` (TIMESTAMP WITH TIME ZONE, NULLABLE)

> [!NOTE]
> **Upsert Race Condition Handling**: The Pi pushes Phase 1 on `/ingest` and Phase 2 on `/timing`. Because the two calls occur within ~300ms, the backend must use an atomic upsert:
> ```sql
> INSERT INTO telemetry.event_traces (...) VALUES (...)
> ON CONFLICT (event_id) DO UPDATE SET
>   transit_latency_ms = EXCLUDED.transit_latency_ms,
>   total_latency_ms = EXCLUDED.total_latency_ms,
>   budget_passed = EXCLUDED.budget_passed;
> ```

---

*Proceed to [DEPLOYMENT.md](file:///c:/Users/pduggal/Downloads/CPAP%20new/docs/DEPLOYMENT.md) for server runbooks and environment configuration.*
