# DICOM Reorganizer

This script reorganizes DICOM studies from the original tar-based structure into a patient-centric directory structure.

## Directory Structure Transformation

**Original Structure:**
```
/studies/<study_id>/series/<series_id>.tar
```

**New Structure:**
```
<output_dir>/<patient_id>/<study_id>/<series_id>/<dicom_files.dcm>
```

## Files

- `dicom_reorganizer.py` - Main reorganization script
- `run_dicom_reorganizer.py` - Convenience script with common options
- `DICOM_REORGANIZER_README.md` - This documentation

## Quick Start

### 1. Dry Run (Recommended First Step)
```bash
# Activate Python environment
source ~/.venv/bin/activate

# Run dry-run to see what would be done
cd /home/sina/gradient-data
python run_dicom_reorganizer.py --mode dry-run
```

### 2. Test Run (Process 5 Studies)
```bash
python run_dicom_reorganizer.py --mode test
```

### 3. Full Processing
```bash
python run_dicom_reorganizer.py --mode full
```

## Advanced Usage

### Custom Number of Studies
```bash
python run_dicom_reorganizer.py --mode test --max-studies 10
```

### Direct Script Usage
```bash
python dicom_reorganizer.py --help
python dicom_reorganizer.py --input-dir /path/to/studies --output-dir /path/to/output --dry-run
python dicom_reorganizer.py --max-studies 5
```

## Default Paths

- **Input Directory:** `/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/dicomweb/studies`
- **Output Directory:** `/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/reorganized`

## Features

- **Patient-centric organization:** Groups all studies by patient ID
- **Metadata preservation:** Saves series metadata as JSON files
- **Intelligent file naming:** Uses instance numbers when available
- **Comprehensive logging:** Detailed logs saved to `dicom_reorganizer.log`
- **Progress tracking:** Shows processing status for each study/series
- **Summary statistics:** Reports patient counts, file counts, modalities
- **Error handling:** Continues processing even if individual files fail
- **Dry run mode:** Preview changes without actually copying files

## Output

The script creates:
1. **Organized DICOM files** in the new directory structure
2. **series_metadata.json** in each series directory with DICOM metadata
3. **reorganization_results.json** with complete processing summary
4. **dicom_reorganizer.log** with detailed processing logs

## Example Output Structure

```
/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/reorganized/
├── GRDNW17NN4S740S1/                          # Patient ID
│   ├── 1.2.826.0.1.3680043.8.498.../         # Study UID
│   │   ├── 1.2.826.0.1.3680043.8.498.../     # Series UID
│   │   │   ├── 0001.dcm                       # DICOM files
│   │   │   ├── 0002.dcm
│   │   │   ├── ...
│   │   │   └── series_metadata.json           # Series metadata
│   │   └── another_series_uid/
│   └── another_study_uid/
├── ANOTHER_PATIENT_ID/
└── reorganization_results.json                # Overall summary
```

## Requirements

- Python 3.6+
- pydicom library (available in your .venv)
- Sufficient disk space for the reorganized files

## Troubleshooting

1. **Permission errors:** Ensure write access to output directory
2. **Disk space:** Monitor available space during processing
3. **Memory issues:** Use `--max-studies` to process in batches
4. **Log file:** Check `dicom_reorganizer.log` for detailed error information

## Safety Features

- **Dry run mode** prevents accidental file operations
- **Copy operation** preserves original files
- **Error isolation** - failed files don't stop the entire process
- **Detailed logging** for audit trail and debugging 