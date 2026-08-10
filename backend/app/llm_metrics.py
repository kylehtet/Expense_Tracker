"""Token-usage logging for every Anthropic API call, tagged by feature, so
actual spend can be measured instead of estimated. Appends one JSON line per
call to logs/llm_usage.jsonl - deliberately not a DB table, since this is
read by an offline benchmark/analysis script, not queried by the app itself."""

from __future__ import annotations

import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "llm_usage.jsonl"


def log_usage(feature: str, model: str, input_tokens: int, output_tokens: int, cached: bool = False) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "feature": feature,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached": cached,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
