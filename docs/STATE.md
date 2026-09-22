# SleepCare CPAP Ecosystem: State, Persistence, and Cache Architecture

> DISP Laboratory (Université Lumière Lyon 2 / INSA Lyon) and Linde HomeCare France  
> Author: Pamit Duggal (Software and AI Engineering Intern)  
> Scope: In-memory cache structures, disk ledgers, and database storage

---

## 1. State design requirements

Medical telemonitoring software cannot afford corrupted state files or repeated alerts. We designed state management around four practical rules:
1. **Idempotence**: Reprocessing an upload must never prescribe the same video twice or double-count an intervention in clinical records.
2. **Sub-millisecond memory checks**: In-memory lookups must run in less than 1 ms so that checking previous history does not slow down the video response.
3. **Atomic disk writes**: We use a temporary file swap pattern so that a sudden server crash never leaves half-written or truncated JSON files on disk.
4. **Thread safety**: Read-write locks protect shared dictionaries when multiple HTTP requests arrive simultaneously.

---

## 2. In-memory singletons and buffers

### Deduplication engine (`PreGenDeduplicationEngine`)
- Location: `CPAP_Video_Server/deduplication_engine.py`
- Lifecycle: Instantiated on the first call to `/api/vertex-generate` and held in memory.
- File watch mechanism: It checks `os.path.getmtime` on cache files. If the timestamp has not changed, it skips disk reads entirely and uses its memory cache:
  ```python
  if current_mtime == self._last_cache_mtime:
      return self._in_memory_cache
  ```
- Lookup cost: An O(1) hash lookup for Level 1 exact matches, followed by set intersection for Level 2 and Level 3 keywords.

### Assignment tracker (`VideoAssignmentTracker`)
- Location: `CPAP_AI_Server/core/video_engine.py`
- Internal structure: In-memory set of `(patient_id, video_filename)` tuples.
- Scale: Holds patient history in memory and backs up to disk.
- Concurrency control: Protected by `threading.RLock()` across all reads and writes.

### Ring buffer log streams (`LogRingBuffer`)
- Location: Implemented on both the Video Server and the AI Server.
- Structure: `collections.deque(maxlen=1000)` holding recent log events.
- Output: Polled by the dashboard console via `/api/server/logs?since_id=X` or streamed through SSE (`/api/logs/stream`), avoiding repeated disk reads.

---

## 3. Atomic file writes

All disk state files use structured JSON. To prevent file corruption during sudden system shutdowns or socket interruptions, every update follows a four-step swap pattern:

```text
+--------------------------------------------------------+
| 1. Prepare updated JSON payload in memory              |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 2. Write payload to temporary file:                    |
|    metadata/assigned_video_history.json.tmp            |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 3. Flush OS buffer to disk: file.flush(); os.fsync()   |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 4. Atomic file rename:                                 |
|    os.replace("assigned...json.tmp", "assigned...json")|
+--------------------------------------------------------+
```

### Persistent state files

| Path | Host | Format | Purpose |
| :--- | :--- | :--- | :--- |
| `CPAP_Video_Server/metadata/assigned_video_history.json` | Video VM4 | JSON Object | Maps patient IDs to video assignments and timestamps. |
| `CPAP_Video_Server/metadata/generative_cache_index.json` | Video VM4 | Key-Value JSON | Maps prompt MD5 hashes to rendered video filenames. |
| `CPAP_Video_Server/metadata/master_video_metadata.json` | Video VM4 | JSON Array | Master catalog of all 39 video clips. |
| `CPAP_AI_Server/artifacts/assigned_videos_tracker.json` | AI Server VM3 | JSON Object | Stores assignment history for cohort patients. |
| `CPAP_AI_Server/distributed_trigger_catalog.json` | AI Server VM3 | JSON Array | Local cache of the 39-video trigger matrix. |
| `CPAP_Raspberry_Pi/logs/events/<event_id>.json` | Pi Edge | JSON Document | One record per `/ingest` call with metrics and RTT timing. |

---

## 4. Ingestion logs on the edge node

The Raspberry Pi stores audit records for compliance and testing:

1. **`data/ingest/<timestamp>_<patient_id>.csv`**: Raw CSV files uploaded to `POST /ingest` are saved before parsing, providing an audit trail of original patient readings.
2. **`logs/events/<event_id>.json`**: Created during `/ingest` and updated when `/timing` returns. Contains:
   - Patient ID, event ID, and timestamp
   - Sensor values (leak, usage hours, residual AHI)
   - Selected intervention scenario and video filename
   - Measured latencies (`processing_ms`, `transit_latency_ms`, `total_latency_ms`)
   - SLA flag (`budget_passed: true`)
3. **`logs/detected_events_and_video_requests.log`**: Text log recording anomalies, video dispatches, and dashboard reset actions.

---

## 5. PostgreSQL database on VM2 (`DB_Clinical`)

The central backend uses PostgreSQL to store long-term records.

### Telemetry table schema (`telemetry.event_traces`)
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

Note on two-phase pushes: Because `/ingest` and `/timing` hit the backend within 300 ms of each other, the database uses an upsert query to avoid race conditions:
```sql
INSERT INTO telemetry.event_traces (event_id, patient_id, ...) 
VALUES (...)
ON CONFLICT (event_id) DO UPDATE SET
  transit_latency_ms = EXCLUDED.transit_latency_ms,
  total_latency_ms = EXCLUDED.total_latency_ms,
  budget_passed = EXCLUDED.budget_passed;
```

Continue to [DEPLOYMENT.md](DEPLOYMENT.md) for installation and runbook instructions.
