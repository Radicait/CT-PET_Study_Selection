# Gradient Study Selection Pipeline

Production-ready pipeline for selecting diagnostic **non-contrast CT chest** studies paired with a **PET/CT** within 60 days, focused on pulmonary nodules.

---

## Table of Contents

1. [Overview](#overview)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Data Flow](#data-flow)
4. [Study Selection Logic](#study-selection-logic)
5. [Filtering Criteria](#filtering-criteria)
6. [Quick Start](#quick-start)
7. [CLI Commands](#cli-commands)
8. [Configuration](#configuration)
9. [Output Artifacts](#output-artifacts)
10. [Repo Layout](#repo-layout)

---

## Overview

This pipeline identifies and pairs radiology studies for pulmonary nodule evaluation by:

1. **Finding PET/CT studies** that mention lung nodules
2. **Finding diagnostic CT-only studies** (non-contrast, chest coverage)
3. **Pairing** each PET/CT with the nearest prior diagnostic CT within 60 days
4. **Extracting** structured data from radiology reports using LLM
5. **Applying** strict eligibility rules to select final study pairs

### Clinical Goal

Select patient studies representing a **diagnostic, non-contrast CT chest** followed by a **PET/CT** for evaluation of a **pulmonary nodule**, excluding:
- Screening/low-dose CTs
- Post-treatment monitoring cases
- Cases driven by non-lung primary cancers

---

## Pipeline Architecture

```
+------------------+     +-------------------+     +------------------+
|                  |     |                   |     |                  |
|  BigQuery Data   |---->|  Query Phase      |---->|  Candidate Pairs |
|  (DICOM + Reports)|    |  (SQL Pairing)    |     |  CSV             |
|                  |     |                   |     |                  |
+------------------+     +-------------------+     +--------+---------+
                                                           |
                                                           v
+------------------+     +-------------------+     +--------+---------+
|                  |     |                   |     |                  |
|  Selected Pairs  |<----|  Selection Phase  |<----|  Extraction Phase|
|  CSV + Audit Log |     |  (Rules Engine)   |     |  (LLM Parsing)   |
|                  |     |                   |     |                  |
+------------------+     +-------------------+     +------------------+
```

### Phase Summary

| Phase | Component | Input | Output |
|-------|-----------|-------|--------|
| **1. Query** | BigQuery SQL | Raw study data | `candidate_pairs.csv` |
| **2. Extract** | OpenAI LLM | Candidate pairs + reports | `extracted_pairs.csv` |
| **3. Select** | Python rules | Extracted data | `selected_PET_CT_studies.csv` |

---

## Data Flow

### End-to-End Pipeline Flow

```
                              START
                                |
                                v
        +-----------------------------------------------+
        |           PHASE 1: QUERY (BigQuery)           |
        +-----------------------------------------------+
        |                                               |
        |  1. Build study-level modality map            |
        |     - Identify PET/CT studies (PT + CT)       |
        |     - Identify CT-only studies                |
        |                                               |
        |  2. Filter PET/CT studies                     |
        |     - Report mentions nodule keywords         |
        |                                               |
        |  3. Filter CT-only studies                    |
        |     - Chest coverage (body part or report)    |
        |     - Non-contrast indication                 |
        |     - Not screening/LDCT                      |
        |                                               |
        |  4. Pair studies                              |
        |     - Same patient                            |
        |     - CT date < PET date                      |
        |     - Within 60-day window                    |
        |     - Select nearest prior CT                 |
        |                                               |
        +-----------------------------------------------+
                                |
                                v
                      candidate_pairs.csv
                    (pt_study_uid, ct_study_uid,
                     patient_id, pet_date, ct_date,
                     days_between, pt_report, ct_report)
                                |
                                v
        +-----------------------------------------------+
        |         PHASE 2: EXTRACTION (LLM)             |
        +-----------------------------------------------+
        |                                               |
        |  For each pair, make TWO separate LLM calls:  |
        |                                               |
        |  CT Extraction:                               |
        |  +------------------------------------------+ |
        |  | Input:  ct_report                        | |
        |  | Output: CT_Regions, CT_Contrast_Agent,   | |
        |  |         Lung_Nodules[]                   | |
        |  +------------------------------------------+ |
        |                                               |
        |  PET Extraction:                              |
        |  +------------------------------------------+ |
        |  | Input:  pt_report                        | |
        |  | Output: Clinical_Reason, Primary_Dx,     | |
        |  |         Lung/Lymph/Other_Hypermetabolic[]| |
        |  +------------------------------------------+ |
        |                                               |
        |  (Parallel execution with 20 workers)         |
        |                                               |
        +-----------------------------------------------+
                                |
                                v
                      extracted_pairs.csv
                    (original columns + ct_* + pet_*)
                                |
                                |
        +-----------------------------------------------+
        |         PHASE 3: SELECTION (Rules)            |
        +-----------------------------------------------+
        |                                               |
        |  Apply eligibility rules:                     |
        |                                               |
        |  CT Rules:                                    |
        |  +------------------------------------------+ |
        |  | - CT_Regions contains "chest"            | |
        |  | - CT_Contrast_Agent == "None"            | |
        |  | - Lung_Nodules is not empty              | |
        |  +------------------------------------------+ |
        |                                               |
        |  PET Rules:                                   |
        |  +------------------------------------------+ |
        |  | - Clinical_Reason == "Indeterminate      | |
        |  |   Pulmonary Nodule"                      | |
        |  | - Primary_Diagnosis in ["Primary Lung    | |
        |  |   Cancer", "No Cancer"]                  | |
        |  | - Lymph_Nodes_Hypermetabolic is empty    | |
        |  | - Other_Hypermetabolic is empty          | |
        |  +------------------------------------------+ |
        |                                               |
        |  Track rejection reasons for audit            |
        |                                               |
        +-----------------------------------------------+
                                |
                                v
                +---------------+---------------+
                |                               |
                v                               v
    selected_PET_CT_studies.csv      selection_audit_log.csv
    (passing pairs only)              (all pairs + reasons)
                                |
                                v
                               END
```

### Study Pairing Logic

```
Patient Timeline
================

        60-day window
    <-------------------->

Day:  -90  -60  -45  -30  -15   0   +15
       |    |    |    |    |    |    |
       CT1  |   CT2  CT3   |  PET/CT |
            |              |         |
            +-- Valid -----+         |
               Window               PET Date

Selection: CT3 chosen (nearest prior CT within window)
```

### Modality Classification

```
+------------------------+      +------------------------+
|     PET/CT Study       |      |     CT-Only Study      |
+------------------------+      +------------------------+
| study_uid: ABC123      |      | study_uid: XYZ789      |
| series:                |      | series:                |
|   - PT (acquisition)   |      |   - CT (diagnostic)    |
|   - CT (attenuation)   |      |                        |
| modalities: [PT, CT]   |      | modalities: [CT]       |
+------------------------+      +------------------------+
         |                               |
         |  is_petct = TRUE              |  is_ct_only = TRUE
         |                               |
         +---------------+---------------+
                         |
                         v
                   Pairing Logic
                  (same patient,
                   CT before PET,
                   within 60 days)
```

---

## Study Selection Logic

### Phase 1: Study-Level Modality Map

For each study, compute:
- `modalities` = distinct modalities from all series
- `is_petct` = contains both PT and CT
- `is_ct_only` = contains only CT

### Phase 2: PET/CT Candidate Selection

**Include** if:
- Study contains both PT and CT modalities
- Report mentions nodule-related keywords (inclusive filter)

```
Keywords: lung cancer, pulmonary nodule, lung nodule
```

### Phase 3: Diagnostic CT Candidate Selection

**Include** if ALL of:

| Criterion | Logic |
|-----------|-------|
| Chest coverage | `body_part_examined` OR `report` contains chest/thorax/torax |
| Non-contrast | Report contains "without contrast" AND NOT "with contrast" |
| Not screening | Report does NOT contain "low dose", "ldct", "screen" |
| Not localizer | Series are not only scout/localizer images |

### Phase 4: Pairing

For each PET/CT study, find the **nearest prior** diagnostic CT:
- Same patient
- CT date < PET date
- CT date >= PET date - 60 days
- Select single best match (minimum days_between)

### Phase 5: LLM Extraction

**Two separate calls** (prevents context mixing):

| Call | Input | Extracted Fields |
|------|-------|------------------|
| CT | `ct_report` | `CT_Regions`, `CT_Contrast_Agent`, `Lung_Nodules[]` |
| PET | `pt_report` | `Clinical_Reason`, `Primary_Diagnosis`, hypermetabolic regions |

### Phase 6: Final Selection Rules

**CT Requirements:**
```
CT_Regions contains "chest"
CT_Contrast_Agent == "None"
Lung_Nodules is not empty
```

**PET Requirements:**
```
Clinical_Reason == "Indeterminate Pulmonary Nodule"
Primary_Diagnosis in ["Primary Lung Cancer", "No Cancer"]
Lymph_Nodes_Hypermetabolic_Regions is empty
Other_Hypermetabolic_Regions is empty
```

---

## Filtering Criteria

### CT Filters (SQL + LLM)

| Filter | SQL Phase | LLM Phase | Rationale |
|--------|-----------|-----------|-----------|
| Chest coverage | body_part OR report text | CT_Regions contains chest | Ensure thoracic imaging |
| Non-contrast | Report text patterns | CT_Contrast_Agent == "None" | Avoid contrast-enhanced CTs |
| Not screening | Report text patterns | - | Exclude LDCT/screening programs |
| Has nodules | - | Lung_Nodules not empty | Must have reportable nodule |

### PET Filters (LLM)

| Filter | Extracted Field | Valid Values | Rationale |
|--------|-----------------|--------------|-----------|
| Clinical reason | Clinical_Reason | "Indeterminate Pulmonary Nodule" | Focus on nodule workup |
| Primary diagnosis | Primary_Diagnosis | "Primary Lung Cancer", "No Cancer" | Exclude other primaries |
| No systemic disease | Lymph_Nodes_Hypermetabolic | empty | Exclude metastatic disease |
| No other sites | Other_Hypermetabolic | empty | Exclude multi-site disease |

### Rejection Tracking

All pairs are tracked with rejection reasons:

```
Reason Codes:
- ct_not_chest              CT regions don't include chest
- ct_contrast_present       Contrast agent detected
- no_lung_nodules           No nodules in CT report
- pet_reason_not_nodule     Clinical reason not pulmonary nodule
- pet_primary_dx_excluded   Primary diagnosis is other cancer
- pet_lymph_hypermetabolic  Hypermetabolic lymph nodes found
- pet_other_hypermetabolic  Other hypermetabolic regions found
- extraction_error          LLM extraction failed
```

---

## Quick Start

1. Set secrets in `.env`:
```bash
OPENAI_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcs_upload_key.json
BQ_PROJECT=radicait
```

2. Review config:
```bash
cat configs/selection.yaml
```

3. Run the pipeline:
```bash
PYTHONPATH=src python -m gradient_selection.cli run --config configs/selection.yaml --limit 50
```

---

## CLI Commands

| Command | Description | Output |
|---------|-------------|--------|
| `query` | Run BigQuery pairing only | `candidate_pairs.csv` |
| `extract` | Run LLM extraction on pairs | `extracted_pairs.csv` |
| `select` | Apply selection rules | `selected_PET_CT_studies.csv` |
| `run` | Full end-to-end pipeline | All outputs |

### Examples

```bash
# Run full pipeline with limit
PYTHONPATH=src python -m gradient_selection.cli run --limit 50

# Run individual phases
PYTHONPATH=src python -m gradient_selection.cli query --limit 20
PYTHONPATH=src python -m gradient_selection.cli extract --input-csv outputs/run_*/candidate_pairs.csv
PYTHONPATH=src python -m gradient_selection.cli select --input-csv outputs/run_*/extracted_pairs.csv
```

---

## Configuration

### `configs/selection.yaml`

```yaml
paths:
  output_dir: outputs
  run_dir_template: "run_{date}"

bigquery:
  project: radicait
  dataset: gradient_health_dataset
  table: public_table

selection:
  max_days: 60                    # CT must be within 60 days before PET
  pet_report_terms:               # PET pre-filter (inclusive)
    - lung cancer
    - pulmonary nodule
    - lung nodule
  ct_chest_terms:                 # Chest coverage indicators
    - chest
    - thorax
    - torax
  ct_noncontrast_terms:           # Non-contrast indicators
    - without contrast
    - w/o contrast
    - noncontrast
  ct_with_contrast_terms:         # Exclusion: contrast present
    - with contrast
    - w/ contrast
    - post contrast
  ct_exclude_terms:               # Exclusion: screening/LDCT
    - low dose
    - ldct
    - screen

llm:
  model: gpt-5.2
  temperature: 0.2
  concurrency: 20                 # Parallel extraction workers
  retries: 3
```

---

## Output Artifacts

Each run creates a timestamped directory:

```
outputs/run_20250109_143000/
|
+-- candidate_pairs.csv           # BigQuery output (paired studies)
|   Columns: pt_study_uid, ct_study_uid, patient_id,
|            pet_date, ct_date, days_between,
|            pt_report, ct_report
|
+-- extracted_pairs.csv           # With LLM extractions
|   Columns: (all above) + ct_CT_Regions, ct_Lung_Nodules,
|            pet_Clinical_Reason, pet_Primary_Diagnosis, ...
|
+-- selected_PET_CT_studies.csv   # Final selected pairs only
|
+-- selection_audit_log.csv       # All pairs with pass/fail + reasons
|   Columns: pt_study_uid, ct_study_uid, selected, reasons
|
+-- extractions/
    +-- ct/
    |   +-- {ct_study_uid}.json   # Raw CT extraction JSON
    +-- pet/
        +-- {pt_study_uid}.json   # Raw PET extraction JSON
```

---

## Repo Layout

```
gradient-data/
|
+-- configs/              YAML configuration files
|   +-- selection.yaml    Main pipeline config
|
+-- prompts/              LLM extraction prompts
|   +-- ct_extraction_prompt.txt
|   +-- pet_extraction_prompt.txt
|
+-- sql/                  Reference SQL templates
|   +-- petct_candidate_pairs.sql
|
+-- src/                  Python package
|   +-- gradient_selection/
|       +-- cli.py        Command-line interface
|       +-- bq.py         BigQuery query builder
|       +-- extraction.py LLM extraction logic
|       +-- selection.py  Selection rules engine
|       +-- config.py     Configuration management
|       +-- logging_utils.py
|
+-- outputs/              Run artifacts (csv/json/logs)
|
+-- legacy/               Archived scripts and notebooks
|
+-- secrets/              Local credentials (git-ignored)
|
+-- docs/                 Additional documentation
```

---

## Notes

- The definitive selection logic is documented in `PLAN_STUDY_SELECTION.md`.
- CT and PET extractions use **separate LLM calls** to prevent context mixing.
- All rejected pairs are tracked with specific rejection reasons for audit.
- Legacy scripts and notebooks are preserved in `legacy/` for reference.
