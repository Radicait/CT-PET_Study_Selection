#!/usr/bin/env python3
"""
DICOM Study Reorganizer

This script reorganizes DICOM studies from the original structure into:
<output_dir>/<patient_id>/<study_id>/<series_id>/<dicom_files.dcm>

Original structure: /studies/<study_id>/series/<series_id>.tar
New structure: <output_dir>/<patient_id>/<study_id>/<series_id>/<dicom_files.dcm>
"""

import os
import tarfile
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
        logging.FileHandler('dicom_reorganizer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def extract_tar_file(tar_path, extract_to):
    """Extract a tar file to a temporary directory"""
    try:
        with tarfile.open(tar_path, 'r') as tar:
            tar.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Error extracting {tar_path}: {e}")
        return False

def find_dicom_files(directory):
    """Recursively find all DICOM files in a directory"""
    dicom_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            # Check if it's a DICOM file by trying to read it
            try:
                pydicom.dcmread(file_path, stop_before_pixels=True)
                dicom_files.append(file_path)
            except (InvalidDicomError, Exception):
                # Skip non-DICOM files
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
    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

def create_directory_structure(output_dir, patient_id, study_id, series_id):
    """Create the output directory structure"""
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
        # Create filename with instance number if available
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

def process_series_tar(tar_path, output_dir, study_id_from_path):
    """Process a single series tar file"""
    series_id_from_tar = os.path.basename(tar_path).replace('.tar', '')
    logger.info(f"Processing series: {series_id_from_tar}")
    
    # Create temporary directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract tar file
        if not extract_tar_file(tar_path, temp_dir):
            return None
        
        # Find all DICOM files
        dicom_files = find_dicom_files(temp_dir)
        
        if not dicom_files:
            logger.warning(f"No DICOM files found in {tar_path}")
            return None
        
        logger.info(f"Found {len(dicom_files)} DICOM files in series {series_id_from_tar}")
        
        # Analyze first DICOM file for metadata
        first_metadata = extract_dicom_metadata(dicom_files[0])
        if not first_metadata:
            logger.error(f"Could not extract metadata from first file in {tar_path}")
            return None
        
        patient_id = first_metadata['PatientID']
        study_id = first_metadata['StudyInstanceUID']
        series_id = first_metadata['SeriesInstanceUID']
        
        # Create target directory
        target_dir = create_directory_structure(output_dir, patient_id, study_id, series_id)
        
        # Copy all DICOM files
        copied_files = []
        for dicom_file in dicom_files:
            # Get metadata for this specific file
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
            'modality': first_metadata.get('Modality', 'N/A'),
            'num_files': len(copied_files),
            'target_directory': target_dir,
            'original_tar': tar_path
        }
        
        logger.info(f"Successfully processed series {series_id_from_tar}: {len(copied_files)} files -> {target_dir}")
        return result

def process_study(study_dir, output_dir):
    """Process a single study directory"""
    study_id_from_path = os.path.basename(study_dir)
    logger.info(f"Processing study: {study_id_from_path}")
    
    series_dir = os.path.join(study_dir, 'series')
    if not os.path.exists(series_dir):
        logger.warning(f"No series directory found in {study_dir}")
        return []
    
    # Find all tar files in series directory
    tar_files = [f for f in os.listdir(series_dir) if f.endswith('.tar')]
    
    if not tar_files:
        logger.warning(f"No tar files found in {series_dir}")
        return []
    
    logger.info(f"Found {len(tar_files)} series in study {study_id_from_path}")
    
    # Process each series
    study_results = []
    for tar_file in sorted(tar_files):
        tar_path = os.path.join(series_dir, tar_file)
        result = process_series_tar(tar_path, output_dir, study_id_from_path)
        if result:
            study_results.append(result)
    
    return study_results

def main():
    parser = argparse.ArgumentParser(description='Reorganize DICOM studies by patient ID')
    parser.add_argument('--input-dir', 
                        default='/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/dicomweb/studies',
                        help='Input studies directory')
    parser.add_argument('--output-dir', 
                        default='/home/sina/Data/Gradient/PET_CT_30JUN2025-R1/reorganized',
                        help='Output directory for reorganized studies')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually copying files')
    parser.add_argument('--max-studies', type=int,
                        help='Maximum number of studies to process (for testing)')
    
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_dir = args.output_dir
    
    if not os.path.exists(input_dir):
        logger.error(f"Input directory does not exist: {input_dir}")
        return
    
    if not args.dry_run:
        os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting DICOM reorganization")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Find all study directories
    study_dirs = [d for d in os.listdir(input_dir) 
                  if os.path.isdir(os.path.join(input_dir, d))]
    
    if args.max_studies:
        study_dirs = study_dirs[:args.max_studies]
    
    logger.info(f"Found {len(study_dirs)} studies to process")
    
    # Process each study
    all_results = []
    summary_stats = defaultdict(lambda: {
        'studies': set(),
        'series': 0,
        'files': 0,
        'modalities': set()
    })
    
    for i, study_dir_name in enumerate(sorted(study_dirs), 1):
        study_path = os.path.join(input_dir, study_dir_name)
        logger.info(f"\n[{i}/{len(study_dirs)}] Processing study: {study_dir_name}")
        
        if args.dry_run:
            logger.info(f"DRY RUN: Would process {study_path}")
            continue
        
        try:
            study_results = process_study(study_path, output_dir)
            all_results.extend(study_results)
            
            # Update summary statistics
            for result in study_results:
                patient_id = result['patient_id']
                modality = result['modality']
                summary_stats[patient_id]['studies'].add(result['study_id'])
                summary_stats[patient_id]['series'] += 1
                summary_stats[patient_id]['files'] += result['num_files']
                summary_stats[patient_id]['modalities'].add(modality)
                
        except Exception as e:
            logger.error(f"Error processing study {study_dir_name}: {e}")
            continue
    
    # Convert sets to counts for JSON serialization
    for patient_id in summary_stats:
        summary_stats[patient_id]['studies'] = len(summary_stats[patient_id]['studies'])
        summary_stats[patient_id]['modalities'] = list(summary_stats[patient_id]['modalities'])
    
    # Save complete results
    if not args.dry_run:
        results_file = os.path.join(output_dir, 'reorganization_results.json')
        with open(results_file, 'w') as f:
            json.dump({
                'summary_stats': dict(summary_stats),
                'detailed_results': all_results,
                'total_series_processed': len(all_results),
                'total_patients': len(summary_stats)
            }, f, indent=2)
        
        logger.info(f"Results saved to: {results_file}")
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("REORGANIZATION SUMMARY")
    logger.info("="*80)
    logger.info(f"Total studies processed: {len(study_dirs)}")
    logger.info(f"Total series processed: {len(all_results)}")
    logger.info(f"Total patients found: {len(summary_stats)}")
    
    logger.info("\nPer-patient summary:")
    for patient_id, stats in summary_stats.items():
        logger.info(f"  Patient {patient_id}:")
        logger.info(f"    Studies: {stats['studies']}")
        logger.info(f"    Series: {stats['series']}")
        logger.info(f"    Files: {stats['files']}")
        logger.info(f"    Modalities: {', '.join(stats['modalities'])}")

if __name__ == "__main__":
    main() 