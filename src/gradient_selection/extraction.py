from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd
from openai import OpenAI

from .config import Config
from .llm import _extract_with_retry, _load_prompt


_EXPECTED_CT_KEYS = ["CT_Regions", "CT_Contrast_Agent", "Lung_Nodules"]
_EXPECTED_PET_KEYS = [
    "Lung_Hypermetabolic_Regions",
    "Lymph_Nodes_Hypermetabolic_Regions",
    "Other_Hypermetabolic_Regions",
    "PET_Tracer",
    "PET_Scan_Region",
    "PET_Blood_Glucose_Level",
    "PET_Waiting_Time",
    "Clinical_Reason",
    "Primary_Diagnosis",
]


def _normalize_json_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return value


def _ordered_keys(values: list[Dict[str, Any]], expected: list[str]) -> list[str]:
    discovered = {key for item in values for key in item.keys()}
    extras = sorted([key for key in discovered if key not in expected])
    return [key for key in expected if key in discovered] + extras


def _extract_pair(
    client: OpenAI,
    ct_prompt: str,
    pet_prompt: str,
    ct_report: str,
    pt_report: str,
    cfg: Config,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ct_json = _extract_with_retry(client, prompt=ct_prompt, report_text=ct_report, cfg=cfg)
    pet_json = _extract_with_retry(client, prompt=pet_prompt, report_text=pt_report, cfg=cfg)
    return ct_json, pet_json


def run_extraction(
    df: pd.DataFrame,
    cfg: Config,
    *,
    ct_prompt_path: str,
    pet_prompt_path: str,
    output_dir: Path,
    max_rows: int | None = None,
) -> pd.DataFrame:
    api_key = cfg.llm.get("api_key")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    ct_prompt = _load_prompt(ct_prompt_path)
    pet_prompt = _load_prompt(pet_prompt_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ct_out_dir = output_dir / "ct"
    pet_out_dir = output_dir / "pet"
    ct_out_dir.mkdir(parents=True, exist_ok=True)
    pet_out_dir.mkdir(parents=True, exist_ok=True)

    max_workers = int(cfg.llm.get("concurrency", 6))

    if max_rows:
        df = df.head(max_rows)

    results = []

    client = OpenAI(api_key=api_key)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for idx, row in df.iterrows():
            futures[executor.submit(
                _extract_pair,
                client,
                ct_prompt,
                pet_prompt,
                str(row.get("ct_report", "")),
                str(row.get("pt_report", "")),
                cfg,
            )] = idx

        for future in as_completed(futures):
            idx = futures[future]
            ct_json, pet_json = {}, {}
            error = ""
            try:
                ct_json, pet_json = future.result()
            except Exception as exc:  # noqa: BLE001
                error = str(exc)

            results.append((idx, ct_json, pet_json, error))

    # attach results in original order
    results_sorted = sorted(results, key=lambda x: x[0])
    ct_jsons = []
    pet_jsons = []
    errors = []

    for _, ct_json, pet_json, error in results_sorted:
        ct_jsons.append(ct_json)
        pet_jsons.append(pet_json)
        errors.append(error)

    out_df = df.copy()
    out_df["ct_json"] = [json.dumps(x) for x in ct_jsons]
    out_df["pet_json"] = [json.dumps(x) for x in pet_jsons]
    out_df["extraction_error"] = errors

    ct_keys = _ordered_keys(ct_jsons, _EXPECTED_CT_KEYS)
    pet_keys = _ordered_keys(pet_jsons, _EXPECTED_PET_KEYS)

    for key in ct_keys:
        out_df[f"ct_{key}"] = [_normalize_json_value(item.get(key)) for item in ct_jsons]
    for key in pet_keys:
        out_df[f"pet_{key}"] = [_normalize_json_value(item.get(key)) for item in pet_jsons]

    # write raw JSON artifacts per study
    for _, row in out_df.iterrows():
        ct_uid = row.get("ct_study_uid", "unknown")
        pt_uid = row.get("pt_study_uid", "unknown")
        ct_path = ct_out_dir / f"{ct_uid}.json"
        pet_path = pet_out_dir / f"{pt_uid}.json"
        ct_path.write_text(row["ct_json"])
        pet_path.write_text(row["pet_json"])

    return out_df
