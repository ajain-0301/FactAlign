
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    """
    Load and combine all benchmark JSON files from the benchmarks directory.

    Expected structure:
        sample_data/
            benchmarks/
                benchmark_01.json
                benchmark_02.json
                benchmark_03.json

    Each JSON file must contain a list of benchmark documents.
    """

    benchmark_dir = Path(path) / "benchmarks"

    if not benchmark_dir.exists():
        return {
            "dataset": "missing",
            "note": f"Benchmark directory not found: {benchmark_dir}",
            "items": [],
            "benchmark_count": 0,
            "total_items": 0,
            "benchmarks": [],
            "assignment_examples": [],
        }

    benchmark_files = sorted(benchmark_dir.glob("benchmark_*.json"))

    all_items: list[dict] = []
    benchmark_metadata: list[dict] = []

    for file in benchmark_files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"Could not load benchmark file {file.name}: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                f"Invalid benchmark format in {file.name}: expected a JSON list."
            )

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Invalid document at index {index} in {file.name}: "
                    "expected a JSON object."
                )

            required = ("id", "source", "title", "language",
                        "reference_summary", "labeled_claims", "pair_id")

            missing = [key for key in required if key not in item]

            if missing:
                raise ValueError(
                    f"Missing fields in {file.name}, document {index}: "
                    f"{', '.join(missing)}"
                )

            all_items.append(item)

        benchmark_metadata.append({
            "file": file.name,
            "document_count": len(data),
            "language": data[0].get("language") if data else None,
        })

    if not benchmark_files:
        note = f"No benchmark_*.json files found in {benchmark_dir}"
        dataset = "missing"
    else:
        note = (
            f"Loaded {len(benchmark_files)} benchmark files "
            f"containing {len(all_items)} documents."
        )
        dataset = "XL-Sum"

    return {
        "dataset": dataset,
        "note": note,
        "benchmark_count": len(benchmark_files),
        "total_items": len(all_items),
        "items": all_items,
        "benchmarks": benchmark_metadata,
        "assignment_examples": [],
    }


@lru_cache(maxsize=4)
def _load_labelled_items(path: str) -> list[dict]:
    p = Path(path) / "benchmark.json"
    if not p.exists():
        return []

    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"Invalid labelled benchmark format in {p.name}: expected an items list.")
    items = data["items"]
    return [item for item in items if isinstance(item, dict) and item.get("labeled_claims")]


def load_benchmark() -> dict:
    """
    Return the complete combined benchmark dataset.
    """
    return _load(str(Path(get_settings().sample_data_dir).resolve()))


def labeled_items() -> list[dict]:
    """Return documents with author-written gold claims for verifier evaluation."""
    return _load_labelled_items(str(Path(get_settings().sample_data_dir).resolve()))


def items(language: str = "all") -> list[dict]:
    """
    Return benchmark documents filtered by language.

    Supported languages:
        all
        hi
        en
        hinglish
    """

    benchmark_items = load_benchmark()["items"]

    if language == "all":
        return benchmark_items

    supported_languages = {"hi", "en", "hinglish"}

    if language not in supported_languages:
        raise ValueError(
            f"Unsupported language '{language}'. "
            f"Choose from: all, hi, en, hinglish."
        )

    return [
        item
        for item in benchmark_items
        if item["language"] == language
    ]


def clear_cache() -> None:
    """
    Clear cached benchmark data after adding or modifying benchmark files.
    """
    _load.cache_clear()
    _load_labelled_items.cache_clear()
