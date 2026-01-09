#!/usr/bin/env python
""" 
batch_rename.py

Enhanced script to classify main CT and PET AC folders from a large set of 
nested DICOM folders, then run rename_dicom_files() for each matched pair.

- Uses Modality (CT vs PT)
- Uses SeriesDescription to exclude localizers, scouts, MIPs, screen captures, etc.
- Uses ImageType to exclude "REFORMATTED", "SECONDARY", "FUSED", "LOCALIZER", etc.
- Looks for "AC" in SeriesDescription for PET to label as attenuation-corrected (pet_priority=2).
- If multiple candidates, picks the largest set of slices (and highest pet_priority).
- Produces a JSON summary of matched folders.
- Has a --dry-run option to check matches without renaming.

Requires:
    - pydicom
    - match_dicom.py (providing rename_dicom_files)
"""

import os
import argparse
import json
import pydicom
from match_dicom import match_and_rename_by_z

###############################################################################
#                  CUSTOMIZABLE EXCLUSION AND CLASSIFICATION RULES
###############################################################################

# Keywords in the SeriesDescription that strongly indicate we do NOT want this folder.
# (localizers, scouts, 2D topograms, MIPs, screen captures, fused recons, etc.)
# Note: We previously had '3d' here, which can exclude legitimate "PET AC 3D BODY" series.
EXCLUDED_SERIESDESC_KEYWORDS = {
    "localizer",
    "topogram",
    "topo",
    "scout",
    "mip",
    "movie",
    "captures",       # e.g. "scrn captures" or "screen captures"
    "screen",
    "fusion",
    "fused",
    "secondary",
    "range",
    "mpr",
    "coronal",
    "sagittal"
    # Removed "3d" to allow "PET AC 3D BODY"
}

# Keywords in the ImageType (0008,0008) that indicate an unwanted derived or reformat series.
# We skip if ANY of these words appear in the list elements of ImageType.
EXCLUDED_IMAGETYPE_KEYWORDS = {
    "secondary",
    "fused",
    "mpr",
    "localizer",
    "scout",
    "coronal",
    "sagittal",
    "captures",
    "screen",
    "topogram",
    "topo",
    "reformatted"     # Some scanners label 2D/3D reformat with "REFORMATTED"
}

def is_excluded_by_series_desc(series_desc_lower):
    """Return True if the SeriesDescription hits any excluded pattern."""
    for kw in EXCLUDED_SERIESDESC_KEYWORDS:
        if kw in series_desc_lower:
            return True
    return False

def is_excluded_by_image_type(image_type_list):
    """Return True if ImageType includes any excluded keyword."""
    lower_list = [itm.lower() for itm in image_type_list]
    for itm in lower_list:
        for kw in EXCLUDED_IMAGETYPE_KEYWORDS:
            if kw in itm:
                return True
    return False

def classify_series(ds, folder_path, dcm_count):
    """
    Classifies a single DICOM series as potential "CT" or "PET AC" or None
    by checking:
      - Modality
      - SeriesDescription (exclude certain keywords, check for AC)
      - ImageType (exclude 'REFORMATTED','SECONDARY','FUSED',etc.)
    Returns:
      (study_id, candidate_type, pet_priority, series_desc)
      or None if we do not want this series as a main CT or PET folder.
    """
    # Basic fields
    study_id = ds.get("StudyID") or ds.get("StudyInstanceUID")
    if not study_id:
        return None
    study_id = str(study_id).strip()

    modality = str(ds.get("Modality", "")).upper()
    series_desc = str(ds.get("SeriesDescription", ""))
    series_desc_lower = series_desc.lower()

    # Check for ImageType
    image_type_list = ds.get("ImageType", [])
    if not isinstance(image_type_list, (list, tuple)):
        image_type_list = [str(image_type_list)]

    # Exclusion checks:
    if is_excluded_by_series_desc(series_desc_lower):
        return None
    if is_excluded_by_image_type(image_type_list):
        return None

    # Classification
    if modality == "CT":
        # We'll treat it as candidate "CT"
        return (study_id, "CT", 0, series_desc)

    if modality == "PT":
        # If "nac" is found, skip it in this example (or make it pet_priority=1 if you prefer fallback).
        if "nac" in series_desc_lower:
            return None
        # If "ac" is present, treat it as the main AC PET
        if "ac" in series_desc_lower:
            return (study_id, "PET", 2, series_desc)
        # else skip (for a typical environment, or set pet_priority=1 to handle non-AC PET)
        return None

    return None

###############################################################################
#                        SCANNING & GATHERING LOGIC
###############################################################################

def is_dicom_folder(folder_path):
    """Check if the folder contains any file ending with .dcm."""
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.dcm'):
            return True
    return False

def get_folder_info(folder_path):
    """Check a sample DICOM file in folder_path; return classification info if any."""
    dcm_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.dcm')]
    if not dcm_files:
        return None

    sample_file = os.path.join(folder_path, dcm_files[0])
    try:
        ds = pydicom.dcmread(sample_file, stop_before_pixels=True)
    except Exception as e:
        print(f"Error reading DICOM file {sample_file}: {e}")
        return None

    result = classify_series(ds, folder_path, len(dcm_files))
    if result is None:
        return None

    study_id, candidate_type, pet_priority, series_desc = result
    return {
        "study_id": study_id,
        "candidate_type": candidate_type,        # "CT" or "PET"
        "pet_priority": pet_priority,            # 2 for AC, or 0 for CT
        "folder_path": folder_path,
        "dcm_count": len(dcm_files),
        "series_desc": series_desc
    }

def gather_study_folders(root_folder):
    """
    Walk through the root_folder recursively, find potential CT/PET series folders,
    then group them by study_id. For each study, we keep:
      - The CT candidate with the largest DICOM count.
      - The PET candidate with the highest pet_priority, then largest count.
    Returns a dict:
      {
        study_id: {
          "CT": (folder, count, series_desc),
          "PET": (folder, count, pet_priority, series_desc)
        }
      }
    """
    studies = {}
    for dirpath, dirnames, filenames in os.walk(root_folder):
        if not filenames:
            continue
        if not any(f.lower().endswith('.dcm') for f in filenames):
            continue

        info = get_folder_info(dirpath)
        if info is None:
            continue

        s_id = info["study_id"]
        ctype = info["candidate_type"]
        pp = info["pet_priority"]
        fpath = info["folder_path"]
        dcount = info["dcm_count"]
        sdesc = info["series_desc"]

        if s_id not in studies:
            studies[s_id] = {}

        if ctype == "CT":
            # Keep the CT with the largest dcm_count
            if "CT" not in studies[s_id]:
                studies[s_id]["CT"] = (fpath, dcount, sdesc)
            else:
                _, existing_count, _ = studies[s_id]["CT"]
                if dcount > existing_count:
                    studies[s_id]["CT"] = (fpath, dcount, sdesc)

        elif ctype == "PET":
            # Keep the PET with the best pet_priority, then largest dcm_count
            if "PET" not in studies[s_id]:
                studies[s_id]["PET"] = (fpath, dcount, pp, sdesc)
            else:
                _, existing_count, existing_pp, _ = studies[s_id]["PET"]
                if pp > existing_pp:
                    studies[s_id]["PET"] = (fpath, dcount, pp, sdesc)
                elif pp == existing_pp and dcount > existing_count:
                    studies[s_id]["PET"] = (fpath, dcount, pp, sdesc)

    return studies

###############################################################################
#                                MAIN SCRIPT
###############################################################################

def main():
    parser = argparse.ArgumentParser(
        description="Batch process DICOM studies: detect main CT and PET AC folders, "
                    "then match & rename using rename_dicom_files."
    )
    parser.add_argument("--root", required=True,
                        help="Path to the root folder containing all studies")
    parser.add_argument("--tolerance", type=float, default=0.5,
                        help="Tolerance (in mm) for matching z-coordinates (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Perform a dry-run: identify folders and print info without renaming files.")
    parser.add_argument("--json-file", type=str, default="study_folders.json",
                        help="Filename to save study folder information in JSON format.")
    args = parser.parse_args()
    
    root_folder = args.root
    tolerance = args.tolerance
    dry_run = args.dry_run
    json_filename = args.json_file

    if not os.path.isdir(root_folder):
        print(f"Error: Provided root folder does not exist: {root_folder}")
        return

    print(f"Scanning root folder: {root_folder}")
    studies = gather_study_folders(root_folder)
    if not studies:
        print("No candidate DICOM study folders found.")
        return
    
    # Save classification results to JSON
    try:
        out_dict = {}
        for study_id, data in studies.items():
            entry = {}
            if "CT" in data:
                (ct_folder, ct_count, ct_desc) = data["CT"]
                entry["CT"] = (ct_folder, ct_count, ct_desc)
            if "PET" in data:
                (pet_folder, pet_count, pet_priority, pet_desc) = data["PET"]
                entry["PET"] = (pet_folder, pet_count, pet_priority, pet_desc)
            out_dict[study_id] = entry

        with open(json_filename, "w") as out_f:
            json.dump(out_dict, out_f, indent=4)
        print(f"\nStudy folder information saved to JSON file: {json_filename}")
    except Exception as e:
        print(f"Error saving JSON file {json_filename}: {e}")

    total_studies = len(studies)
    processed_studies = 0
    skipped_studies = 0

    for study_id, folders in studies.items():
        print(f"\nStudy ID: {study_id}")
        ct_candidate = folders.get("CT")
        pet_candidate = folders.get("PET")

        if ct_candidate is None:
            print(f"  Skipping study {study_id}: No main CT folder found.")
            skipped_studies += 1
            continue

        if pet_candidate is None:
            print(f"  Skipping study {study_id}: No PET AC folder found.")
            skipped_studies += 1
            continue

        ct_folder, ct_count, ct_desc = ct_candidate
        pet_folder, pet_count, pet_priority, pet_desc = pet_candidate

        print(f"  CT folder: {ct_folder}")
        print(f"    Series Description: {ct_desc}")
        print(f"    Number of DCM files: {ct_count}")
        print(f"  PET folder: {pet_folder}")
        print(f"    Series Description: {pet_desc}")
        print(f"    Number of DCM files: {pet_count}")
        print(f"    PET priority: {pet_priority}")

        if dry_run:
            print("  Dry-run enabled: skipping renaming of files for this study.")
            processed_studies += 1
            continue

        try:
            match_and_rename_by_z(ct_folder, pet_folder, tolerance)
            processed_studies += 1
        except Exception as e:
            print(f"Error processing study {study_id}:\n"
                  f"  CT folder: {ct_folder}\n"
                  f"  PET folder: {pet_folder}\n"
                  f"  {e}")

    print("\nSummary:")
    print(f"  Total studies found: {total_studies}")
    print(f"  Processed studies:   {processed_studies}")
    print(f"  Skipped studies:     {skipped_studies}")

if __name__ == "__main__":
    main()
