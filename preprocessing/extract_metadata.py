#!/usr/bin/env python3
"""Extract DICOM metadata from grouped subdirectories into a CSV file."""

from __future__ import annotations

import argparse
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from preprocessing.dicom_utils import (
    METADATA_FIELDS,
    METADATA_TAGS,
    extract_metadata,
    read_dicom_headers,
    write_csv,
)

logger = logging.getLogger(__name__)
CSV_HEADERS = (*METADATA_FIELDS, "Group")
DEFAULT_WORKERS = os.cpu_count() or 4


def _extract_group_record(task: tuple[str, Path]) -> dict[str, Any] | None:
    group, file_path = task
    ds = read_dicom_headers(file_path, METADATA_TAGS)
    if ds is None:
        return None
    record = extract_metadata(ds)
    record["Group"] = group
    return record


def extract_dataset(input_dir: Path, workers: int) -> list[dict[str, Any]]:
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    group_dirs = sorted(p for p in input_dir.iterdir() if p.is_dir())
    if not group_dirs:
        raise RuntimeError(f"No group subdirectories found in {input_dir}")

    tasks = [
        (group_dir.name, file_path)
        for group_dir in group_dirs
        for file_path in sorted(p for p in group_dir.iterdir() if p.is_file())
    ]
    if not tasks:
        return []

    chunksize = max(1, min(32, len(tasks) // (workers * 4)))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_extract_group_record, tasks, chunksize=chunksize)
        return [row for row in results if row is not None]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Extract metadata from grouped DICOM directories to CSV."
    )
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    output_csv = args.output or (args.input / "metadata.csv")
    rows = extract_dataset(args.input, max(1, args.workers))
    write_csv(rows, output_csv, CSV_HEADERS)
    logger.info("Saved %d records to %s", len(rows), output_csv)


if __name__ == "__main__":
    main()
