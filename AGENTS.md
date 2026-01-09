# Gradient Study Selection Pipeline (Agent Guide)

This repo has been refactored to a production-style pipeline. Look at `PLAN_STUDY_SELECTION.md` for the initial idea behind the pipeline.

## Goal
Select **diagnostic, non-contrast CT chest** studies paired with a **PET/CT** within 60 days for pulmonary nodule evaluation.

## New Pipeline Overview
1) **BigQuery candidate pairing** (study-level PET/CT + CT-only)
2) **LLM extraction** (CT and PET reports are processed separately)
3) **Selection filtering** based on extracted fields
4) **Output** CSVs + audit logs

## CLI Entry Points
- `python -m gradient_selection.cli run`
- `python -m gradient_selection.cli query`
- `python -m gradient_selection.cli extract`
- `python -m gradient_selection.cli select`

## Key Files
- Config: `configs/selection.yaml`
- Prompts: `prompts/ct_extraction_prompt.txt`, `prompts/pet_extraction_prompt.txt`
- SQL reference: `sql/petct_candidate_pairs.sql`
- Source code: `src/gradient_selection/`
- Outputs: `outputs/`

## Secrets
- `.env` holds `OPENAI_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS`
- Secrets are ignored by git via `.gitignore`

## Legacy
All previous notebooks/scripts were moved to `legacy/` for reference. No backward compatibility is guaranteed.
