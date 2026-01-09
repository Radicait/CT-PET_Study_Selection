#!/usr/bin/env python3
"""
This script zips and uploads a dicom-based study data to Google Cloud Storage.
"""
import os
import subprocess
from google.cloud import storage
import concurrent.futures
from tqdm import tqdm  # Added for progress bar
import time

def verify_gcs_permissions(bucket):
    try:
        # List blobs with a limit to verify read access
        list(bucket.list_blobs(max_results=1))
        
        # Try to create a small test file with timestamp to avoid conflicts
        test_blob = bucket.blob(f'permission_test_{int(time.time())}')
        test_blob.upload_from_string('test')
        return True
    except Exception as e:
        print(f"[ERROR] Failed to verify access to GCS bucket: {str(e)}")
        return False

# Initialize the GCS client
client = storage.Client.from_service_account_json('gcs_upload_key.json')

# Define the GCS bucket name
bucket_name = 'radicait-pet-ct-data'
folder_name = 'NSCLC Radiogenomics'
bucket = client.bucket(bucket_name)

# Remove the problematic line and directly check permissions
if not verify_gcs_permissions(bucket):
    print("Please ensure the service account has the following roles:")
    print("- roles/storage.objectViewer")
    print("- roles/storage.objectCreator")
    exit(1)

# Get the list of main folders in the directory
root_data_dir = '/home/sina/Data/NSCLC_Radiogenomics_Dataset/NSCLC_Radiogenomics/NSCLC Radiogenomics'
main_folders = [f.path for f in os.scandir(root_data_dir) if f.is_dir()]


def process_folder(folder):
    # Compress the folder
    compressed_file = f"{folder}.tar.gz"
    subprocess.run(
        ['tar', '-czf', compressed_file, '-C', os.path.dirname(folder), os.path.basename(folder)],
        check=True
    )
    
    # Upload to GCS bucket inside the specified folder
    blob = bucket.blob(f"{folder_name}/{os.path.basename(compressed_file)}")
    blob.upload_from_filename(compressed_file)
    
    # Remove the compressed file
    os.remove(compressed_file)
    return folder  # Return folder info for progress tracking

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    # Iterate over the folders with a progress bar
    for _ in tqdm(executor.map(process_folder, main_folders), total=len(main_folders), desc="Processing folders"):
        pass
