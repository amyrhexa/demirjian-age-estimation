from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pydicom
from pydicom.errors import InvalidDicomError
from pydicom.misc import is_dicom

PATIENT_ID_TAG = "PatientID"
METADATA_FIELDS = (
    "PatientID",
    "PatientName",
    "Age",
    "PatientSex",
    "KVP",
    "ExposureTime",
    "XRayTubeCurrent",
)
METADATA_TAGS = (
    "SOPInstanceUID",
    "PatientID",
    "PatientName",
    "PatientAge",
    "PatientSex",
    "KVP",
    "ExposureTime",
    "XRayTubeCurrent",
)
_UNSAFE_CHARS_RE = re.compile(r'[\\/*?:"<>|\x00-\x1f]')
_EMBEDDED_AGE_RE = re.compile(r"\.\s*(\d+)[A-Za-z]*\s*$")
_DICOM_AGE_RE = re.compile(r"(\d+)\s*([DWMY])?", re.IGNORECASE)
_AGE_DIVISORS = {"Y": 1, "M": 12, "W": 52, "D": 365}
_SEX_MAP = {"M": 1, "F": 0}
_FALLBACK_SUFFIXES = {".dcm", ""}


def sanitize_filename(name: str) -> str:
    cleaned = _UNSAFE_CHARS_RE.sub("_", name).strip(" .")
    return cleaned or "UNKNOWN_PATIENT"


def _detect_force_mode(path: Path) -> bool | None:
    """Return False for standard DICOM, True for preamble-less candidate, None to skip."""
    try:
        if is_dicom(path):
            return False
    except OSError:
        return None
    return True if path.suffix.lower() in _FALLBACK_SUFFIXES else None


def read_dicom_headers(path: Path, tags: tuple[str, ...]) -> pydicom.Dataset | None:
    force = _detect_force_mode(path)
    if force is None:
        return None

    requested = list(tags)
    if force and "SOPInstanceUID" not in requested:
        requested.append("SOPInstanceUID")

    try:
        ds = pydicom.dcmread(
            path,
            stop_before_pixels=True,
            specific_tags=requested,
            force=force,
        )
    except InvalidDicomError, OSError, ValueError, TypeError, RuntimeError:
        return None

    return None if (force and "SOPInstanceUID" not in ds) else ds


def read_dicom_full(path: Path) -> pydicom.Dataset | None:
    force = _detect_force_mode(path)
    if force is None:
        return None

    try:
        ds = pydicom.dcmread(path, force=force)
    except InvalidDicomError, OSError, ValueError, TypeError, RuntimeError:
        return None

    return None if (force and "SOPInstanceUID" not in ds) else ds


def _parse_int(value: Any) -> int | str:
    if value is None or value == "":
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if not value:
            return ""
        value = value[0]
    try:
        return round(float(value))
    except ValueError, TypeError:
        return ""


def _parse_sex(value: Any) -> int | str:
    if value is None:
        return ""
    return _SEX_MAP.get(str(value).strip().upper(), "")


def _parse_dicom_age(raw_age: Any) -> int | str:
    if not raw_age:
        return ""
    match = _DICOM_AGE_RE.search(str(raw_age))
    if not match:
        return ""
    amount = int(match.group(1))
    unit = (match.group(2) or "Y").upper()
    return round(amount / _AGE_DIVISORS[unit])


def parse_patient_info(raw_name: Any, raw_age: Any = None) -> tuple[str, int | str]:
    clean_name = ""
    age: int | str = ""

    if raw_name:
        raw_text = str(raw_name).strip()
        age_match = _EMBEDDED_AGE_RE.search(raw_text)
        if age_match:
            age = int(age_match.group(1))
            raw_text = raw_text[: age_match.start()]
        clean_name = " ".join(raw_text.replace("^", " ").split())

    if age == "":
        age = _parse_dicom_age(raw_age)

    return clean_name, age


def extract_metadata(ds: pydicom.Dataset) -> dict[str, Any]:
    patient_name, age = parse_patient_info(
        getattr(ds, "PatientName", None),
        getattr(ds, "PatientAge", None),
    )
    return {
        "PatientID": str(getattr(ds, "PatientID", "")).strip(),
        "PatientName": patient_name,
        "Age": age,
        "PatientSex": _parse_sex(getattr(ds, "PatientSex", None)),
        "KVP": _parse_int(getattr(ds, "KVP", None)),
        "ExposureTime": _parse_int(getattr(ds, "ExposureTime", None)),
        "XRayTubeCurrent": _parse_int(getattr(ds, "XRayTubeCurrent", None)),
    }


def write_csv(
    rows: list[dict[str, Any]],
    output_path: Path,
    fieldnames: tuple[str, ...],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
