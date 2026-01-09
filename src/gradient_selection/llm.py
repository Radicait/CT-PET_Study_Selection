from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

from .config import Config


def _load_prompt(path: str) -> str:
    return Path(path).read_text()


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try to extract first JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _extract_with_retry(client: OpenAI, *, prompt: str, report_text: str, cfg: Config) -> Dict[str, Any]:
    retries = int(cfg.llm.get("retries", 3))
    temperature = float(cfg.llm.get("temperature", 0.2))
    max_output_tokens = int(cfg.llm.get("max_output_tokens", 2000))
    model = cfg.llm.get("model", "gpt-5.2")

    for attempt in range(1, retries + 1):
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {"type": "input_text", "text": prompt}
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": report_text}
                        ],
                    },
                ],
                text={"format": {"type": "json_object"}},
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            text = response.output[0].content[0].text
            return _parse_json(text)
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)

    return {}


def extract_ct(report_text: str, cfg: Config, *, prompt_path: str) -> Dict[str, Any]:
    api_key = cfg.llm.get("api_key")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=api_key)
    prompt = _load_prompt(prompt_path)
    return _extract_with_retry(client, prompt=prompt, report_text=report_text, cfg=cfg)


def extract_pet(report_text: str, cfg: Config, *, prompt_path: str) -> Dict[str, Any]:
    api_key = cfg.llm.get("api_key")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=api_key)
    prompt = _load_prompt(prompt_path)
    return _extract_with_retry(client, prompt=prompt, report_text=report_text, cfg=cfg)
