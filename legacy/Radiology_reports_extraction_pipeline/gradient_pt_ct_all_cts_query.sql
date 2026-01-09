WITH pt_studies AS (
  -- All PET studies that contain the desired search term
  SELECT
    CAST(pt.row_id AS STRING)         AS pt_row_id,
    CAST(pt.study_uid AS STRING)      AS pt_study_uid,
    pt.patient_id,
    pt_series.modality               AS pt_modality,
    pt_series.acquisition_date       AS pt_acquisition_date,
    pt.deid_english_report           AS pt_report
  FROM `radicait.gradient_health_dataset.public_table` pt,
  UNNEST(pt.series) AS pt_series
  WHERE pt_series.modality = 'PT'
    -- Replace <search_term> with the desired expression when running the query
    AND REGEXP_CONTAINS(pt.deid_english_report, r'(?i)<search_term>?')
),

ct_studies AS (
  -- All CT studies (non-contrast) for every patient
  SELECT
    CAST(ct.row_id AS STRING)         AS ct_row_id,
    CAST(ct.study_uid AS STRING)      AS ct_study_uid,
    ct.patient_id,
    ct_series.acquisition_date       AS ct_acquisition_date,
    ct.deid_english_report           AS ct_report,
    ct_series.contrast_bolus_agent   AS ct_contrast_agent,
    ct_series.number_of_slices       AS ct_number_of_slices,
    ct_series.slice_thickness        AS ct_slice_thickness,
    ct_series.series_description     AS ct_series_description
  FROM `radicait.gradient_health_dataset.public_table` ct,
  UNNEST(ct.series) AS ct_series
  WHERE ct_series.modality = 'CT'
    -- Non-contrast CT reports only
    AND REGEXP_CONTAINS(ct.deid_english_report, r'(?i)WITHOUT CONTR|W/O CONTR')
    -- Restrict to thin-slice CTs (≤ 5 mm)
    AND ct_series.slice_thickness <= 5
)

-- -------------------------------------------
-- Final join: one row per PET study combined
-- with *each* qualifying CT study in the
-- 60-day look-back window (exclusive of same-
-- day or future CTs).
-- -------------------------------------------
SELECT
  pt.pt_row_id,
  pt.pt_study_uid,
  pt.patient_id,
  pt.pt_modality,
  pt.pt_acquisition_date,
  pt.pt_report,
  ct.ct_row_id,
  ct.ct_study_uid,
  ct.ct_acquisition_date,
  ct.ct_report,
  ct.ct_contrast_agent,
  ct.ct_number_of_slices,
  ct.ct_slice_thickness,
  ct.ct_series_description,
  DATE_DIFF(pt.pt_acquisition_date, ct.ct_acquisition_date, DAY) AS days_between_ct_and_pt
FROM pt_studies pt
JOIN ct_studies ct
  ON pt.patient_id = ct.patient_id
 -- Look-back window: strictly before PET, within 30 days
  AND ct.ct_acquisition_date < pt.pt_acquisition_date
  AND ct.ct_acquisition_date >= DATE_SUB(pt.pt_acquisition_date, INTERVAL 30 DAY)
ORDER BY pt.pt_acquisition_date DESC,
         pt.pt_study_uid,
         ct.ct_acquisition_date DESC; 