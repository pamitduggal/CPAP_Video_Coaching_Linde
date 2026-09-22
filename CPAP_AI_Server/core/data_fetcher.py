"""
SleepCare AI Server - REST API Streaming Data Fetcher
=====================================================
This module handles downloading clinical datasets from the central backend REST API.
It features:
- Streaming chunk downloads with a terminal progress bar.
- Automatic since_date optimization for large tables (e.g. cpap-usage with 15M+ rows).
- Graceful error recovery returning empty DataFrames when offline.
"""

import os
import sys
import time
import json
import logging
import requests
import pandas as pd
from typing import Optional

from core.config import API_BASE, HEADERS

logger = logging.getLogger("CPAP_AI_Server")


def fetch_dataset(
    endpoint_name: str,
    patient_id: Optional[int] = None,
    limit: Optional[int] = None,
    since_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Downloads clinical data from a backend REST endpoint with live progress reporting.

    Parameters:
    - endpoint_name: The REST resource path (e.g. 'cpap-usage', 'interventions').
    - patient_id: Optional filter for a specific patient ID.
    - limit: Optional row limit for test batches.
    - since_date: Optional cutoff date string (e.g. '2024-01-01') to avoid downloading ancient data.

    Returns:
    - pd.DataFrame containing the downloaded records, or an empty DataFrame on failure.
    """
    url = f"{API_BASE}/{endpoint_name}"
    params = {}
    
    if patient_id is not None:
        params["patient_id"] = patient_id
    if limit is not None:
        params["limit"] = limit
    if since_date is not None:
        params["since_date"] = since_date
    elif endpoint_name == "cpap-usage":
        # Default cutoff date prevents backend database query timeouts on 15.5M row CPAP usage tables
        params["since_date"] = os.environ.get("CPAP_SINCE_DATE", "2024-01-01")

    try:
        start_time = time.time()
        print(f"\n[API FETCHING] Downloading '{endpoint_name}' from {url}...")
        response = requests.get(url, headers=HEADERS, params=params, stream=True, timeout=120)

        if response.status_code == 200:
            total_size = int(response.headers.get("content-length", 0))
            chunks = []
            downloaded = 0

            # Read stream in 64KB blocks while updating the ASCII progress bar
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100.0
                        bar_length = 30
                        filled = int(bar_length * downloaded // total_size)
                        bar = "=" * filled + "-" * (bar_length - filled)
                        mb = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r [{bar}] {percent:5.1f}% ({mb:.2f} MB)")
                    else:
                        mb = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r Downloading: {mb:.2f} MB...")
                    sys.stdout.flush()

            sys.stdout.write("\n")
            elapsed = time.time() - start_time
            print(f"[API FETCH SUCCESS] '{endpoint_name}' downloaded cleanly ({downloaded / (1024 * 1024):.2f} MB in {elapsed:.1f}s)")

            raw_content = b"".join(chunks).decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    return pd.DataFrame(parsed)
                elif isinstance(parsed, dict):
                    for envelope_key in ("data", "records", "items", "results"):
                        if envelope_key in parsed and isinstance(parsed[envelope_key], list):
                            return pd.DataFrame(parsed[envelope_key])
                    return pd.DataFrame([parsed])
                else:
                    return pd.DataFrame()
            except json.JSONDecodeError as j_err:
                print(f"[API JSON DECODE ERROR] {endpoint_name}: {j_err}")
                return pd.DataFrame()
        else:
            print(f"[API ERROR {response.status_code}] Failed to fetch {endpoint_name}: {response.text[:200]}")
    except Exception as exc:
        print(f"\n[API CONNECTION FAILED] {endpoint_name}: {exc}")

    # Return empty DataFrame if download failed so callers can fall back to local disk files
    return pd.DataFrame()
