"""
Preprocess raw per-client CSVs into LSTM-ready numpy arrays.

Reads patients.csv, vitals.csv, and events.csv from a client directory,
builds sliding-window time-series sequences, and labels each window
based on whether a critical event (vasopressor or mechanical ventilation
onset) occurs within the next ``prediction_horizon`` minutes.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)

VITAL_FEATURES: list[str] = [
    "heartrate",
    "respiration",
    "sao2",
    "temperature",
    "systemicsystolic",
    "systemicdiastolic",
    "systemicmean",
    "cvp",
    "st1",
    "st2",
    "st3",
]

PATIENT_ID_COL = "patientunitstayid"


def preprocess_client_data(
    client_dir: Path,
    seq_len: int | None = None,
    prediction_horizon: int | None = None,
    window_stride: int | None = None,
    max_neg_per_patient: int | None = None,
) -> tuple[np.ndarray, np.ndarray, int]:
    """
    Transform raw CSVs into LSTM-ready (X, y, n_features).

    Produces sliding-window samples labeled with a 6-hour (default)
    prediction horizon for critical-event onset.

    Parameters
    ----------
    client_dir : Path
        Directory containing ``patients.csv``, ``vitals.csv``, and
        ``events.csv``.
    seq_len : int, optional
        Number of time-steps per window.  Falls back to
        ``settings.sequence_length`` (default 24).
    prediction_horizon : int, optional
        Minutes ahead to look for a critical event (default 360 = 6 h).
    window_stride : int, optional
        Step size in observations between consecutive windows (default 6).
    max_neg_per_patient : int, optional
        Cap on label-0 windows kept per patient to limit class imbalance.

    Returns
    -------
    X : np.ndarray, shape (n_windows, seq_len, n_features)
    y : np.ndarray, shape (n_windows,)
    n_features : int
    """
    if seq_len is None:
        seq_len = settings.sequence_length
    if prediction_horizon is None:
        prediction_horizon = settings.prediction_horizon_minutes
    if window_stride is None:
        window_stride = settings.window_stride
    if max_neg_per_patient is None:
        max_neg_per_patient = settings.max_neg_windows_per_patient

    n_features = len(VITAL_FEATURES)
    empty = (
        np.empty((0, seq_len, n_features)),
        np.empty(0, dtype=np.int64),
        n_features,
    )

    patients_path = client_dir / "patients.csv"
    vitals_path = client_dir / "vitals.csv"
    events_path = client_dir / "events.csv"

    if not patients_path.exists() or not vitals_path.exists():
        logger.warning("Missing CSV files in %s", client_dir)
        return empty

    patients = pd.read_csv(patients_path)
    vitals = pd.read_csv(vitals_path)

    if patients.empty or vitals.empty:
        logger.warning("Empty CSV files in %s", client_dir)
        return empty

    # Build event-onset lookup {patient_id: event_offset_minutes}
    event_map: dict[int, float] = {}
    if events_path.exists():
        events = pd.read_csv(events_path)
        if not events.empty:
            for _, row in events.iterrows():
                event_map[int(row[PATIENT_ID_COL])] = float(row["event_offset"])

    valid_pids = set(patients[PATIENT_ID_COL]) & set(vitals[PATIENT_ID_COL])
    vitals = vitals[vitals[PATIENT_ID_COL].isin(valid_pids)]

    if len(valid_pids) == 0:
        logger.warning("No patients with vitals in %s", client_dir)
        return empty

    vitals = vitals.sort_values([PATIENT_ID_COL, "observationoffset"])

    for feat in VITAL_FEATURES:
        if feat not in vitals.columns:
            vitals[feat] = np.nan

    vitals[VITAL_FEATURES] = (
        vitals.groupby(PATIENT_ID_COL)[VITAL_FEATURES]
        .transform(lambda s: s.ffill().bfill())
    )
    vitals[VITAL_FEATURES] = vitals[VITAL_FEATURES].fillna(0.0)

    means = vitals[VITAL_FEATURES].mean()
    stds = vitals[VITAL_FEATURES].std().fillna(1.0)
    stds = stds.mask(stds < 1e-8, 1.0)

    sequences: list[np.ndarray] = []
    labels: list[int] = []
    rng = np.random.default_rng(42)

    for pid in sorted(valid_pids):
        g = vitals[vitals[PATIENT_ID_COL] == pid].sort_values("observationoffset")
        if len(g) < seq_len:
            continue

        offsets = g["observationoffset"].to_numpy(dtype=np.float64)
        arr = g[VITAL_FEATURES].to_numpy(dtype=np.float64)
        arr = (arr - means.to_numpy()) / stds.to_numpy()

        t_event = event_map.get(int(pid))
        pos_idx: list[int] = []
        neg_idx: list[int] = []
        window_meta: list[tuple[int, int]] = []  # (label, index in pending list)

        pending: list[np.ndarray] = []
        start = 0
        while start + seq_len <= len(arr):
            t_end = float(offsets[start + seq_len - 1])
            window = arr[start : start + seq_len]

            if t_event is not None:
                if t_end >= t_event:
                    start += window_stride
                    continue
                if t_event - prediction_horizon <= t_end < t_event:
                    lab = 1
                else:
                    lab = 0
            else:
                lab = 0

            idx = len(pending)
            pending.append(window)
            window_meta.append((lab, idx))
            if lab == 1:
                pos_idx.append(idx)
            else:
                neg_idx.append(idx)

            start += window_stride

        keep: set[int] = set(pos_idx)
        if neg_idx:
            if len(neg_idx) <= max_neg_per_patient:
                keep.update(neg_idx)
            else:
                chosen = rng.choice(
                    neg_idx, size=max_neg_per_patient, replace=False
                )
                keep.update(int(x) for x in chosen)

        for lab, idx in window_meta:
            if idx in keep:
                sequences.append(pending[idx])
                labels.append(lab)

    if not sequences:
        logger.warning("No sliding windows in %s", client_dir)
        return empty

    X = np.stack(sequences, axis=0).astype(np.float32)
    y = np.array(labels, dtype=np.int64)
    rate = float(y.mean()) if len(y) else 0.0
    logger.info(
        "Preprocessed %s: %d windows, event_rate=%.4f",
        client_dir.name,
        len(y),
        rate,
    )
    return X, y, n_features
