#!/usr/bin/env python3
"""
match_dicom.py
Match and Rename CT and PET DICOM Files by Sorting on Z-Coordinate

Many PET/CT acquisitions have reversed DICOM InstanceNumber sequences
(e.g., CT might list the head as slice #1, while PET lists the feet as slice #1).
To properly match them from foot to head, this script sorts all DICOM slices
by their z-position (SliceLocation or ImagePositionPatient[2]), and then
renames them in ascending z-order.

For each study found in the CT and PET folders:

1. Load all DICOM files and read:
   - Study ID (StudyID or StudyInstanceUID as fallback)
   - Z-coordinate (from `SliceLocation` or `ImagePositionPatient[2]`)

2. Sort the slices by z-coordinate (lowest z = slice #1).

3. Match slices from CT and PET one-to-one by **index** (0, 1, 2, ...).
   - If the difference in z-coordinates at the same index exceeds the
     specified tolerance, that slice pair is skipped (error is logged).
   - If total number of slices in CT != total number of slices in PET,
     a warning/error is logged, but we still try to match by the smaller count.

4. Rename each matched pair to: <study_id>_<slice_index_3digit>.dcm
   - For example:  "1.2.3.4_001.dcm", "1.2.3.4_002.dcm", ...

5. Print a summary report at the end.

Requires:
    pydicom >= 2.2.0

Usage (typical):
    python match_dicom.py \
        --ct_folder /path/to/ct/folder \
        --pet_folder /path/to/pet/folder \
        --tolerance 2.0
"""

import os
import argparse
import pydicom

def get_dicom_data(file_path):
    """
    Read the DICOM file to extract:
      - Study ID (using StudyID or falling back to StudyInstanceUID).
      - Z-coordinate from either SliceLocation or ImagePositionPatient[2].

    Returns:
        (study_id, z_value)

    Raises:
        ValueError: if the file cannot be read or mandatory fields are missing.
    """
    try:
        ds = pydicom.dcmread(file_path, stop_before_pixels=True)
    except Exception as e:
        raise ValueError(f"Error reading DICOM file {file_path}: {e}")

    # Get Study ID or fallback to Study Instance UID
    study_id = ds.get("StudyID") or ds.get("StudyInstanceUID")
    if not study_id:
        raise ValueError(f"No StudyID or StudyInstanceUID found in file {file_path}")
    study_id = str(study_id).strip()

    # Get z-coordinate from SliceLocation or ImagePositionPatient
    z = None
    if "SliceLocation" in ds:
        try:
            z = float(ds.SliceLocation)
        except Exception as e:
            raise ValueError(f"Error converting SliceLocation in file {file_path}: {e}")
    elif "ImagePositionPatient" in ds:
        try:
            z = float(ds.ImagePositionPatient[2])
        except Exception as e:
            raise ValueError(f"Error extracting z from ImagePositionPatient in file {file_path}: {e}")

    if z is None:
        raise ValueError(f"No z-coordinate found (SliceLocation or ImagePositionPatient) in file {file_path}")

    return study_id, z


def build_study_slices_dict(folder_path):
    """
    Walk through the specified folder, find all '.dcm' files, and extract:
        study_id -> list of (file_path, z_value)

    Returns:
        A dictionary of the form:
            {
                study_id_1: [(file_path_1, z_1), (file_path_2, z_2), ...],
                study_id_2: [...]
            }

    Any files that produce errors on reading are skipped (error is printed).
    """
    study_dict = {}

    if not os.path.isdir(folder_path):
        print(f"Warning: {folder_path} is not a directory or does not exist.")
        return study_dict

    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.dcm'):
            file_path = os.path.join(folder_path, filename)
            try:
                study_id, z = get_dicom_data(file_path)
            except ValueError as e:
                print(f"Skipping file due to error: {e}")
                continue

            if study_id not in study_dict:
                study_dict[study_id] = []
            study_dict[study_id].append((file_path, z))

    return study_dict


def match_and_rename_by_z(ct_folder, pet_folder, tolerance=2.0):
    """
    Match DICOM files in ct_folder and pet_folder by sorting them on z-coordinate.
    Then rename each matched pair in ascending z order for each study.

    Steps:
      1. Build dictionaries of CT and PET slices grouped by study_id.
      2. For each common study_id:
         - Sort CT slices by z ascending
         - Sort PET slices by z ascending
         - If counts differ, log a warning but match up to the min length
         - Check z-differences pairwise (index by index in sorted order)
         - If difference > tolerance, skip renaming that pair
         - Otherwise rename both files to <study_id>_<###>.dcm
      3. Print a summary

    Args:
      ct_folder (str): Path to folder containing CT DICOMs.
      pet_folder (str): Path to folder containing PET DICOMs.
      tolerance (float): Allowed difference in z (mm) for matching slices.
    """
    # 1. Build dictionary: study_id -> list of (filepath, z)
    ct_study_dict = build_study_slices_dict(ct_folder)
    pet_study_dict = build_study_slices_dict(pet_folder)

    # Find the intersection of study IDs
    common_studies = set(ct_study_dict.keys()) & set(pet_study_dict.keys())
    if not common_studies:
        print("No common study IDs found between the CT and PET folders.")
        return

    # Prepare overall summary
    summary = {}

    for study_id in sorted(common_studies):
        summary[study_id] = {
            "ct_count": 0,
            "pet_count": 0,
            "matched_slices": 0,
            "errors": [],
            "warnings": []
        }

        ct_slices = ct_study_dict[study_id]
        pet_slices = pet_study_dict[study_id]

        # Sort each list by ascending z
        ct_slices_sorted = sorted(ct_slices, key=lambda x: x[1])  # x = (filepath, z)
        pet_slices_sorted = sorted(pet_slices, key=lambda x: x[1])

        ct_count = len(ct_slices_sorted)
        pet_count = len(pet_slices_sorted)

        summary[study_id]["ct_count"] = ct_count
        summary[study_id]["pet_count"] = pet_count

        if ct_count != pet_count:
            msg = (f"Warning: study {study_id} has {ct_count} CT slices vs {pet_count} PET slices. "
                   "Will match up to the smaller count.")
            summary[study_id]["warnings"].append(msg)
            print(msg)

        # Match up to the min length
        n = min(ct_count, pet_count)
        matched_slices = 0

        for i in range(n):
            ct_file, ct_z = ct_slices_sorted[i]
            pet_file, pet_z = pet_slices_sorted[i]
            z_diff = abs(ct_z - pet_z)

            if z_diff > tolerance:
                # Large mismatch in z => skip
                err_msg = (f"Study {study_id} index {i}: z mismatch: "
                           f"CT z={ct_z:.2f}, PET z={pet_z:.2f}, diff={z_diff:.2f} > tolerance={tolerance}")
                summary[study_id]["errors"].append(err_msg)
                # print(err_msg)
                continue

            # Construct new file name
            new_basename = f"{study_id}_{i+1:03d}.dcm"
            new_ct_path = os.path.join(ct_folder, new_basename)
            new_pet_path = os.path.join(pet_folder, new_basename)

            # Rename CT file
            try:
                if os.path.exists(new_ct_path):
                    warn_msg = f"Study {study_id}: Target file {new_ct_path} already exists. Skipping rename."
                    summary[study_id]["trivial_warnings"].append(warn_msg)
                    # print(warn_msg)
                else:
                    os.rename(ct_file, new_ct_path)
            except OSError as e:
                err_msg = f"Error renaming CT file {ct_file} -> {new_ct_path}: {e}"
                summary[study_id]["errors"].append(err_msg)
                # print(err_msg)
                continue

            # Rename PET file
            try:
                if os.path.exists(new_pet_path):
                    warn_msg = f"Study {study_id}: Target file {new_pet_path} already exists. Skipping rename."
                    summary[study_id]["trivial_warnings"].append(warn_msg)
                    # print(warn_msg)
                else:
                    os.rename(pet_file, new_pet_path)
            except OSError as e:
                err_msg = f"Error renaming PET file {pet_file} -> {new_pet_path}: {e}"
                summary[study_id]["errors"].append(err_msg)
                # print(err_msg)
                continue

            matched_slices += 1

        summary[study_id]["matched_slices"] = matched_slices
        print(f"Study {study_id}: Matched and renamed {matched_slices} slices.\n")

    # Final summary
    print("\n===== FINAL SUMMARY =====")
    for study_id, data in summary.items():
        print(f"Study: {study_id}")
        print(f"  CT slices: {data['ct_count']}, PET slices: {data['pet_count']}")
        print(f"  Matched & renamed slices: {data['matched_slices']}")
        if data["warnings"]:
            print("  Warnings:")
            for w in data["warnings"]:
                print(f"    - {w}")
        if data["errors"]:
            print("  Errors:")
            for e in data["errors"]:
                print(f"    - {e}")
        print("")


def run_unit_test():
    """
    Simple unit test using hardcoded paths (for demonstration).
    Update the paths for your local file system if needed.
    """
    ct_folder = "/path/to/ct/test_data"
    pet_folder = "/path/to/pet/test_data"
    tolerance = 2.0

    print("Running unit test with hardcoded paths:")
    print(f"  CT folder:  {ct_folder}")
    print(f"  PET folder: {pet_folder}")
    print(f"  Tolerance:  {tolerance}")
    match_and_rename_by_z(ct_folder, pet_folder, tolerance)


def main():
    """
    Command-line entry point.

    Typical usage:
      python match_dicom.py \
        --ct_folder /path/to/ct/folder \
        --pet_folder /path/to/pet/folder \
        --tolerance 2.0
    """
    parser = argparse.ArgumentParser(
        description="Match and rename CT/PET DICOM slices by sorting on z-coordinate."
    )
    parser.add_argument("--ct_folder", required=False, help="Folder containing CT DICOM files")
    parser.add_argument("--pet_folder", required=False, help="Folder containing PET DICOM files")
    parser.add_argument("--tolerance", type=float, default=0.5, help="z-position tolerance in mm (default=2.0)")
    parser.add_argument("--test", action="store_true", help="Run simple unit test instead of processing user folders")

    args = parser.parse_args()

    if args.test:
        run_unit_test()
    else:
        if not args.ct_folder or not args.pet_folder:
            print("CT or PET folder not specified. Use --test or provide both --ct_folder and --pet_folder.")
            return
        match_and_rename_by_z(args.ct_folder, args.pet_folder, args.tolerance)


if __name__ == "__main__":
    main()
