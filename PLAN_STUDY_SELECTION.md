# Study Selection Plan (Diagnostic CT + PET/CT for Pulmonary Nodules)

Date: 2025-12-29

## Goal
Select patient studies that represent a **diagnostic, non-contrast CT chest** followed by a **PET/CT** within 60 days for evaluation of a **pulmonary nodule**, and exclude cases that are screening CTs, post-treatment monitoring, or driven by non-lung primaries/metastatic disease.

---

## Definitions
**PET/CT study (for this pipeline):**
- A single study (`study_uid`) that contains **both PT and CT series**.
- No date-overlap check is required; the presence of CT modality within the PET study is sufficient.
- The CT series in PET/CT is assumed to be **attenuation/localization CT (CTAC)**.

**Diagnostic CT candidate:**
- **CT-only** study (`modalities = {CT}`) with **chest** coverage.
- **Non-contrast** (no IV contrast).
- **Not screening / low-dose** (exclude LDCT and screening programs).

---

## Data Sources
**BigQuery**: `radicait.gradient_health_dataset.public_table`
- Each row is a **study** with `study_uid`, `patient_id`, `study_date`, and `deid_english_report`.
- DICOM metadata is stored in repeated `series` records; there is **no top-level modality**.

**pipeline outputs**
- `reports_data/gradient_pt_ct_all_pairs_query.csv`
- `reports_data/LLM_extracted_data/`
- `selected_PET_CT_studies.csv`
- `PET_CT_study_ids.csv`
- `selection_audit_log.csv`

**Local files deliveries** (shall be done manually later when data is purchased from Gradient)
- `/home/sina/Data/Gradient/CT_PET_pairs/CSV/reports_data/*.csv`
- `/home/sina/Data/Gradient/CT_PET_pairs/CSV/dicom_metadata_data/*.csv`
- `/home/sina/Data/Gradient/CT_PET_pairs/reorganized/` (DICOM files)

---

## Selection Pipeline (Implementation Plan)

### Phase 1: Build study-level modality map
**Purpose:** Identify PET/CT studies and CT-only studies at the study level.

- For each `study_uid`, compute:
  - `modalities = ARRAY_AGG(DISTINCT series.modality)`
  - `pt_acq_dates = ARRAY_AGG(DISTINCT series.acquisition_date WHERE modality='PT')`
  - `ct_acq_dates = ARRAY_AGG(DISTINCT series.acquisition_date WHERE modality='CT')`
  - `study_date`
- Derive:
  - `is_petct = ('PT' IN modalities AND 'CT' IN modalities)`
  - `is_ct_only = (ARRAY_LENGTH(modalities)=1 AND modalities[OFFSET(0)]='CT')`

**PET date selection:**
- `pet_date = COALESCE(MAX(pt_acq_dates), study_date)`

**CT date selection (for CT-only studies):**
- `ct_date = COALESCE(MAX(ct_acq_dates), study_date)`

---

### Phase 2: PET/CT candidate selection (study-level)
**Keep** only studies where:
- `is_petct = TRUE`
- PET report **mentions nodule** or **pulmonary nodule** (pre-filter to reduce unrelated cancers).

**Note:** We do **not** require PT/CT acquisition date overlap. If CT modality exists within the PET study, we treat it as CTAC and order the full study.

**Note:** This pre-filter should be inclusive (regex: `nodule|pulmonary nodule|lung nodule|lung cancer`). We will filter more strictly after LLM extraction.

---

### Phase 3: Diagnostic CT candidate selection (study-level)
**Keep** only CT-only studies where:

**Chest criteria** (must satisfy at least one):
- `series.body_part_examined` contains `CHEST|THORAX|TORAX`, OR
- `study_description` contains `CHEST|THORAX|TORAX`, OR
- `ct_report` contains `CHEST|THORAX|TORAX`.

**Non-contrast criteria** (strict):
- `ct_report` indicates non-contrast (e.g., `WITHOUT CONTRAST|W/O CONTRAST|NONCONTRAST`), AND
- `ct_report` does **not** contain `WITH CONTRAST|W/ CONTRAST|POST CONTRAST`.

**Exclude screening / LDCT**:
- `ct_report` does **not** contain `LOW DOSE|LDCT|SCREEN`.

**Exclude localizers/scouts**:
- Exclude studies where CT series are only `SCOUT|LOCALIZER|TOPO|TOPOGRAM`.

**Slice thickness preference**:
- Prefer `slice_thickness <= 5` when available. If missing, keep but **flag for QA**.

---

### Phase 4: Pairing logic (CT -> PET/CT)
For each PET/CT study:
- Find all CT-only diagnostic candidates for same `patient_id` where:
  - `ct_date < pet_date`
  - `ct_date >= pet_date - 60 days`
- Choose the **nearest prior CT** (smallest `days_between`).
- If multiple CTs tie, prefer:
  1) CT with chest-only coverage (not chest/abdomen),
  2) thinner slices,
  3) non-screening keywords.

Output: `candidate_pairs` with
- `pt_study_uid`, `ct_study_uid`, `patient_id`, `pet_date`, `ct_date`, `days_between`, `pt_report`, `ct_report`.

---

### Phase 5: LLM extraction (two separate calls)
**Do not combine CT + PET into a single prompt.**

**CT extraction prompt:**
- Extract CT regions, contrast agent, and lung nodules.
- Ignore PET/CT report entirely.

**PET extraction prompt:**
- Extract tracer, scan region, glucose, hypermetabolic findings (lung, lymph nodes, other), clinical reason, and primary diagnosis.
- Ignore CT report entirely.

**Why separate:** The current combined prompt can mix CT and PET contexts (especially for nodules and regions). Separation reduces false positives/negatives.

---

### Phase 6: Eligibility rules after extraction
**Include** only if all conditions hold:

**CT rules:**
- `CT_Regions` contains chest.
- `CT_Contrast_Agent` = "None".
- `Lung_Nodules` is not empty.
- CT report indicates non-contrast.

**PET rules:**
- `Clinical_Reason` = "Indeterminate Pulmonary Nodule" OR imaging explicitly for pulmonary nodule evaluation.
- `Primary_Diagnosis` = "Primary Lung Cancer" OR "No Cancer" (if PET is for indeterminate nodule and no evidence of systemic malignancy).
- `Lymph_Nodes_Hypermetabolic_Regions` is empty.
- `Other_Hypermetabolic_Regions` is empty.
- PET lung hypermetabolism is allowed if it is limited to the index nodule.

**Exclude** if:
- PET report indicates known non-lung primary cancer or metastatic disease.
- PET report is explicitly for restaging/monitoring existing cancer.

---

### Phase 7: QA / Validation
**Automated checks**
- Cross-check CT chest coverage using report + `body_part_examined`.

**Manual review sample (recommended each run):**
- Randomly review 10-20 pairs from `candidate_pairs`.
- Confirm:
  - CT is diagnostic chest, non-contrast.
  - PET/CT report is for pulmonary nodule.
  - No other primary cancer drives the case.

---

## Known Discrepancies Observed (from current review)
These findings are why the above filters are strict:
- **BodyPartExamined inaccuracies:** Some CT-only studies labeled with chest body part had abdomen/pelvis CT reports; report text must be used as a guard.
- **High prevalence of other cancers in PET reports:** Many PET reports mention other primaries (melanoma, breast, pancreas, etc.), so LLM classification and downstream filters are essential.

---

## Implementation Notes (Repo Integration)
- Replace the current SQL in `Radiology_reports_extraction_pipeline/gradient_pt_ct_all_pairs_query.sql` with a **study-level** PET/CT and CT-only pairing query (use `QUALIFY` to select nearest prior CT).
- Create two new prompts:
  - `extraction_prompt_ct.py`
  - `extraction_prompt_pet.py`
- Update `extract_data.py` to call **two** LLM extractions per pair (CT and PET separately), then merge fields.
- Store LLM outputs in separate columns (prefixes `ct_` and `pet_`) to avoid accidental overwrites.

---

## Deliverables per run
- `candidate_pairs.csv` (from BigQuery)
- `ct_extracted.csv` + `pet_extracted.csv`
- `selected_PET_CT_studies.csv` (final)
- `PET_CT_study_ids.csv` (delivery list)
- `selection_audit_log.csv` (rule failures and reasons for exclusion)


---

## Reference SQL (candidate_pairs skeleton)
```sql
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
```
