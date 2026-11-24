#!/usr/bin/env python3
"""Recursively rename DICOM files to <PatientID>.dcm with collision handling."""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from preprocessing.dicom_utils import (
    PATIENT_ID_TAG,
    read_dicom_headers,
    sanitize_filename,
)

EXTENSION = ".dcm"
DEFAULT_WORKERS = os.cpu_count() or 4


@dataclass
class RenamePlan:
    total_files: int = 0
    skipped: int = 0
    operations: list[tuple[Path, Path]] = field(default_factory=list)
    conflicts: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def _scan_directory(root_dir: Path) -> tuple[list[Path], set[Path]]:
    files: list[Path] = []
    occupied: set[Path] = set()

    for root, dirs, filenames in os.walk(root_dir):
        root_path = Path(root)
        occupied.update(root_path / name for name in (*dirs, *filenames))
        files.extend(root_path / name for name in filenames)

    files.sort()
    return files, occupied


def _read_patient_id(path: Path) -> tuple[Path, str | None, str | None]:
    ds = read_dicom_headers(path, (PATIENT_ID_TAG,))
    if ds is None:
        return path, None, "Not a valid DICOM file"

    raw_id = getattr(ds, PATIENT_ID_TAG, None)
    if raw_id is None or not str(raw_id).strip():
        return path, None, "Missing or empty PatientID"

    return path, sanitize_filename(str(raw_id)), None


def _reserve_target(source: Path, stem: str, occupied: set[Path]) -> Path:
    candidate = source.parent / f"{stem}{EXTENSION}"
    counter = 1
    while candidate in occupied:
        candidate = source.parent / f"{stem}_{counter:03d}{EXTENSION}"
        counter += 1
    occupied.add(candidate)
    return candidate


def plan_renames(target_dir: Path, workers: int) -> RenamePlan:
    files, occupied = _scan_directory(target_dir)
    plan = RenamePlan(total_files=len(files))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_read_patient_id, files))

    for file_path, clean_id, error in results:
        if error or clean_id is None:
            plan.errors.append((file_path, error or "Read error"))
            continue

        primary = file_path.parent / f"{clean_id}{EXTENSION}"
        if file_path == primary:
            plan.skipped += 1
            continue

        target = _reserve_target(file_path, clean_id, occupied)
        plan.operations.append((file_path, target))
        if target != primary:
            plan.conflicts.append((file_path, target))

    return plan


def preview_renames(plan: RenamePlan) -> int:
    for src, dst in plan.operations:
        print(f"[DRY-RUN] {src.name} -> {dst.name}")
    return len(plan.operations)


def apply_renames(plan: RenamePlan) -> int:
    renamed = 0
    for src, dst in plan.operations:
        if os.path.lexists(dst):
            plan.errors.append((src, f"Target already exists: {dst.name}"))
            continue
        try:
            src.rename(dst)
            print(f"Renamed: {src.name} -> {dst.name}")
            renamed += 1
        except OSError as exc:
            plan.errors.append((src, f"Rename failed: {exc}"))
    return renamed


def print_summary(plan: RenamePlan, processed: int, mode: str) -> None:
    print(f"\n=== SUMMARY ({mode}) ===")
    print(f"Scanned  : {plan.total_files}")
    print(f"Renamed  : {processed}")
    print(f"Skipped  : {plan.skipped}")
    print(f"Errors   : {len(plan.errors)}")

    if plan.conflicts:
        print(f"\nCollisions resolved ({len(plan.conflicts)}):")
        for src, dst in plan.conflicts:
            print(f"  {src.name} -> {dst.name}")

    if plan.errors:
        print(f"\nErrors ({len(plan.errors)}):")
        for src, reason in plan.errors:
            print(f"  {src}: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively rename DICOM files to <PatientID>.dcm."
    )
    parser.add_argument("directory", type=Path, help="Root directory to process.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only.")
    parser.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    target_dir = args.directory.resolve()
    if not target_dir.is_dir():
        sys.exit(f"Error: '{target_dir}' is not a valid directory.")

    plan = plan_renames(target_dir, max(1, args.workers))
    if args.dry_run:
        processed = preview_renames(plan)
        print_summary(plan, processed, "DRY-RUN")
    else:
        processed = apply_renames(plan)
        print_summary(plan, processed, "LIVE")


if __name__ == "__main__":
    main()
