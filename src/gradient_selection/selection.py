from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import pandas as pd

from .config import Config


_ALLOWED_DIAGNOSES = {"Primary Lung Cancer", "No Cancer"}
_ALLOWED_REASONS = {"Indeterminate Pulmonary Nodule"}


def _parse_json_cell(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value))
    except Exception:  # noqa: BLE001
        return {}


def _list_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return len(parsed) == 0
    except Exception:  # noqa: BLE001
        pass
    return False


def _contains_chest(regions: List[str]) -> bool:
    for r in regions:
        if "chest" in r.lower():
            return True
    return False


def evaluate_row(row: pd.Series, cfg: Config) -> Tuple[bool, List[str]]:
    reasons = []

    if row.get("extraction_error"):
        reasons.append("extraction_error")
        return False, reasons

    ct = _parse_json_cell(row.get("ct_json"))
    pet = _parse_json_cell(row.get("pet_json"))

    ct_regions = ct.get("CT_Regions", [])
    ct_contrast = ct.get("CT_Contrast_Agent", "")
    lung_nodules = ct.get("Lung_Nodules", [])

    if not _contains_chest(ct_regions):
        reasons.append("ct_not_chest")
    if str(ct_contrast).strip().lower() != "none":
        reasons.append("ct_contrast_present")
    if not lung_nodules or lung_nodules == []:
        reasons.append("no_lung_nodules")

    clinical_reason = pet.get("Clinical_Reason", "")
    primary_dx = pet.get("Primary_Diagnosis", "")

    lymph_nodes = pet.get("Lymph_Nodes_Hypermetabolic_Regions", [])
    other_hyper = pet.get("Other_Hypermetabolic_Regions", [])

    if clinical_reason not in _ALLOWED_REASONS:
        reasons.append("pet_reason_not_indeterminate_nodule")
    if primary_dx not in _ALLOWED_DIAGNOSES:
        reasons.append("pet_primary_dx_not_allowed")
    if not _list_empty(lymph_nodes):
        reasons.append("pet_lymph_hypermetabolic")
    if not _list_empty(other_hyper):
        reasons.append("pet_other_hypermetabolic")

    return len(reasons) == 0, reasons


def apply_selection(df: pd.DataFrame, cfg: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    selected_rows = []
    audit_rows = []

    for _, row in df.iterrows():
        include, reasons = evaluate_row(row, cfg)
        audit_rows.append({
            "pt_study_uid": row.get("pt_study_uid"),
            "ct_study_uid": row.get("ct_study_uid"),
            "patient_id": row.get("patient_id"),
            "selected": include,
            "reasons": ";".join(reasons),
        })
        if include:
            selected_rows.append(row)

    selected_df = pd.DataFrame(selected_rows)
    audit_df = pd.DataFrame(audit_rows)
    return selected_df, audit_df
