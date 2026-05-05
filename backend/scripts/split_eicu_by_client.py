"""
Split the eICU dataset into per-client raw CSV files.

Reads patient.csv.gz, vitalPeriodic.csv.gz, and treatment.csv.gz from the eICU
dataset, groups by hospitalid, and writes per client:

    data/raw/client_{id}/patients.csv   — patient metadata (no outcome label)
    data/raw/client_{id}/vitals.csv     — time-series vitals (11 features)
    data/raw/client_{id}/treatment.csv  — raw treatment records per stay

Hospitals are included only if they have at least ``min_patients`` stays and at
least ``min_positive_windows`` positive sliding windows under the same labeling
rules as ``app.data.preprocessor.preprocess_client_data``.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.data.preprocessor import count_positive_training_windows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("split_eicu")

PATIENT_COL = "patientunitstayid"
HOSPITAL_COL = "hospitalid"

PATIENT_COLS = [
    PATIENT_COL,
    HOSPITAL_COL,
    "unitdischargestatus",
    "age",
    "gender",
    "unittype",
]

VITAL_FEATURES = [
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
VITAL_COLS = [PATIENT_COL, "observationoffset"] + VITAL_FEATURES


def split_eicu(
    min_patients: int = 30,
    min_positive_windows: int = 1,
    data_dir: str | None = None,
    output_dir: str | None = None,
):
    data_path = Path(data_dir) if data_dir else Path(settings.data_dir)
    out_path = Path(output_dir) if output_dir else Path(settings.raw_client_data_dir)

    logger.info("Loading patient data from %s ...", data_path)
    patients = pd.read_csv(
        data_path / "patient.csv.gz",
        compression="gzip",
        usecols=PATIENT_COLS,
    )
    logger.info(
        "  %d patient stays across %d hospitals",
        len(patients),
        patients[HOSPITAL_COL].nunique(),
    )

    logger.info("Loading vital signs from %s ...", data_path)
    vitals = pd.read_csv(
        data_path / "vitalPeriodic.csv.gz",
        compression="gzip",
        usecols=VITAL_COLS,
    )
    logger.info("  %d vital records", len(vitals))
    treatment_path = data_path / "treatment.csv.gz"
    if treatment_path.exists():
        logger.info("Loading treatment records from %s ...", treatment_path)
        treatments = pd.read_csv(
            treatment_path,
            compression="gzip",
            usecols=["patientunitstayid", "treatmentoffset", "treatmentstring"],
            low_memory=False,
        )
        logger.info("  %d treatment records", len(treatments))
    else:
        logger.warning(
            "treatment.csv.gz not found at %s — treatment.csv files will be empty",
            data_path,
        )
        treatments = pd.DataFrame(
            columns=["patientunitstayid", "treatmentoffset", "treatmentstring"]
        )

    hospital_patient_counts = patients.groupby(HOSPITAL_COL)[PATIENT_COL].nunique()
    candidates = hospital_patient_counts.index[hospital_patient_counts >= min_patients]

    eligible: list[int] = []
    for hid in sorted(candidates.astype(int)):
        client_patients = patients[patients[HOSPITAL_COL] == hid]
        client_patient_ids = set(client_patients[PATIENT_COL].astype(int))
        client_vitals = vitals[vitals[PATIENT_COL].isin(client_patient_ids)]
        client_treatments = treatments[
            treatments[PATIENT_COL].isin(client_patient_ids)
        ].copy()
        n_pos, _ = count_positive_training_windows(
            client_patients,
            client_vitals,
            client_treatments,
        )
        if n_pos >= min_positive_windows:
            eligible.append(int(hid))

    logger.info(
        "  %d hospitals with >= %d patients and >= %d positive training windows "
        "(same rules as preprocess_client_data)",
        len(eligible),
        min_patients,
        min_positive_windows,
    )

    written = 0
    for hid in sorted(eligible):
        client_dir = out_path / f"client_{hid}"
        client_dir.mkdir(parents=True, exist_ok=True)

        client_patients = patients[patients[HOSPITAL_COL] == hid].copy()
        client_patient_ids = set(client_patients[PATIENT_COL].astype(int))

        patient_out = client_patients[PATIENT_COLS].drop_duplicates(subset=[PATIENT_COL])
        patient_out.to_csv(client_dir / "patients.csv", index=False)

        client_vitals = vitals[vitals[PATIENT_COL].isin(client_patient_ids)].copy()
        vital_out_cols = [PATIENT_COL, "observationoffset"] + VITAL_FEATURES
        for c in vital_out_cols:
            if c not in client_vitals.columns:
                client_vitals[c] = float("nan")
        client_vitals[vital_out_cols].to_csv(client_dir / "vitals.csv", index=False)

        client_treatments = treatments[
            treatments[PATIENT_COL].isin(client_patient_ids)
        ].copy()
        client_treatments.to_csv(client_dir / "treatment.csv", index=False)

        written += 1
        if written % 20 == 0:
            logger.info("  Written %d / %d clients...", written, len(eligible))

    logger.info("Done. %d client directories written to %s", written, out_path)


def main():
    parser = argparse.ArgumentParser(
        description="Split eICU dataset into per-client raw CSVs"
    )
    parser.add_argument(
        "--min-patients",
        type=int,
        default=30,
        help="Min patients per client to include",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to eICU dataset (default: from config)",
    )
    parser.add_argument(
        "--min-positive-windows",
        type=int,
        default=1,
        help="Min positive sliding windows per hospital (labeling matches preprocess_client_data)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: data/raw)",
    )
    args = parser.parse_args()

    split_eicu(
        min_patients=args.min_patients,
        min_positive_windows=args.min_positive_windows,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
