-- Candidate PET/CT + prior diagnostic CT pairing
-- This is a template; the Python pipeline injects regex terms and max_days.

WITH study_mods AS (
  SELECT
    study_uid,
    patient_id,
    study_date,
    ARRAY_AGG(DISTINCT s.modality) AS modalities
  FROM `radicait.gradient_health_dataset.public_table`, UNNEST(series) AS s
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
  FROM `radicait.gradient_health_dataset.public_table` t
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
  FROM `radicait.gradient_health_dataset.public_table` t
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
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(body_part_examined), r'CHEST|THORAX|TORAX')) AS body_part_chest,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'CHEST|THORAX|TORAX')) AS report_chest,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'LOW DOSE|LDCT|SCREEN')) AS report_screen,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'WITH CONTRAST|W/ CONTRAST|POST CONTRAST')) AS report_with_contrast,
    LOGICAL_OR(REGEXP_CONTAINS(UPPER(ct_report), r'WITHOUT CONTRAST|W/O CONTRAST|NONCONTRAST')) AS report_without_contrast
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
   AND c.ct_date >= DATE_SUB(p.pet_date, INTERVAL 60 DAY)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY p.study_uid ORDER BY days_between) = 1
)
SELECT * FROM paired;
