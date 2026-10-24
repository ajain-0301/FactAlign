from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache
def _load(path: str) -> dict:
    p = Path(path) / "benchmark.json"
    if not p.exists():
        return {"dataset": "missing", "note": f"{p} not found", "items": [], "assignment_examples": []}
    return json.loads(p.read_text(encoding="utf-8"))


def load_benchmark() -> dict:
    return _load(get_settings().sample_data_dir)


def items(language: str = "all") -> list[dict]:
    its = load_benchmark()["items"]
    return its if language == "all" else [i for i in its if i["language"] == language]
