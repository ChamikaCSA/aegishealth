"""Shared configuration for critical event extraction.

Treatment rows are matched with substring search on lowercased
``treatmentstring`` (see ``preprocessor._build_event_onset_map``).
Keywords focus on acute hemodynamic and respiratory deterioration signals
that can plausibly be anticipated from periodic vitals.
"""

from __future__ import annotations

import pandas as pd

CRITICAL_EVENT_KEYWORDS: tuple[str, ...] = (
    "vasopressor",
    "vasopressors",
    "norepinephrine",
    "epinephrine",
    "phenylephrine",
    "vasopressin",
    "dobutamine",
    "dopamine <=",
    "dopamine >",
    "dopamine  5-15",
    "dopamine 5-15",
    "milrinone",
    "isoproterenol",
    "cardioversion",
    "cardiac defibrillation",
    "defibrillation",
    "overdrive pacing",
    "shock",
    "mechanical ventilation",
    "reintubation",
    "endotracheal tube",
    "non-invasive ventilation",
    "cpap/peep therapy",
    "oxygen therapy (> 60%)",
    "dialysis",
    "hemodialysis",
    "peritoneal dialysis",
)

CRITICAL_EVENT_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "endotracheal tube removal",
    "reduce cpap as tolerated",
    "reduce peep as tolerated",
    "ventilator weaning",
    "dialysis access surgery",
    "insertion of catheter for peritoneal dialysis",
    "insertion of venous catheter for hemodialysis",
    "arteriovenous shunt for renal dialysis",
    "procedure on upper respiratory tract - not tracheostomy",
)


def critical_event_treatment_mask(treatmentstring: pd.Series) -> pd.Series:
    """True where a treatment row counts toward critical-event onset."""
    ts = treatmentstring.astype(str).str.lower()
    mask = pd.Series(False, index=treatmentstring.index, dtype=bool)
    for keyword in CRITICAL_EVENT_KEYWORDS:
        mask = mask | ts.str.contains(keyword, na=False, regex=False)
    exclude_mask = pd.Series(False, index=treatmentstring.index, dtype=bool)
    for keyword in CRITICAL_EVENT_EXCLUDE_KEYWORDS:
        exclude_mask = exclude_mask | ts.str.contains(keyword, na=False, regex=False)
    return mask & ~exclude_mask
