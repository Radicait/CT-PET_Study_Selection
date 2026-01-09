SELECT 
    CONCAT("'", SAFE_CAST(row_id AS STRING)) as row_id,
    patient_id,
    accession_number,
    deid_english_report,
    study_date,
    s.slice_thickness,
    s.series_description,
    s.modality
    FROM `gradient-health-search.fermat.public_table`, UNNEST(series) AS s
    WHERE 
     s.modality = 'CT' AND s.slice_thickness <= 1.0 
     AND 
      (
        REGEXP_CONTAINS(deid_english_report, "(?i)chest")
      )
     AND 
      (
        REGEXP_CONTAINS(deid_english_report, "(?i)WITHOUT CONTR|W/O CONTR")
      )
     AND NOT 
      (
        REGEXP_CONTAINS(s.series_description, "(?i)TOPO|SCOUT|SUMMA")
      )
    AND NOT 
      (
        REGEXP_CONTAINS(deid_english_report, "(?i)head|brain")
      )
     
    