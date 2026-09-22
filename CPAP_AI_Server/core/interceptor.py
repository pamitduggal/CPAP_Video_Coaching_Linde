"""
SleepCare AI Server - Smart CSV Interceptor & Runtime Compatibility Hooks
=========================================================================
This module enables seamless virtualization of data loading:
1. `smart_read_csv`: Transparently intercepts `pd.read_csv(...)`, fetching live data from
   the backend REST API first, then falling back to local files in data/ or artifacts/.
2. `find_artifact_file`: Finds generated outputs across subfolders.
3. `load_cached_csv`: Lightweight mtime-based cache to eliminate redundant disk reads on large CSVs.
4. Runtime compatibility hooks for Pandas 2.x, CatBoost, and LightGBM so the M4
   Jupyter notebook runs smoothly without crashing.
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional, Dict, Tuple

from core.config import ENDPOINT_MAP
from core.registry import MODEL_HEALTH, state_lock
from core.data_fetcher import fetch_dataset
from core.preprocessor import _process_dataset

logger = logging.getLogger("CPAP_AI_Server")

# Store the unpatched original pd.read_csv
_original_read_csv = pd.read_csv

# In-memory CSV cache: {filepath: (mtime, DataFrame)}
_CSV_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}


def find_artifact_file(filename: str) -> str:
    """
    Searches for a file across the most common project directories:
    root, artifacts/, outputs/, reports/, data/, scripts/, and notebooks/.
    """
    if not filename:
        return filename

    search_folders = ["", "artifacts", "outputs", "reports", "data", "scripts", "notebooks"]
    for folder in search_folders:
        path = os.path.join(folder, filename) if folder else filename
        if os.path.exists(path):
            return path

    return filename


def load_cached_csv(filename: str) -> pd.DataFrame:
    """
    Loads a CSV file with an in-memory mtime cache.
    If the file on disk hasn't changed since last read, returns the cached DataFrame
    instantly, avoiding slow 10MB+ disk reads on rapid HTTP requests.
    """
    resolved_path = find_artifact_file(filename)
    if not os.path.exists(resolved_path):
        return pd.DataFrame()

    try:
        current_mtime = os.path.getmtime(resolved_path)
        if resolved_path in _CSV_CACHE:
            cached_mtime, cached_df = _CSV_CACHE[resolved_path]
            if cached_mtime == current_mtime:
                return cached_df

        df = _original_read_csv(resolved_path)
        _CSV_CACHE[resolved_path] = (current_mtime, df)
        return df
    except Exception as exc:
        logger.warning(f"[CACHE READ ERROR] Could not read {resolved_path}: {exc}")
        return pd.DataFrame()


def smart_read_csv(filepath_or_buffer, *args, **kwargs):
    """
    Smart replacement for pandas.read_csv:
    1. If the requested file matches one of the 12 clinical backend endpoints,
       it attempts to stream live data from the backend REST API first.
    2. If the API returns valid data, it post-processes and returns it.
    3. If the API is offline or returns empty, it falls back to the local file
       (searching both the exact path and subdirectories like data/ or artifacts/).
    """
    if isinstance(filepath_or_buffer, str):
        clean_name = os.path.basename(filepath_or_buffer).strip("\"'").lower()
        canonical_name = clean_name.replace(" ", "_")
        endpoint_name = ENDPOINT_MAP.get(clean_name) or ENDPOINT_MAP.get(canonical_name)

        # 1. Try Live Backend API
        if endpoint_name:
            df = fetch_dataset(endpoint_name)
            if not df.empty:
                return _process_dataset(df, endpoint_name)

        # 2. Check exact local path
        if os.path.exists(filepath_or_buffer):
            local_df = _original_read_csv(filepath_or_buffer, *args, **kwargs)
            return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

        # 3. Check standard project subfolders (data/, artifacts/, etc.)
        subfolders = ["artifacts", "outputs", "data", "reports", "notebooks", "scripts"]
        for folder in subfolders:
            candidate = os.path.join(folder, os.path.basename(filepath_or_buffer))
            if os.path.exists(candidate):
                local_df = _original_read_csv(candidate, *args, **kwargs)
                return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

            # Check alternative naming with spaces vs underscores
            alt_name = clean_name.replace("_", " ") if "_" in clean_name else clean_name.replace(" ", "_")
            alt_candidate = os.path.join(folder, alt_name)
            if os.path.exists(alt_candidate):
                local_df = _original_read_csv(alt_candidate, *args, **kwargs)
                return _process_dataset(local_df, endpoint_name) if endpoint_name else local_df

    # Fallback to standard pandas read_csv for buffers or unmapped files
    return _original_read_csv(filepath_or_buffer, *args, **kwargs)


# ==============================================================================
# Smart DataFrame.to_csv Interceptor (Saves Pipeline Artifacts to artifacts/)
# ==============================================================================
_original_to_csv = pd.DataFrame.to_csv

KNOWN_ARTIFACT_FILENAMES = {
    "baselines.csv", "bio_features.csv", "bio_layer2_states.csv", "care_features.csv",
    "cpap_clustering_summary.csv", "cpap_features.csv", "cpap_layer2_clusters.csv",
    "features_merged.csv", "features_with_evidence.csv", "layer0_results.csv",
    "layer3_results.csv", "layer4_triplets.csv", "layer5_recommendations.csv",
    "layer6_events.csv", "patient_action_plan.csv", "survey_features.csv",
    "survey_layer2_states.csv"
}


def smart_to_csv(self, path_or_buf=None, *args, **kwargs):
    """
    Smart replacement for DataFrame.to_csv:
    Automatically redirects model pipeline CSV outputs to the 'artifacts/' folder,
    keeping the root project directory clean and organized.
    """
    if isinstance(path_or_buf, str):
        basename = os.path.basename(path_or_buf).strip("\"'").lower()
        has_dir = bool(os.path.dirname(path_or_buf))
        if basename in KNOWN_ARTIFACT_FILENAMES or (not has_dir and basename.endswith(".csv")):
            os.makedirs("artifacts", exist_ok=True)
            target_path = os.path.join("artifacts", os.path.basename(path_or_buf))
            return _original_to_csv(self, target_path, *args, **kwargs)

    return _original_to_csv(self, path_or_buf, *args, **kwargs)


# ==============================================================================
# Runtime Compatibility Fixes for Pandas 2.x & ML Models
# ==============================================================================
_orig_series_clip = pd.Series.clip

def _safe_series_clip(self, lower=None, upper=None, *args, **kwargs):
    """
    Fixes a Pandas 2.0+ bug where calling .clip() on datetime-like series with
    integer bounds raises a TypeError. Converts to numeric values first if needed.
    """
    if np.issubdtype(self.dtype, np.datetime64) and (isinstance(lower, (int, float)) or isinstance(upper, (int, float))):
        converted = pd.to_numeric(self, errors="coerce").fillna(0).astype(int)
        return _orig_series_clip(converted, lower=lower, upper=upper, *args, **kwargs)
    return _orig_series_clip(self, lower=lower, upper=upper, *args, **kwargs)


def _patch_catboost():
    """
    Patches CatBoostClassifier to prevent crashes when training on filtered
    cohort subsets that have only 1 target class or zero feature variance.
    """
    try:
        from catboost import CatBoostClassifier
        _orig_cat_fit = CatBoostClassifier.fit

        def _safe_cat_fit(self, X, y=None, *args, **kwargs):
            if y is not None and len(np.unique(y)) <= 1:
                self._is_dummy = True
                self._dummy_class = int(np.unique(y)[0])
                with state_lock:
                    MODEL_HEALTH["catboost_dummy_fallback"] = True
                    warn_msg = f"CatBoostClassifier single-class training detected (y={np.unique(y)}). Degraded to constant dummy predictor Class {self._dummy_class}."
                    if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                        MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                        logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")
                return self
            try:
                return _orig_cat_fit(self, X, y, *args, **kwargs)
            except Exception as e:
                if "constant or ignored" in str(e) or "All features are either constant" in str(e):
                    self._is_dummy = True
                    self._dummy_class = int(y[0]) if y is not None and len(y) > 0 else 0
                    with state_lock:
                        MODEL_HEALTH["catboost_dummy_fallback"] = True
                        warn_msg = f"CatBoostClassifier zero-variance feature error caught ({e}). Degraded to constant dummy predictor Class {self._dummy_class}."
                        if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                            MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                            logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")
                    return self
                raise

        _orig_cat_predict = CatBoostClassifier.predict

        def _safe_cat_predict(self, X, *args, **kwargs):
            if getattr(self, "_is_dummy", False):
                n = len(X) if hasattr(X, "__len__") else 1
                return np.full(n, getattr(self, "_dummy_class", 0))
            return _orig_cat_predict(self, X, *args, **kwargs)

        _orig_cat_proba = CatBoostClassifier.predict_proba

        def _safe_cat_predict_proba(self, X, *args, **kwargs):
            if getattr(self, "_is_dummy", False):
                n = len(X) if hasattr(X, "__len__") else 1
                res = np.zeros((n, 4))
                res[:, getattr(self, "_dummy_class", 0)] = 1.0
                return res
            return _orig_cat_proba(self, X, *args, **kwargs)

        CatBoostClassifier.fit = _safe_cat_fit
        CatBoostClassifier.predict = _safe_cat_predict
        CatBoostClassifier.predict_proba = _safe_cat_predict_proba
    except ImportError:
        pass


def _patch_lightgbm():
    """
    Patches LightGBM to prevent C++ assertion errors when all histogram bins
    are pruned on zero-variance feature sets.
    """
    try:
        import lightgbm as lgb
        _orig_lgb_train = lgb.train

        def _safe_lgb_train(params, train_set, *args, **kwargs):
            try:
                return _orig_lgb_train(params, train_set, *args, **kwargs)
            except Exception as e:
                if "num_features" in str(e) or "Check failed" in str(e):
                    with state_lock:
                        MODEL_HEALTH["lightgbm_dummy_fallback"] = True
                        warn_msg = f"LightGBM zero-feature training error caught ({e}). Degraded to DummyLGBBooster (constant 0.05)."
                        if warn_msg not in MODEL_HEALTH["degraded_warnings"]:
                            MODEL_HEALTH["degraded_warnings"].append(warn_msg)
                            logger.warning(f"[AI MODEL DEGRADATION WARNING] {warn_msg}")

                    class DummyLGBBooster:
                        def predict(self, data, *a, **k):
                            n = len(data) if hasattr(data, "__len__") else 1
                            return np.full(n, 0.05)

                    return DummyLGBBooster()
                raise

        lgb.train = _safe_lgb_train
    except ImportError:
        pass


def apply_runtime_patches():
    """Applies all smart interceptors and library compatibility patches."""
    pd.read_csv = smart_read_csv
    pd.DataFrame.to_csv = smart_to_csv
    pd.Series.clip = _safe_series_clip
    _patch_catboost()
    _patch_lightgbm()
