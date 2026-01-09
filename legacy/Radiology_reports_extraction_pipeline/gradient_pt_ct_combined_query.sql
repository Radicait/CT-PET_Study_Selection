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
ct_studies_ranked AS (
  -- Get all CT studies and rank them by how recent they are for each patient
  SELECT
    CAST(ct.row_id AS STRING) AS ct_row_id,
    CAST(ct.study_uid AS STRING) AS ct_study_uid,
    ct.patient_id,
    ct_series.acquisition_date AS ct_acquisition_date,
    ct.deid_english_report AS ct_report,
    ct_series.contrast_bolus_agent AS ct_contrast_agent,
    ct_series.number_of_slices AS ct_number_of_slices,
    ct_series.slice_thickness AS ct_slice_thickness,
    ct_series.series_description AS ct_series_description,
    -- Rank CT studies by acquisition date (most recent first) for each patient
    ROW_NUMBER() OVER (
      PARTITION BY ct.patient_id, ct_series.acquisition_date 
      ORDER BY ct.study_uid
    ) AS rn
  FROM `radicait.gradient_health_dataset.public_table` ct,
  UNNEST(ct.series) AS ct_series
  WHERE ct_series.modality = 'CT'
  AND REGEXP_CONTAINS(ct.deid_english_report, "(?i)WITHOUT CONTR|W/O CONTR")
)

-- Join PT studies with their most recent prior CT study
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
  ct.ct_number_of_slices,
  ct.ct_slice_thickness,
  ct.ct_series_description,
  DATE_DIFF(pt.pt_acquisition_date, ct.ct_acquisition_date, DAY) AS days_between_ct_and_pt
FROM pt_studies pt
INNER JOIN (
  -- Get the most recent CT for each PT study
  SELECT 
    pt_inner.patient_id,
    pt_inner.pt_acquisition_date,
    MAX(ct_inner.ct_acquisition_date) AS most_recent_ct_date
  FROM pt_studies pt_inner
  INNER JOIN ct_studies_ranked ct_inner
    ON pt_inner.patient_id = ct_inner.patient_id
  WHERE ct_inner.ct_acquisition_date < pt_inner.pt_acquisition_date
    AND ct_inner.ct_acquisition_date >= DATE_SUB(pt_inner.pt_acquisition_date, INTERVAL 60 DAY)
    AND ct_inner.ct_slice_thickness <=5
    AND ct_inner.rn = 5  -- Only one study per patient per date
  GROUP BY pt_inner.patient_id, pt_inner.pt_acquisition_date
) most_recent_ct
  ON pt.patient_id = most_recent_ct.patient_id
  AND pt.pt_acquisition_date = most_recent_ct.pt_acquisition_date
INNER JOIN ct_studies_ranked ct
  ON ct.patient_id = pt.patient_id
  AND ct.ct_acquisition_date = most_recent_ct.most_recent_ct_date
  AND ct.rn = 5  -- In case multiple studies on same date, pick one
ORDER BY pt.pt_acquisition_date DESC
