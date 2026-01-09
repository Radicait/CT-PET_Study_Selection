# Study Selection Review (Gradient PET/CT + Diagnostic CT)

Date: 2025-12-28

## Scope
This review covers:
- BigQuery table: `radicait.gradient_health_dataset.public_table` (study-level rows with nested `series`).
- Local delivery: `/home/sina/Data/Gradient/PET_CT_30JUN2025-R1` (reports + DICOM metadata + reorganized DICOM).
- Manual deep-dive of 20 PET/CT studies + their candidate diagnostic CTs (where present), including DICOM tag inspection from the reorganized dataset.

Artifacts produced during this review:
- `reports_data/_sample_study_pairs_review.csv` (20 PET/CT studies + candidate CT within 60 days when present).
- `reports_data/_sample_study_dicom_series_review.csv` (series-level DICOM tags for the above studies).

---

## BigQuery Data Structure (public_table)
**Row = study.** Key top-level fields used in this pipeline:
- `row_id`, `study_uid`, `patient_id`, `study_date`, `study_description`, `deid_english_report`, `institution`, `patient_sex`, `patient_age`.
- `series` (REPEATED RECORD) contains series-level DICOM metadata.

**series sub-record (high value fields for this pipeline):**
- `series_instance_uid`, `modality`, `acquisition_date`, `acquisition_date_time`.
- `series_description`, `protocol_name`, `body_part_examined`.
- `slice_thickness`, `number_of_slices`, `image_rows`, `image_columns`.
- `contrast_bolus_agent`, `requested_contrast_agent`.

**Important structural note:** There is no top-level `modality`; it exists only inside `series`. All modality logic must use `UNNEST(series)`.

---

## BigQuery Observations (as of 2025-12-28)
**Study-level counts**
- Total studies: **20,394,822**
- Studies with PT series: **87,642**
- PET/CT studies (PT+CT series in same study): **76,331**
- PT-only studies (no CT series): **11,311**
- CT-only studies (no PT series): **5,115,780**

**PET/CT same-day check (PT vs CT acquisition_date):**
- Same-day PT & CT within study: **72,334**
- Not same-day (or missing dates): **3,997**

**Data quality (series-level):**
- PT series missing acquisition_date: **27,181**
- CT series missing acquisition_date: **1,034,529**
- CT series missing slice_thickness: **3,224,932**
- CT series slice_thickness <= 5 mm: **21,259,760**
- CT series slice_thickness > 5 mm: **1,693,470**

Implication: relying only on `series.acquisition_date` and `slice_thickness <= 5` will drop a non-trivial number of valid studies (missing dates/thickness).

---

## Local Delivery Review (PET_CT_30JUN2025-R1)
**Dataset summary**
- Studies: **1409**
  - PET/CT (PT+CT): **632**
  - CT-only: **775**
  - PT-only: **2**
- PET/CT studies with a CT-only study within 60 days: **563**
- PET/CT studies without a CT-only study within 60 days: **96**

**Report patterns**
- PET/CT reports mentioning attenuation correction: **624/632**
- CT-only reports mentioning "without contrast": **890/894**
- CT-only reports mentioning "with and without": **4/894**
- CT-only reports mentioning "low dose": **4/894**
- CT-only reports mentioning "screen" (screening): **239/894**

**DICOM series characteristics from the 20-study sample**
- PET/CT studies had **5-11 series**; CT-only studies had **5-6 series**.
- PET/CT CT-series body part: typically **Whole Body** or **Head** (consistent with attenuation/localization CT).
- Diagnostic CT body part: **Chest** or **Chest/Abdomen**.
- PET/CT CT-series descriptions frequently include **SCOUT / CT IMAGES / CTAC / RANGE-CT**.
- PET series descriptions commonly include **PET AC / PET NAC / MIP / REFORMATTED**.
- Some diagnostic CT series contain non-empty `ContrastBolusAgent` despite "without contrast" wording in the report, indicating DICOM tags alone are not fully reliable.

---

## 20-Study Sample (PET/CT + Diagnostic CT when present)
UIDs are shortened to the last 12 digits for readability; full UIDs are in `reports_data/_sample_study_pairs_review.csv`.

| PatientID        | PET Date   |   PET UID (last12) | CT UID (last12)   | Days CT->PET   | PET Modalities   | PET Report: CT Atten Only   | CT Report: Without Contrast   | CT Report: Low Dose   |
|:-----------------|:-----------|-------------------:|:------------------|:---------------|:-----------------|:----------------------------|:------------------------------|:----------------------|
| GRDN04RZGTGBWU8H | 2011-05-21 |       672186099288 | 870601460505      | 2.0            | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN05OWHZNCXP6U | 2022-06-13 |       113399599107 | 980318156124      | 48.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN06YJB19PTFSV | 2010-03-29 |       233496417223 | 438063230604      | 10.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN08LEN281XO0F | 2022-11-04 |       391431477148 | 902088616560      | 13.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0BGVCDSOECLR | 2018-07-08 |       468667254636 | 979940242467      | 9.0            | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0IMXKL6D68SN | 2014-12-20 |       718651572944 | 289249600753      | 13.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0IMXKL6D68SN | 2015-05-31 |       040678537141 | 214356939365      | 26.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0IQLQMG1DA4Y | 2017-09-21 |       707982108299 | 451142224872      | 32.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0JT4YCBGXIDZ | 2023-10-25 |       821565708817 | 096663357116      | 29.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0JVOALSLS9CM | 2019-08-03 |       951425884661 | 803828283777      | 15.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0MB24PAW4U11 | 2009-05-11 |       594634592229 | 509681592646      | 12.0           | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN0OUXQI7QJQCL | 2011-03-31 |       313363489159 | 462314008629      | 5.0            | ['CT', 'PT']     | True                        | True                          | False                 |
| GRDN01FO2GO3T94Q | 2012-08-19 |       037218216894 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN058B4QOK739I | 2008-07-20 |       984024286812 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN0SXOON7NT3Z5 | 2021-01-29 |       604115832164 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN0VSP3X5S9CCN | 2007-01-10 |       021398396073 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN1KR114ZQ7MHN | 2015-04-26 |       109469065632 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN250FAEVZBUO6 | 2011-09-06 |       395315926863 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN26C8D5A4NGJW | 2016-01-16 |       998224410743 |                   |                | ['CT', 'PT']     | True                        |                               |                       |
| GRDN2V9DCLC5QQ75 | 2020-05-23 |       610851164930 |                   |                | ['CT', 'PT']     | True                        |                               |                       |

Notes:
- "PET Report: CT Atten Only" is derived from report text (attenuation-correction language).
- Blank CT columns indicate no CT-only study within 60 days for that patient.

---

## Review of Current Pipeline Logic
### What is working
- PET/CT report extraction reliably captures tracer/glucose/scan region for most cases.
- The 60-day window matches many real-world CT->PET workflows (563/632 in the 2025-06-30 delivery).

### Key risks / edge cases observed
1. **PET-only studies are included**: The SQL selects any study with PT series, but ~13% of PT studies are PT-only (no CT series). The definition of "PET/CT" in the goal requires both PT and CT in the same study.
2. **Series-level duplication**: Unnesting `series` creates multiple rows per study, inflating joins. `rn` is computed but never used.
3. **Acquisition date missing**: ~8% of PT series and ~4% of CT series lack `acquisition_date`, causing valid studies to be dropped in the date filter.
4. **Contrast logic**: Report-based "WITHOUT CONTR" is permissive and can still include contrast studies ("with and without") or be contradicted by DICOM contrast tags.
5. **Chest specificity**: The BigQuery query does not enforce chest region; the LLM filter handles it later, but this increases load and risk of misclassification.
6. **Diagnostic CT selection**: The current join returns *all* CTs within 60 days; it does not select the most likely diagnostic CT (nearest prior).
7. **Screening CTs**: ~27% of CT-only reports in the local dataset mention "screen", which likely includes low-dose screening scans that you want to exclude.
8. **Prompt ambiguity**: LLM is given a combined report; it may occasionally mix CT and PET contexts despite headings, especially for nodules and regions.
9. **Security**: `Radiology_reports_extraction_pipeline/openai_helper.py` hardcodes an API key (should be moved to env/secret).

---

## Recommended "Correct" Approach
### 1) Identify PET/CT studies explicitly (study-level)
- Require **both PT and CT series** in the same `study_uid`.
- Use **study_date** as fallback when series `acquisition_date` is null.
- Validate same-day PT/CT within the study when possible.

### 2) Define diagnostic CT candidates
- Use **CT-only studies** (modalities = {CT}) to avoid grabbing PET/CT attenuation CTs.
- Require chest location using **`body_part_examined`**, **`study_description`**, or report text (include multilingual terms like "CHEST/THORAX/TORAX").
- Exclude screening CTs using report text: "screen", "low dose", "LDCT".
- Exclude scouts/localizers using `series_description` regex: `SCOUT|LOCALIZER|TOPO|TOPOGRAM`.

### 3) Pairing logic
- For each PET/CT study, select the **nearest prior CT-only study** within 60 days.
- If multiple CTs exist, pick the one with: nearest date, thin-slice axial series, and chest protocol.

### 4) Report extraction improvements
- Pass CT and PET reports as **separate fields** (not concatenated), or use a strict delimiter and explicit instructions to only read CT report for CT_Regions/contrast.
- Add lightweight rule-based checks for CT screening/contrast before sending to the LLM.

### 5) Suggested SQL pattern (sketch)
```sql
WITH study_modalities AS (
  SELECT
    study_uid,
    patient_id,
    study_date,
    ARRAY_AGG(DISTINCT s.modality) AS modalities,
    ARRAY_AGG(DISTINCT s.acquisition_date IGNORE NULLS) AS acq_dates
  FROM `radicait.gradient_health_dataset.public_table`, UNNEST(series) AS s
  GROUP BY study_uid, patient_id, study_date
),
petct AS (
  SELECT *
  FROM study_modalities
  WHERE 'PT' IN UNNEST(modalities) AND 'CT' IN UNNEST(modalities)
),
ct_only AS (
  SELECT t.study_uid, t.patient_id, t.study_date,
         s.acquisition_date AS ct_acq_date,
         s.series_description, s.body_part_examined,
         s.slice_thickness, s.contrast_bolus_agent
  FROM `radicait.gradient_health_dataset.public_table` t, UNNEST(t.series) AS s
  JOIN study_modalities m ON m.study_uid = t.study_uid
  WHERE m.modalities = ['CT']
    AND s.modality = 'CT'
    AND (s.body_part_examined LIKE '%Chest%' OR REGEXP_CONTAINS(UPPER(t.study_description), r'CHEST|THORAX|TORAX'))
    AND NOT REGEXP_CONTAINS(UPPER(s.series_description), r'SCOUT|LOCALIZER|TOPO')
),
ct_study_dates AS (
  SELECT study_uid, patient_id,
         COALESCE(MAX(ct_acq_date), MAX(study_date)) AS ct_date
  FROM ct_only
  GROUP BY study_uid, patient_id
),
pet_dates AS (
  SELECT study_uid, patient_id,
         COALESCE(MAX(d), MAX(study_date)) AS pet_date
  FROM petct, UNNEST(acq_dates) AS d
  GROUP BY study_uid, patient_id, study_date
),
paired AS (
  SELECT
    p.study_uid AS pt_study_uid,
    c.study_uid AS ct_study_uid,
    DATE_DIFF(p.pet_date, c.ct_date, DAY) AS days_between
  FROM pet_dates p
  JOIN ct_study_dates c
    ON p.patient_id = c.patient_id
   AND c.ct_date < p.pet_date
   AND c.ct_date >= DATE_SUB(p.pet_date, INTERVAL 60 DAY)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY p.study_uid ORDER BY days_between) = 1
)
SELECT * FROM paired;
```

---

## Bottom Line
- The current pipeline is **close** but misses key requirements: explicitly ensure PET/CT studies (PT+CT in same study), de-duplicate series-level joins, and select the nearest prior diagnostic CT.
- Screening CTs and contrast ambiguity are the biggest sources of incorrect inclusion.
- The data supports the CT->PET workflow in many cases, but enforcing study-level modality and chest/diagnostic criteria will improve yield and precision.
