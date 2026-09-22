#!/usr/bin/env python3
"""
===============================================================================
assignment_ledger.py - Persistent Video Assignment Ledger & Deduplication Engine
===============================================================================
Tracks and persists all video coaching assignments made to patients to prevent
duplicate video assignments across server restarts or pipeline replays.
===============================================================================
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone

env_base = os.environ.get("VIDEO_BASE_DIR")
if env_base and Path(env_base).exists():
    BASE_DIR = Path(env_base)
else:
    BASE_DIR = Path(__file__).resolve().parent

METADATA_DIR = BASE_DIR / "metadata"
LEDGER_FILE = METADATA_DIR / "assigned_video_history.json"

logger = logging.getLogger("CPAP_Assignment_Ledger")


class VideoAssignmentLedger:
    """
    Thread-safe persistent ledger tracking all video assignments made to patients.
    Guarantees idempotency: prevents assigning the same video/sequence twice to
    the same patient upon server restarts or error recovery replays.
    """
    def __init__(self, ledger_path: Path = LEDGER_FILE):
        self.ledger_path = ledger_path
        self._lock = threading.RLock()
        self._patient_history: Dict[str, List[Dict[str, Any]]] = {}
        self._assigned_fingerprints: Set[str] = set()
        self._assigned_event_ids: Set[str] = set()
        self._latest_decision_cache: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load_ledger()

    def _load_ledger(self):
        """Loads historical assignments from disk into memory."""
        with self._lock:
            if not self.ledger_path.exists():
                return
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                records = data.get("patients", {})
                self._patient_history = records
                
                for pid, history in records.items():
                    if not history:
                        continue
                    # Cache the most recent decision
                    latest_item = history[-1]
                    decision_payload = latest_item.get("decision_payload")
                    if decision_payload:
                        self._latest_decision_cache[str(pid)] = decision_payload
                        
                    for entry in history:
                        fp = entry.get("fingerprint")
                        if fp:
                            self._assigned_fingerprints.add(fp)
                        evt = entry.get("event_id")
                        if evt:
                            self._assigned_event_ids.add(str(evt))
                            
                logger.info(f"[ASSIGNMENT LEDGER] Loaded {len(self._assigned_fingerprints)} historical assignments across {len(self._patient_history)} patients.")
            except Exception as err:
                logger.warning(f"[ASSIGNMENT LEDGER] Could not read ledger from {self.ledger_path}: {err}")

    def save_ledger(self):
        """Persists the ledger to disk atomically."""
        with self._lock:
            try:
                self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "total_patients_tracked": len(self._patient_history),
                    "total_assignments_recorded": len(self._assigned_fingerprints),
                    "patients": self._patient_history
                }
                temp_path = self.ledger_path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                temp_path.replace(self.ledger_path)
                self._dirty = False
            except Exception as err:
                logger.error(f"[ASSIGNMENT LEDGER SAVE ERROR] {err}")

    def compute_fingerprint(self, patient_id: str, video_filename: Optional[str] = None, clips: Optional[List[Dict[str, Any]]] = None, title: Optional[str] = None) -> str:
        """Computes a deterministic fingerprint for a patient assignment."""
        pid_clean = str(patient_id).strip()
        if clips and len(clips) > 0:
            clip_names = [c.get("video_filename") or c.get("filename") or str(c.get("video_id")) for c in clips]
            return f"{pid_clean}:pkg:{'_'.join(str(n) for n in clip_names)}"
        elif video_filename:
            return f"{pid_clean}:vid:{video_filename}"
        elif title:
            return f"{pid_clean}:title:{title}"
        return f"{pid_clean}:default"

    def is_already_assigned(self, patient_id: str, event_id: Optional[str] = None, video_filename: Optional[str] = None, clips: Optional[List[Dict[str, Any]]] = None, title: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Checks if the requested video/event was already assigned to this patient.
        Returns: (is_duplicate, previous_decision_payload)
        """
        pid_clean = str(patient_id).strip()
        
        with self._lock:
            # Check 1: Event ID match
            if event_id and str(event_id).strip() in self._assigned_event_ids:
                cached_decision = self._latest_decision_cache.get(pid_clean)
                return True, cached_decision
                
            # Check 2: Patient + Video fingerprint match
            fp = self.compute_fingerprint(pid_clean, video_filename, clips, title)
            if fp in self._assigned_fingerprints:
                cached_decision = self._latest_decision_cache.get(pid_clean)
                return True, cached_decision

        return False, None

    def record_assignment(self, patient_id: str, event_id: Optional[str], video_filename: Optional[str], decision_payload: Dict[str, Any], dashboard_status: str = "success", clips: Optional[List[Dict[str, Any]]] = None, title: Optional[str] = None):
        """Records a new successful video assignment into the ledger."""
        pid_clean = str(patient_id).strip()
        fp = self.compute_fingerprint(pid_clean, video_filename, clips, title)
        
        entry = {
            "fingerprint": fp,
            "event_id": str(event_id) if event_id else None,
            "video_filename": video_filename,
            "title": title or decision_payload.get("title"),
            "video_type": decision_payload.get("video_type", "single"),
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "dashboard_push_status": dashboard_status,
            "decision_payload": decision_payload
        }
        
        with self._lock:
            self._assigned_fingerprints.add(fp)
            if event_id:
                self._assigned_event_ids.add(str(event_id).strip())
            
            if pid_clean not in self._patient_history:
                self._patient_history[pid_clean] = []
            self._patient_history[pid_clean].append(entry)
            self._latest_decision_cache[pid_clean] = decision_payload
            self._dirty = True

        # Persist to disk
        self.save_ledger()

    def get_latest_decision(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the latest cached decision for a patient."""
        with self._lock:
            return self._latest_decision_cache.get(str(patient_id).strip())

    def get_all_patient_decisions(self) -> Dict[str, Dict[str, Any]]:
        """Returns the in-memory dictionary of all patient latest decisions."""
        with self._lock:
            return dict(self._latest_decision_cache)

    def get_ledger_summary(self) -> Dict[str, Any]:
        """Returns statistical summary of recorded assignments."""
        with self._lock:
            return {
                "total_unique_patients": len(self._patient_history),
                "total_unique_assignments": len(self._assigned_fingerprints),
                "total_recorded_events": len(self._assigned_event_ids),
                "ledger_file": str(self.ledger_path)
            }

    def clear_ledger(self):
        """Clears all assignment history (for testing or clinical resets)."""
        with self._lock:
            self._patient_history.clear()
            self._assigned_fingerprints.clear()
            self._assigned_event_ids.clear()
            self._latest_decision_cache.clear()
            self._dirty = True
        self.save_ledger()


# Global Singleton Ledger Instance
assignment_ledger = VideoAssignmentLedger()
