# demirjian-age-estimation

Pipeline for dental age estimation using the Demirjian method: DICOM preprocessing, tooth extraction with a pretrained model, and age estimation.

## Project Structure

```text
demirjian-age-estimation/
├── preprocessing/      # Stage 1: DICOM renaming, metadata extraction, PNG conversion
├── extraction/         # Stage 2: Tooth extraction with pretrained model (planned)
├── age_estimation/     # Stage 3: Demirjian staging and age estimation (planned)
├── tests/              # Unit tests
├── articles/           # Reference papers and literature
├── data/               # Raw DICOMs, converted PNGs, and intermediate datasets
├── weights/            # Pretrained and trained model weights
├── outputs/            # Predictions, metrics, and figures
├── pyproject.toml
└── README.md
```

## Setup

Requires Python 3.14+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

Run all scripts as modules from the project root.

### Stage 1: Preprocessing (`preprocessing/`)

#### 1. Rename DICOMs (`preprocessing.rename_dicom`)

Recursively renames DICOM files to `<PatientID>.dcm` (adds `_001`, `_002`, ... on collisions).

```bash
# Preview changes without modifying files
uv run python -m preprocessing.rename_dicom data/raw --dry-run

# Apply renames
uv run python -m preprocessing.rename_dicom data/raw
```

**Options:**

- `--dry-run`: preview renames without changing files
- `-w, --workers`: number of worker threads (default: CPU count)

#### 2. Extract Metadata (`preprocessing.extract_metadata`)

Extracts DICOM metadata from grouped subdirectories (`<input>/<group>/*`) into a single CSV file.

```bash
uv run python -m preprocessing.extract_metadata -i data/raw -o data/metadata.csv
```

**Options:**

- `-i, --input`: root directory containing group subdirectories (required)
- `-o, --output`: output CSV path (default: `<input>/metadata.csv`)
- `-w, --workers`: number of worker processes (default: CPU count)

**CSV columns:** `PatientID`, `PatientName`, `Age`, `PatientSex` (`1` = M, `0` = F), `KVP`, `ExposureTime`, `XRayTubeCurrent`, `Group`.

#### 3. Convert DICOM to PNG (`preprocessing.dcm2png`)

Converts DICOM files in a directory to 8-bit grayscale PNGs (applies modality/VOI LUTs and handles `MONOCHROME1`) and exports metadata to CSV.

```bash
uv run python -m preprocessing.dcm2png -i data/raw -o data/png
```

**Options:**

- `-i, --input`: directory containing DICOM files (required)
- `-o, --output`: output directory for PNGs and CSV (required)
- `-c, --csv`: CSV filename saved inside the output directory (default: `metadata.csv`)
- `-w, --workers`: number of worker processes (default: CPU count)

### Stage 2: Tooth Extraction (`extraction/`)

_(Not implemented yet.)_

### Stage 3: Age Estimation (`age_estimation/`)

_(Not implemented yet.)_

## Tests

```bash
uv run pytest
```
