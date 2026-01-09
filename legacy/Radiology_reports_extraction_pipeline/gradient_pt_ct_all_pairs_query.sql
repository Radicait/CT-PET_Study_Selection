WITH pt_studies AS (
  -- First, get all PT studies with lung cancer mentions
  SELECT
    CAST(pt.row_id AS STRING) AS pt_row_id,
    CAST(pt.study_uid AS STRING) AS pt_study_uid,
    pt.patient_id,
    pt_series.modality AS pt_modality,
    pt_series.acquisition_date AS pt_acquisition_date,
    pt.deid_english_report AS pt_report
  FROM `radicait.gradient_health_dataset.public_table` pt,
  UNNEST(pt.series) AS pt_series
  WHERE pt_series.modality = 'PT'
  AND REGEXP_CONTAINS(pt.deid_english_report, r'(?i)<search_term>?')
),
ct_studies_filtered AS (
  -- Get all CT studies that meet the criteria
  SELECT
    CAST(ct.row_id AS STRING) AS ct_row_id,
    CAST(ct.study_uid AS STRING) AS ct_study_uid,
    ct.patient_id,
    ct_series.acquisition_date AS ct_acquisition_date,
    ct.deid_english_report AS ct_report,
    ct_series.contrast_bolus_agent AS ct_contrast_agent,
    ct_series.slice_thickness AS ct_slice_thickness,
    ct_series.series_description AS ct_series_description,
    -- Rank CT studies by acquisition date (most recent first) for each patient per date
    ROW_NUMBER() OVER (
      PARTITION BY ct.patient_id, ct_series.acquisition_date 
      ORDER BY ct.study_uid
    ) AS rn
  FROM `radicait.gradient_health_dataset.public_table` ct,
  UNNEST(ct.series) AS ct_series
  WHERE ct_series.modality = 'CT'
  AND REGEXP_CONTAINS(ct.deid_english_report, "(?i)WITHOUT CONTR|W/O CONTR")
  AND ct_series.slice_thickness <= 5
)

-- Join PT studies with ALL qualifying CT studies within 60 days
-- This creates a row for each PET-CT pair combination
SELECT DISTINCT
  pt.pt_row_id,
  pt.pt_study_uid,
  pt.patient_id,
  pt.pt_modality,
  pt.pt_acquisition_date,
  pt.pt_report,
  ct.ct_study_uid,
  ct.ct_acquisition_date,
  ct.ct_report,
  ct.ct_contrast_agent,
  ct.ct_slice_thickness,
  ct.ct_series_description,
  DATE_DIFF(pt.pt_acquisition_date, ct.ct_acquisition_date, DAY) AS days_between_ct_and_pt
FROM pt_studies pt
INNER JOIN ct_studies_filtered ct
  ON pt.patient_id = ct.patient_id
  -- CT must be before PT scan
  AND ct.ct_acquisition_date < pt.pt_acquisition_date
  -- CT must be within certain days of PT scan
  AND ct.ct_acquisition_date >= DATE_SUB(pt.pt_acquisition_date, INTERVAL 60 DAY)
ORDER BY 
  pt.patient_id,
  pt.pt_acquisition_date DESC,
  ct.ct_acquisition_date DESC