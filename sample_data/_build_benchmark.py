
#!/usr/bin/env python3
"""
Build 12 FactAlign benchmarks from XL-Sum validation datasets.

Output:
    sample_data/
        _build_benchmark.py
        benchmarks/
            benchmark_01.json
            ...
            benchmark_12.json
            manifest.json

Configuration:
    6 English-only benchmarks
    6 Hindi-only benchmarks
    29 documents per benchmark
    Fixed random seed for reproducibility
"""

import json
import random
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ENGLISH_DATASET = (
    BASE_DIR.parent
    / "dataset"
    / "english_XLSum_v2.0"
    / "english_val.jsonl"
)

HINDI_DATASET = (
    BASE_DIR.parent
    / "dataset"
    / "hindi_XLSum_v2.0"
    / "hindi_val.jsonl"
)

OUTPUT_DIR = BASE_DIR / "benchmarks"

RANDOM_SEED = 42

BENCHMARKS_PER_LANGUAGE = 6
DOCUMENTS_PER_BENCHMARK = 29

LANGUAGES = {
    "english": ENGLISH_DATASET,
    "hindi": HINDI_DATASET,
}


# ============================================================
# Dataset Loading
# ============================================================

def load_jsonl(file_path: Path) -> list:
    """Load records from a JSONL dataset."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    records = []

    with file_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):

            if not line.strip():
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {file_path}, "
                    f"line {line_number}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected JSON object at line {line_number}"
                )

            records.append(record)

    return records


# ============================================================
# Record Normalization
# ============================================================

def get_first(record: dict, *keys):
    """Return the first available non-null field."""

    for key in keys:
        value = record.get(key)

        if value is not None:
            return value

    return None


def normalize_record(
    record: dict,
    language: str,
    benchmark_number: int,
    document_number: int,
) -> dict:
    """
    Convert an XL-Sum record into the FactAlign format.

    Original dataset information is preserved.
    No factuality labels or claims are generated.
    """

    title = get_first(
        record,
        "title",
        "headline",
    )

    source = get_first(
        record,
        "text",
        "article",
        "source",
    )

    reference_summary = get_first(
        record,
        "summary",
        "reference_summary",
    )

    if not isinstance(title, str) or not title.strip():
        raise ValueError("Record is missing a valid title.")

    if not isinstance(source, str) or not source.strip():
        raise ValueError("Record is missing a valid source article.")

    if (
        not isinstance(reference_summary, str)
        or not reference_summary.strip()
    ):
        raise ValueError("Record is missing a valid reference summary.")

    original_id = get_first(
        record,
        "id",
        "dataset_id",
    )

    # Stable benchmark-specific document ID.
    document_id = (
        f"benchmark_{benchmark_number:02d}"
        f"_doc_{document_number:02d}"
    )

    # Preserve the original ID separately in pair_id
    # and dataset_id when available.
    pair_id = (
        str(original_id)
        if original_id is not None
        else document_id
    )

    normalized = {
        "id": document_id,
        "pair_id": pair_id,
        "language": language,
        "title": title,
        "source": source,
        "reference_summary": reference_summary,
        "labeled_claims": [],
    }

    if original_id is not None:
        normalized["dataset_id"] = original_id

    return normalized


# ============================================================
# Benchmark Generation
# ============================================================

def generate_benchmarks():
    """Generate all 12 language-specific benchmarks."""

    rng = random.Random(RANDOM_SEED)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Load both datasets.
    datasets = {
        language: load_jsonl(path)
        for language, path in LANGUAGES.items()
    }

    # Validate dataset sizes before sampling.
    required_records = (
        BENCHMARKS_PER_LANGUAGE
        * DOCUMENTS_PER_BENCHMARK
    )

    for language, records in datasets.items():

        if len(records) < required_records:
            raise ValueError(
                f"{language} dataset contains only "
                f"{len(records)} records. "
                f"At least {required_records} unique records "
                f"are required."
            )

    manifest = {
        "project": "FactAlign",
        "dataset": "XL-Sum",
        "random_seed": RANDOM_SEED,
        "documents_per_benchmark": DOCUMENTS_PER_BENCHMARK,
        "benchmarks_per_language": BENCHMARKS_PER_LANGUAGE,
        "total_benchmarks": 12,
        "total_documents": (
            12 * DOCUMENTS_PER_BENCHMARK
        ),
        "languages": {},
        "benchmarks": [],
    }

    benchmark_number = 0

    # Generate English benchmarks first, followed by Hindi.
    for language in ("english", "hindi"):

        records = datasets[language]

        # Shuffle once and distribute without replacement.
        shuffled_records = records.copy()
        rng.shuffle(shuffled_records)

        manifest["languages"][language] = {
            "source_file": str(
                LANGUAGES[language].relative_to(BASE_DIR.parent)
            ),
            "benchmark_count": BENCHMARKS_PER_LANGUAGE,
            "total_documents": required_records,
        }

        for benchmark_index in range(
            BENCHMARKS_PER_LANGUAGE
        ):

            benchmark_number += 1

            start = (
                benchmark_index
                * DOCUMENTS_PER_BENCHMARK
            )

            end = (
                start
                + DOCUMENTS_PER_BENCHMARK
            )

            selected_records = shuffled_records[start:end]

            benchmark_documents = []

            for document_number, record in enumerate(
                selected_records,
                start=1,
            ):

                document = normalize_record(
                    record=record,
                    language=language,
                    benchmark_number=benchmark_number,
                    document_number=document_number,
                )

                benchmark_documents.append(document)

            # Validate benchmark language purity.
            assert len(benchmark_documents) == 29

            assert all(
                doc["language"] == language
                for doc in benchmark_documents
            )

            assert all(
                doc["labeled_claims"] == []
                for doc in benchmark_documents
            )

            filename = (
                f"benchmark_{benchmark_number:02d}.json"
            )

            output_path = OUTPUT_DIR / filename

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    benchmark_documents,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

                file.write("\n")

            manifest["benchmarks"].append({
                "file": filename,
                "benchmark_number": benchmark_number,
                "language": language,
                "document_count": len(benchmark_documents),
                "annotations_complete": False,
            })

            print(
                f"Generated {filename}: "
                f"{len(benchmark_documents)} "
                f"{language} documents"
            )

    # Save manifest.
    manifest["generated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    manifest_path = OUTPUT_DIR / "manifest.json"

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    # Final validation.
    validate_benchmarks()

    print("\n========================================")
    print("FactAlign benchmark generation complete!")
    print("========================================")
    print(f"Benchmarks: 12")
    print(f"English:    6")
    print(f"Hindi:      6")
    print(f"Documents:  348")
    print(f"Per file:   29")
    print(f"Seed:       {RANDOM_SEED}")
    print(f"Output:     {OUTPUT_DIR}")
    print("========================================")


# ============================================================
# Validation
# ============================================================

def validate_benchmarks():
    """Validate benchmark count, structure, and language purity."""

    expected_files = [
        f"benchmark_{i:02d}.json"
        for i in range(1, 13)
    ]

    english_count = 0
    hindi_count = 0

    for index, filename in enumerate(
        expected_files,
        start=1,
    ):

        path = OUTPUT_DIR / filename

        if not path.exists():
            raise AssertionError(
                f"Missing benchmark: {filename}"
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            documents = json.load(file)

        if len(documents) != DOCUMENTS_PER_BENCHMARK:
            raise AssertionError(
                f"{filename} has {len(documents)} documents "
                f"instead of 29."
            )

        expected_language = (
            "english" if index <= 6 else "hindi"
        )

        languages = {
            document["language"]
            for document in documents
        }

        if languages != {expected_language}:
            raise AssertionError(
                f"Language mixing or incorrect language "
                f"in {filename}: {languages}"
            )

        required_fields = {
            "id",
            "pair_id",
            "language",
            "title",
            "source",
            "reference_summary",
            "labeled_claims",
        }

        for document in documents:

            missing = (
                required_fields
                - document.keys()
            )

            if missing:
                raise AssertionError(
                    f"{filename}: missing fields {missing}"
                )

            if document["labeled_claims"] != []:
                raise AssertionError(
                    f"{filename}: fabricated or prefilled claims"
                )

            if not document["title"].strip():
                raise AssertionError(
                    f"{filename}: empty title"
                )

            if not document["source"].strip():
                raise AssertionError(
                    f"{filename}: empty source"
                )

            if not document["reference_summary"].strip():
                raise AssertionError(
                    f"{filename}: empty reference summary"
                )

        if expected_language == "english":
            english_count += 1
        else:
            hindi_count += 1

    if english_count != 6 or hindi_count != 6:
        raise AssertionError(
            "Incorrect language distribution."
        )

    # Validate manifest.
    manifest_path = OUTPUT_DIR / "manifest.json"

    if not manifest_path.exists():
        raise AssertionError("Missing manifest.json")

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        manifest = json.load(file)

    if len(manifest["benchmarks"]) != 12:
        raise AssertionError(
            "Manifest benchmark count is incorrect."
        )

    print("\nValidation passed:")
    print("- 12 benchmark files found")
    print("- 29 documents in every benchmark")
    print("- 6 English-only benchmarks")
    print("- 6 Hindi-only benchmarks")
    print("- No mixed-language benchmarks")
    print("- All required FactAlign fields present")
    print("- All labeled_claims arrays are empty")
    print("- Manifest exists and is valid")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    generate_benchmarks()
