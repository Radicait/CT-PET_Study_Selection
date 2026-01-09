#!/usr/bin/env python3
"""
Merge PET First Batch Studies

This script processes uncompressed directories from PET_first_batch and merges them into 
the existing reorganized directory structure based on patient ID from DICOM metadata.

Structure: uncompressed directories -> read studies/series/instances -> read DICOM metadata -> merge into organized structure
"""

import os
import tempfile
import shutil
from pathlib import Path
import pydicom
from pydicom.errors import InvalidDicomError
import json
from collections import defaultdict
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('merge_pet_batch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def find_dicom_files(directory):
    """Recursively find all DICOM files in a directory"""
    dicom_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.dcm'):
                file_path = os.path.join(root, file)
                # Verify it's actually a DICOM file
                try:
                    pydicom.dcmread(file_path, stop_before_pixels=True)
                    dicom_files.append(file_path)
                except (InvalidDicomError, Exception):
                    continue
    return dicom_files

def extract_dicom_metadata(dicom_file):
    """Extract key metadata from a DICOM file"""
    try:
        ds = pydicom.dcmread(dicom_file, stop_before_pixels=True)
        
        metadata = {}
        
        # Required fields for reorganization
        if hasattr(ds, 'PatientID'):
            metadata['PatientID'] = str(ds.PatientID).strip()
        else:
            metadata['PatientID'] = 'UNKNOWN_PATIENT'
        
        if hasattr(ds, 'StudyInstanceUID'):
            metadata['StudyInstanceUID'] = str(ds.StudyInstanceUID).strip()
        else:
            metadata['StudyInstanceUID'] = 'UNKNOWN_STUDY'
        
        if hasattr(ds, 'SeriesInstanceUID'):
            metadata['SeriesInstanceUID'] = str(ds.SeriesInstanceUID).strip()
        else:
            metadata['SeriesInstanceUID'] = 'UNKNOWN_SERIES'
        
        # Additional useful metadata
        if hasattr(ds, 'PatientName'):
            metadata['PatientName'] = str(ds.PatientName)
        
        if hasattr(ds, 'SeriesDescription'):
            metadata['SeriesDescription'] = str(ds.SeriesDescription)
        
        if hasattr(ds, 'StudyDescription'):
            metadata['StudyDescription'] = str(ds.StudyDescription)
        
        if hasattr(ds, 'StudyDate'):
            metadata['StudyDate'] = str(ds.StudyDate)
        
        if hasattr(ds, 'Modality'):
            metadata['Modality'] = str(ds.Modality)
        
        if hasattr(ds, 'SeriesNumber'):
            metadata['SeriesNumber'] = str(ds.SeriesNumber)
            
        if hasattr(ds, 'InstanceNumber'):
            metadata['InstanceNumber'] = str(ds.InstanceNumber)
        
        return metadata
    except Exception as e:
        logger.error(f"Error reading DICOM metadata from {dicom_file}: {e}")
        return None

def sanitize_filename(filename):
    """Sanitize filename for filesystem compatibility"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

def create_composite_study_id(metadata):
    """Create a composite study identifier using StudyDate + StudyDescription"""
    study_date = metadata.get('StudyDate', 'UNKNOWN_DATE')
    study_desc = metadata.get('StudyDescription', 'UNKNOWN_STUDY')
    
    # Create a more readable composite identifier
    composite_id = f"{study_date}_{sanitize_filename(study_desc)}"
    
    # Truncate if too long to avoid filesystem issues
    if len(composite_id) > 200:
        composite_id = composite_id[:200]
    
    return composite_id

def group_existing_series_by_composite_study(output_dir):
    """Group existing series that have the same composite study ID"""
    reorganization_actions = []
    
    # Find all existing series directories
    for patient_dir in os.listdir(output_dir):
        patient_path = os.path.join(output_dir, patient_dir)
        if not os.path.isdir(patient_path) or patient_dir.endswith('.json'):
            continue
            
        logger.info(f"Processing patient: {patient_dir}")
        
        # Map to track composite study IDs and their series
        composite_studies = defaultdict(list)
        
        # Scan existing studies
        for study_dir in os.listdir(patient_path):
            study_path = os.path.join(patient_path, study_dir)
            if not os.path.isdir(study_path):
                continue
                
            # Find series in this study
            for series_dir in os.listdir(study_path):
                series_path = os.path.join(study_path, series_dir)
                if not os.path.isdir(series_path):
                    continue
                    
                # Check if series has metadata
                metadata_file = os.path.join(series_path, 'series_metadata.json')
                if os.path.exists(metadata_file):
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    composite_study_id = create_composite_study_id(metadata)
                    composite_studies[composite_study_id].append({
                        'original_study_path': study_path,
                        'series_path': series_path,
                        'series_id': series_dir,
                        'metadata': metadata
                    })
        
        # Find studies that need to be merged
        for composite_study_id, series_list in composite_studies.items():
            if len(series_list) > 1:
                logger.info(f"Found {len(series_list)} series for composite study: {composite_study_id}")
                for series_info in series_list:
                    logger.info(f"  - Series: {series_info['metadata'].get('SeriesDescription', 'Unknown')} ({series_info['metadata'].get('Modality', 'Unknown')})")
                
                reorganization_actions.append({
                    'patient_id': patient_dir,
                    'composite_study_id': composite_study_id,
                    'series_list': series_list
                })
    
    return reorganization_actions

def create_target_directory(output_dir, patient_id, study_id, series_id):
    """Create the target directory structure using study identifier"""
    # Sanitize directory names
    patient_id = sanitize_filename(patient_id)
    study_id = sanitize_filename(study_id)
    series_id = sanitize_filename(series_id)
    
    target_dir = os.path.join(output_dir, patient_id, study_id, series_id)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def copy_dicom_file(source_path, target_dir, metadata):
    """Copy a DICOM file to the target directory with appropriate naming"""
    try:
        filename = os.path.basename(source_path)
        
        # Try to create a more meaningful filename
        if 'InstanceNumber' in metadata:
            instance_num = metadata['InstanceNumber'].zfill(4)
            base_name = f"{instance_num}.dcm"
        else:
            # Keep original filename but ensure .dcm extension
            base_name = filename
            if not base_name.lower().endswith('.dcm'):
                base_name += '.dcm'
        
        target_path = os.path.join(target_dir, base_name)
        
        # Handle filename conflicts
        counter = 1
        original_target = target_path
        while os.path.exists(target_path):
            name, ext = os.path.splitext(original_target)
            target_path = f"{name}_{counter:04d}{ext}"
            counter += 1
        
        shutil.copy2(source_path, target_path)
        return target_path
    except Exception as e:
        logger.error(f"Error copying {source_path}: {e}")
        return None

def check_existing_series(output_dir, patient_id, study_id, series_id):
    """Check if a specific series already exists for a patient using study ID and series ID"""
    patient_dir = os.path.join(output_dir, sanitize_filename(patient_id))
    study_dir = os.path.join(patient_dir, sanitize_filename(study_id))
    series_dir = os.path.join(study_dir, sanitize_filename(series_id))
    return os.path.exists(series_dir)

def process_uncompressed_directory(input_dir, output_dir, patient_folder_name):
    """Process an uncompressed directory from PET_first_batch"""
    logger.info(f"\n=== Processing uncompressed directory {patient_folder_name} ===")
    
    patient_folder_path = os.path.join(input_dir, patient_folder_name)
    
    if not os.path.isdir(patient_folder_path):
        logger.warning(f"Not a directory: {patient_folder_path}")
        return []
    
    results = []
    
    # Look for the nested structure: patient_folder/subfolder/studies/
    for subfolder in os.listdir(patient_folder_path):
        subfolder_path = os.path.join(patient_folder_path, subfolder)
        if not os.path.isdir(subfolder_path):
            continue
        
        studies_dir = os.path.join(subfolder_path, 'studies')
        if not os.path.exists(studies_dir):
            logger.warning(f"No studies directory found in {subfolder_path}")
            continue
        
        logger.info(f"Found studies directory: {studies_dir}")
        
        # Each subdirectory in studies is a study
        for study_name in os.listdir(studies_dir):
            study_path = os.path.join(studies_dir, study_name)
            if not os.path.isdir(study_path):
                continue
            
            logger.info(f"Processing study: {study_name}")
            
            # Look for series directory
            series_dir = os.path.join(study_path, 'series')
            if not os.path.exists(series_dir):
                logger.warning(f"No series directory in study {study_name}")
                continue
            
            # Process each series
            for series_name in os.listdir(series_dir):
                series_path = os.path.join(series_dir, series_name)
                if not os.path.isdir(series_path):
                    continue
                
                logger.info(f"Processing series: {series_name}")
                
                # Look for instances directory
                instances_dir = os.path.join(series_path, 'instances')
                if not os.path.exists(instances_dir):
                    logger.warning(f"No instances directory in series {series_name}")
                    continue
                
                # Find DICOM files in instances directory
                dicom_files = find_dicom_files(instances_dir)
                
                if not dicom_files:
                    logger.warning(f"No DICOM files found in series {series_name}")
                    continue
                
                logger.info(f"Found {len(dicom_files)} DICOM files in series {series_name}")
                
                # Get metadata from first DICOM file
                first_metadata = extract_dicom_metadata(dicom_files[0])
                if not first_metadata:
                    logger.error(f"Could not extract metadata from series {series_name}")
                    continue
                
                patient_id = first_metadata['PatientID']
                study_id = first_metadata['StudyInstanceUID']
                series_id = first_metadata['SeriesInstanceUID']
                
                logger.info(f"Patient: {patient_id}, Study: {study_id[:50]}..., Series: {series_id[:50]}...")
                
                # Check if this series already exists
                if check_existing_series(output_dir, patient_id, study_id, series_id):
                    logger.info(f"Series already exists for patient {patient_id}, study {study_id[:50]}..., series {series_id[:50]}... - skipping")
                    continue
                
                # Create target directory
                target_dir = create_target_directory(output_dir, patient_id, study_id, series_id)
                
                # Copy all DICOM files
                copied_files = []
                for dicom_file in dicom_files:
                    file_metadata = extract_dicom_metadata(dicom_file)
                    if file_metadata:
                        target_path = copy_dicom_file(dicom_file, target_dir, file_metadata)
                        if target_path:
                            copied_files.append(target_path)
                
                # Save series metadata
                metadata_file = os.path.join(target_dir, 'series_metadata.json')
                with open(metadata_file, 'w') as f:
                    json.dump(first_metadata, f, indent=2)
                
                result = {
                    'patient_id': patient_id,
                    'study_id': study_id,
                    'series_id': series_id,
                    'series_description': first_metadata.get('SeriesDescription', 'N/A'),
                    'study_description': first_metadata.get('StudyDescription', 'N/A'),
                    'study_date': first_metadata.get('StudyDate', 'N/A'),
                    'modality': first_metadata.get('Modality', 'N/A'),
                    'num_files': len(copied_files),
                    'target_directory': target_dir,
                    'source_directory': patient_folder_name
                }
                
                results.append(result)
                logger.info(f"Successfully processed series: {len(copied_files)} files -> {target_dir}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Merge PET first batch studies into reorganized structure')
    parser.add_argument('--input-dir', 
                        default='/home/sina/Data/Gradient/PET_first_batch',
                        help='Input directory with uncompressed patient folders')
    parser.add_argument('--output-dir', 
                        default='/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/reorganized',
                        help='Output directory (existing reorganized structure)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually copying files')
    parser.add_argument('--max-folders', type=int,
                        help='Maximum number of patient folders to process (for testing)')
    parser.add_argument('--patient-filter', 
                        help='Filter to process only a specific patient ID')
    parser.add_argument('--reorganize-existing', action='store_true',
                        help='Reorganize existing data to group series by composite study ID')
    
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_dir = args.output_dir
    
    # Handle reorganization of existing data
    if args.reorganize_existing:
        logger.info("Reorganizing existing data using composite study IDs")
        
        if not os.path.exists(output_dir):
            logger.error(f"Output directory does not exist: {output_dir}")
            return
        
        actions = group_existing_series_by_composite_study(output_dir)
        
        logger.info(f"Found {len(actions)} reorganization actions needed")
        
        if args.dry_run:
            logger.info("DRY RUN MODE - showing what would be reorganized")
            for action in actions:
                logger.info(f"Patient: {action['patient_id']}, Composite Study: {action['composite_study_id']}")
                logger.info(f"  Would group {len(action['series_list'])} series")
        else:
            logger.info("Reorganization mode not yet implemented - use --dry-run to see what would be done")
        
        return

    if not os.path.exists(input_dir):
        logger.error(f"Input directory does not exist: {input_dir}")
        return
    
    if not os.path.exists(output_dir):
        logger.error(f"Output directory does not exist: {output_dir}")
        logger.error("Please run the main reorganizer first to create the base structure")
        return
    
    logger.info(f"Starting PET batch merge from uncompressed directories")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Find all patient folders (excluding .tar.gz files)
    patient_folders = [f for f in os.listdir(input_dir) 
                      if os.path.isdir(os.path.join(input_dir, f)) and not f.endswith('.tar.gz')]
    
    # Apply patient filter if specified
    if args.patient_filter:
        patient_folders = [f for f in patient_folders if args.patient_filter in f]
        logger.info(f"Filtered to patient: {args.patient_filter}")
    
    if args.max_folders:
        patient_folders = patient_folders[:args.max_folders]
    
    logger.info(f"Found {len(patient_folders)} patient folders to process")
    
    if args.dry_run:
        logger.info("DRY RUN MODE - no files will be copied")
        for patient_folder in patient_folders[:5]:  # Show first 5 in dry run
            logger.info(f"Would process: {patient_folder}")
        return
    
    # Process each patient folder
    all_results = []
    summary_stats = defaultdict(lambda: {
        'studies': set(),
        'series': 0,
        'files': 0,
        'modalities': set()
    })
    
    for i, patient_folder in enumerate(sorted(patient_folders), 1):
        logger.info(f"\n[{i}/{len(patient_folders)}] Processing {patient_folder}")
        
        try:
            results = process_uncompressed_directory(input_dir, output_dir, patient_folder)
            all_results.extend(results)
            
            # Update summary statistics
            for result in results:
                patient_id = result['patient_id']
                modality = result['modality']
                summary_stats[patient_id]['studies'].add(result['study_id'])
                summary_stats[patient_id]['series'] += 1
                summary_stats[patient_id]['files'] += result['num_files']
                summary_stats[patient_id]['modalities'].add(modality)
                
        except Exception as e:
            logger.error(f"Error processing {patient_folder}: {e}")
            continue
    
    # Convert sets to counts for JSON serialization
    for patient_id in summary_stats:
        summary_stats[patient_id]['studies'] = len(summary_stats[patient_id]['studies'])
        summary_stats[patient_id]['modalities'] = list(summary_stats[patient_id]['modalities'])
    
    # Save results
    results_file = os.path.join(output_dir, 'pet_batch_merge_results.json')
    with open(results_file, 'w') as f:
        json.dump({
            'summary_stats': dict(summary_stats),
            'detailed_results': all_results,
            'total_series_processed': len(all_results),
            'total_patients_updated': len(summary_stats),
            'total_folders_processed': len(patient_folders)
        }, f, indent=2)
    
    logger.info(f"Results saved to: {results_file}")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("MERGE SUMMARY")
    logger.info("="*80)
    logger.info(f"Total patient folders processed: {len(patient_folders)}")
    logger.info(f"Total new series added: {len(all_results)}")
    logger.info(f"Total patients updated: {len(summary_stats)}")
    
    logger.info("\nPer-patient summary:")
    for patient_id, stats in summary_stats.items():
        logger.info(f"  Patient {patient_id}:")
        logger.info(f"    New studies: {stats['studies']}")
        logger.info(f"    New series: {stats['series']}")
        logger.info(f"    New files: {stats['files']}")
        logger.info(f"    Modalities: {', '.join(stats['modalities'])}")

if __name__ == "__main__":
    main() 