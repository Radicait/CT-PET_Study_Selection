from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class Config:
    paths: Dict[str, Any]
    bigquery: Dict[str, Any]
    selection: Dict[str, Any]
    llm: Dict[str, Any]


def _apply_env_overrides(cfg: Dict[str, Any]) -> None:
    project = os.getenv("BQ_PROJECT")
    if project:
        cfg.setdefault("bigquery", {})["project"] = project

    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds:
        cfg.setdefault("bigquery", {})["credentials"] = creds

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        cfg.setdefault("llm", {})["api_key"] = api_key


def _resolve_paths(cfg: Dict[str, Any], base_dir: Path) -> None:
    paths = cfg.setdefault("paths", {})
    for key in ["output_dir", "logs_dir", "prompts_dir", "sql_dir"]:
        if key in paths:
            paths[key] = str((base_dir / paths[key]).resolve())


def load_config(path: str, *, base_dir: Optional[str] = None) -> Config:
    base = Path(base_dir or Path(path).parent).resolve()
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Config file must be a YAML mapping")

    _apply_env_overrides(data)
    _resolve_paths(data, base)

    return Config(
        paths=data.get("paths", {}),
        bigquery=data.get("bigquery", {}),
        selection=data.get("selection", {}),
        llm=data.get("llm", {}),
    )


def create_run_dir(cfg: Config, *, run_name: Optional[str] = None) -> Path:
    output_dir = Path(cfg.paths.get("output_dir", "outputs"))
    template = cfg.paths.get("run_dir_template", "run_{date}")
    date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir_name = run_name or template.format(date=date_str)
    run_dir = output_dir / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
