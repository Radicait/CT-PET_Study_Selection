from __future__ import annotations

import os
import re
from typing import List, Optional

import pandas as pd
from google.cloud import bigquery

from .config import Config


def _regex_union(terms: List[str]) -> str:
    escaped = [re.escape(t.strip().upper()) for t in terms if t.strip()]
    if not escaped:
        return ""
    return "(" + "|".join(escaped) + ")"


def build_candidate_pairs_query(cfg: Config, *, sample_limit: Optional[int] = None) -> str:
    selection = cfg.selection

    pet_terms = selection.get("pet_report_terms", [])
    ct_chest_terms = selection.get("ct_chest_terms", [])
    ct_noncontrast_terms = selection.get("ct_noncontrast_terms", [])
    ct_with_contrast_terms = selection.get("ct_with_contrast_terms", [])
    ct_exclude_terms = selection.get("ct_exclude_terms", [])
    max_days = int(selection.get("max_days", 60))

    pet_regex = _regex_union(pet_terms)
    chest_regex = _regex_union(ct_chest_terms)
    noncontrast_regex = _regex_union(ct_noncontrast_terms)
    with_contrast_regex = _regex_union(ct_with_contrast_terms)
    exclude_regex = _regex_union(ct_exclude_terms)

    dataset = cfg.bigquery.get("dataset")
    table = cfg.bigquery.get("table")
    if not dataset or not table:
        raise ValueError("bigquery.dataset and bigquery.table are required")

    limit_clause = f"LIMIT {sample_limit}" if sample_limit else ""

    return f"""
WITH study_mods AS (
  SELECT
    study_uid,
    patient_id,
    study_date,
    ARRAY_AGG(DISTINCT s.modality) AS modalities
  FROM `{cfg.bigquery.get('project')}.{dataset}.{table}`, UNNEST(series) AS s
  GROUP BY study_uid, patient_id, study_date
),
petct AS (
  SELECT study_uid, patient_id, study_date
  FROM study_mods
  WHERE 'PT' IN UNNEST(modalities)
    AND 'CT' IN UNNEST(modalities)
),
petct_dates AS (
  SELECT
    t.study_uid,
    t.patient_id,
    COALESCE(MAX(CASE WHEN s.modality='PT' THEN s.acquisition_date END), t.study_date) AS pet_date,
    t.deid_english_report AS pt_report
  FROM `{cfg.bigquery.get('project')}.{dataset}.{table}` t
  JOIN petct p ON p.study_uid = t.study_uid
  JOIN UNNEST(t.series) AS s
  GROUP BY t.study_uid, t.patient_id, t.study_date, t.deid_english_report
),
ct_only AS (
  SELECT
    t.study_uid,
    t.patient_id,
    t.study_date,
    t.deid_english_report AS ct_report,
    s.acquisition_date AS ct_acq_date,
    s.series_description,
    s.body_part_examined
  FROM `{cfg.bigquery.get('project')}.{dataset}.{table}` t
  JOIN study_mods m ON m.study_uid = t.study_uid
  JOIN UNNEST(t.series) AS s
  WHERE ARRAY_LENGTH(m.modalities) = 1
    AND m.modalities[OFFSET(0)] = 'CT'
    AND s.modality = 'CT'
),
ct_only_agg AS (
  SELECT
    study_uid,
    patient_id,
    COALESCE(MAX(ct_acq_date), MAX(study_date)) AS ct_date,
    ANY_VALUE(ct_report) AS ct_report,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(body_part_examined), r'{chest_regex}')) AS body_part_chest,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'{chest_regex}')) AS report_chest,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'{exclude_regex}')) AS report_screen,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'{with_contrast_regex}')) AS report_with_contrast,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'{noncontrast_regex}')) AS report_without_contrast
  FROM ct_only
  GROUP BY study_uid, patient_id
),
ct_candidate_studies AS (
  SELECT *
  FROM ct_only_agg
  WHERE (body_part_chest OR report_chest)
    AND NOT report_screen
    AND NOT report_with_contrast
    AND report_without_contrast
),
paired AS (
  SELECT
    p.study_uid AS pt_study_uid,
    p.patient_id,
    p.pet_date,
    p.pt_report,
    c.study_uid AS ct_study_uid,
    c.ct_date,
    c.ct_report,
    DATE_DIFF(p.pet_date, c.ct_date, DAY) AS days_between
  FROM petct_dates p
  JOIN ct_candidate_studies c
    ON p.patient_id = c.patient_id
   AND c.ct_date < p.pet_date
   AND c.ct_date >= DATE_SUB(p.pet_date, INTERVAL {max_days} DAY)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY p.study_uid ORDER BY days_between) = 1
)
SELECT * FROM paired
WHERE REGEXP_CONTAINS(UPPER(pt_report), r'{pet_regex}')
{limit_clause}
"""


def run_query(cfg: Config, query: str) -> pd.DataFrame:
    if cfg.bigquery.get("credentials"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cfg.bigquery["credentials"]

    client = bigquery.Client(project=cfg.bigquery.get("project"))
    return client.query(query).to_dataframe()
