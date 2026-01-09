-- Count PT studies that have a CT in the prior 2 months
WITH pt_with_ct AS (
  SELECT DISTINCT
    pt.study_uid AS pt_study_uid,
    pt.patient_id
  FROM `radicait.gradient_health_dataset.public_table` pt,
  UNNEST(pt.series) AS pt_series
  WHERE pt_series.modality = 'PT'
    AND REGEXP_CONTAINS(pt.deid_english_report, r'(?i)lung cancer?')
    AND EXISTS (
      SELECT 1
      FROM `radicait.gradient_health_dataset.public_table` ct,
      UNNEST(ct.series) AS ct_series
      WHERE ct.patient_id = pt.patient_id
        AND ct_series.modality = 'CT'
        AND ct_series.acquisition_date < pt_series.acquisition_date
        AND ct_series.acquisition_date >= DATE_SUB(pt_series.acquisition_date, INTERVAL 60 DAY)
    )
)
SELECT 
  COUNT(DISTINCT pt_study_uid) AS pt_studies_with_prior_ct,
  COUNT(DISTINCT patient_id) AS unique_patients
FROM pt_with_ct; 