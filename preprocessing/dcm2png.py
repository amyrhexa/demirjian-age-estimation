#!/usr/bin/env python3
"""Convert DICOM files in a directory to 8-bit PNGs and export metadata CSV."""

from __future__ import annotations

import argparse
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image
from pydicom.pixels.processing import apply_modality_lut, apply_voi_lut

from preprocessing.dicom_utils import (
    METADATA_FIELDS,
    extract_metadata,
    read_dicom_full,
    sanitize_filename,
    write_csv,
)

logger = logging.getLogger(__name__)
PNG_MAX_VALUE = 255.0
DEFAULT_WORKERS = os.cpu_count() or 4


def dicom_to_uint8(ds: pydicom.Dataset) -> np.ndarray:
    pixels = apply_modality_lut(ds.pixel_array, ds)
    try:
        pixels = apply_voi_lut(pixels, ds)
    except ValueError, RuntimeError:
        pass

    arr = np.asarray(pixels, dtype=np.float32)
    low, high = float(arr.min()), float(arr.max())
    span = high - low

    if span <= 0.0:
        return np.zeros(arr.shape, dtype=np.uint8)

    arr -= low
    arr *= PNG_MAX_VALUE / span
    np.clip(arr, 0.0, PNG_MAX_VALUE, out=arr)
    img = arr.astype(np.uint8)

    if str(getattr(ds, "PhotometricInterpretation", "")).strip() == "MONOCHROME1":
        np.subtract(255, img, out=img)

    return img


def save_unique_png(image: np.ndarray, output_dir: Path, stem: str) -> Path:
    """Atomically create a collision-free PNG file across parallel workers."""
    pil_image = Image.fromarray(image)
    candidate = output_dir / f"{stem}.png"
    counter = 1

    while True:
        try:
            file = candidate.open("xb")
        except FileExistsError:
            candidate = output_dir / f"{stem}_{counter:03d}.png"
            counter += 1
            continue

        try:
            with file:
                pil_image.save(file, format="PNG")
            return candidate
        except Exception:
            candidate.unlink(missing_ok=True)
            raise


def _convert_file(file_path: Path, output_dir: Path) -> dict[str, Any] | None:
    ds = read_dicom_full(file_path)
    if ds is None or "PixelData" not in ds:
        return None

    try:
        metadata = extract_metadata(ds)
        stem = sanitize_filename(metadata["PatientID"] or file_path.stem)
        image = dicom_to_uint8(ds)
        save_unique_png(image, output_dir, stem)
        return metadata
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed %s: %s", file_path.name, exc)
        return None


def convert_directory(
    input_dir: Path,
    output_dir: Path,
    workers: int,
) -> list[dict[str, Any]]:
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in input_dir.iterdir() if p.is_file())
    if not files:
        return []

    worker_fn = partial(_convert_file, output_dir=output_dir)
    chunksize = max(1, min(8, len(files) // (workers * 4)))

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(worker_fn, files, chunksize=chunksize)
        return [row for row in results if row is not None]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Convert DICOM files to PNG and extract metadata to CSV."
    )
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-c", "--csv", default="metadata.csv")
    parser.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    rows = convert_directory(args.input, args.output, max(1, args.workers))
    if not rows:
        logger.warning("No valid DICOM files found in %s", args.input)
        return

    csv_path = args.output / args.csv
    write_csv(rows, csv_path, METADATA_FIELDS)
    logger.info("Processed %d files; CSV saved to %s", len(rows), csv_path)


if __name__ == "__main__":
    main()
