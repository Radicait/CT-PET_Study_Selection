from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from dotenv import load_dotenv

from .bq import build_candidate_pairs_query, run_query
from .config import create_run_dir, load_config
from .extraction import run_extraction
from .logging_utils import setup_logging
from .selection import apply_selection

load_dotenv()

app = typer.Typer(add_completion=False)


@app.command()
def query(
    config: str = typer.Option("configs/selection.yaml", help="Path to YAML config"),
    limit: Optional[int] = typer.Option(None, help="Limit number of pairs"),
    run_name: Optional[str] = typer.Option(None, help="Run folder name"),
) -> None:
    cfg = load_config(config, base_dir=".")
    run_dir = create_run_dir(cfg, run_name=run_name)
    logger = setup_logging(cfg.paths.get("logs_dir", "outputs/logs"))

    sql = build_candidate_pairs_query(cfg, sample_limit=limit or cfg.selection.get("sample_limit"))
    logger.info("Running BigQuery candidate selection")
    df = run_query(cfg, sql)

    out_path = run_dir / "candidate_pairs.csv"
    df.to_csv(out_path, index=False)
    logger.info("Wrote %s rows to %s", len(df), out_path)


@app.command()
def extract(
    input_csv: str = typer.Option(..., help="Path to candidate_pairs.csv"),
    config: str = typer.Option("configs/selection.yaml", help="Path to YAML config"),
    run_name: Optional[str] = typer.Option(None, help="Run folder name"),
    max_rows: Optional[int] = typer.Option(None, help="Max rows to extract"),
) -> None:
    cfg = load_config(config, base_dir=".")
    run_dir = create_run_dir(cfg, run_name=run_name)
    logger = setup_logging(cfg.paths.get("logs_dir", "outputs/logs"))

    df = pd.read_csv(input_csv)

    ct_prompt = str(Path(cfg.paths.get("prompts_dir")) / "ct_extraction_prompt.txt")
    pet_prompt = str(Path(cfg.paths.get("prompts_dir")) / "pet_extraction_prompt.txt")

    logger.info("Running LLM extraction on %s rows", len(df))
    out_df = run_extraction(
        df,
        cfg,
        ct_prompt_path=ct_prompt,
        pet_prompt_path=pet_prompt,
        output_dir=run_dir / "extractions",
        max_rows=max_rows,
    )

    out_path = run_dir / "extracted_pairs.csv"
    out_df.to_csv(out_path, index=False)
    logger.info("Wrote extracted data to %s", out_path)


@app.command()
def select(
    input_csv: str = typer.Option(..., help="Path to extracted_pairs.csv"),
    config: str = typer.Option("configs/selection.yaml", help="Path to YAML config"),
    run_name: Optional[str] = typer.Option(None, help="Run folder name"),
) -> None:
    cfg = load_config(config, base_dir=".")
    run_dir = create_run_dir(cfg, run_name=run_name)
    logger = setup_logging(cfg.paths.get("logs_dir", "outputs/logs"))

    df = pd.read_csv(input_csv)
    selected_df, audit_df = apply_selection(df, cfg)

    selected_path = run_dir / "selected_PET_CT_studies.csv"
    audit_path = run_dir / "selection_audit_log.csv"

    selected_df.to_csv(selected_path, index=False)
    audit_df.to_csv(audit_path, index=False)

    logger.info("Selected %s studies", len(selected_df))
    logger.info("Wrote selection audit to %s", audit_path)


@app.command()
def run(
    config: str = typer.Option("configs/selection.yaml", help="Path to YAML config"),
    limit: Optional[int] = typer.Option(None, help="Limit number of pairs"),
    max_rows: Optional[int] = typer.Option(None, help="Max rows for LLM extraction"),
    run_name: Optional[str] = typer.Option(None, help="Run folder name"),
) -> None:
    cfg = load_config(config, base_dir=".")
    run_dir = create_run_dir(cfg, run_name=run_name)
    logger = setup_logging(cfg.paths.get("logs_dir", "outputs/logs"))

    sql = build_candidate_pairs_query(cfg, sample_limit=limit or cfg.selection.get("sample_limit"))
    logger.info("Running BigQuery candidate selection")
    df = run_query(cfg, sql)

    candidate_path = run_dir / "candidate_pairs.csv"
    df.to_csv(candidate_path, index=False)
    logger.info("Wrote %s rows to %s", len(df), candidate_path)

    ct_prompt = str(Path(cfg.paths.get("prompts_dir")) / "ct_extraction_prompt.txt")
    pet_prompt = str(Path(cfg.paths.get("prompts_dir")) / "pet_extraction_prompt.txt")

    logger.info("Running LLM extraction")
    extracted_df = run_extraction(
        df,
        cfg,
        ct_prompt_path=ct_prompt,
        pet_prompt_path=pet_prompt,
        output_dir=run_dir / "extractions",
        max_rows=max_rows,
    )

    extracted_path = run_dir / "extracted_pairs.csv"
    extracted_df.to_csv(extracted_path, index=False)

    selected_df, audit_df = apply_selection(extracted_df, cfg)
    selected_path = run_dir / "selected_PET_CT_studies.csv"
    audit_path = run_dir / "selection_audit_log.csv"
    selected_df.to_csv(selected_path, index=False)
    audit_df.to_csv(audit_path, index=False)

    logger.info("Selected %s studies", len(selected_df))
    logger.info("Wrote selection audit to %s", audit_path)


if __name__ == "__main__":
    app()
