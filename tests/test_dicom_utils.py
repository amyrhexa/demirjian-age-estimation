from pathlib import Path

import numpy as np
from pydicom.datadict import tag_for_keyword

from preprocessing.dcm2png import save_unique_png
from preprocessing.dicom_utils import (
    METADATA_TAGS,
    parse_patient_info,
    sanitize_filename,
)


def test_metadata_tags_are_valid_dicom_keywords() -> None:
    assert all(tag_for_keyword(tag) is not None for tag in METADATA_TAGS)


def test_parse_patient_info() -> None:
    assert parse_patient_info("Smith^John.45") == ("Smith John", 45)
    assert parse_patient_info("Dr.Smith^John") == ("Dr.Smith John", "")
    assert parse_patient_info("Dr.Smith^John.45Y") == ("Dr.Smith John", 45)
    assert parse_patient_info("Smith^Baby", "024M") == ("Smith Baby", 2)


def test_sanitize_filename() -> None:
    assert sanitize_filename(" 123/45:6 ") == "123_45_6"
    assert sanitize_filename("..") == "UNKNOWN_PATIENT"


def test_save_unique_png_collision(tmp_path: Path) -> None:
    img = np.zeros((4, 4), dtype=np.uint8)
    first = save_unique_png(img, tmp_path, "P01")
    second = save_unique_png(img, tmp_path, "P01")
    assert first.name == "P01.png"
    assert second.name == "P01_001.png"
