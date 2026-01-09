"""
This script is used to load the studies_list.json file into the Firestore database.

Firestore Data Structure:
------------------------
Collection: 'studies'
Document ID: study_id (e.g., 'GRDNPOCP25GQPBFB')
Document Fields:
    {
        "study_id": str,  # Unique identifier for the study
        "CT": {
            "file_path": str,     # Path to CT scan files
            "slice_count": int,   # Number of CT slices
            "description": str    # Description of the CT scan
        },
        "PET": {
            "file_path": str,     # Path to PET scan files
            "slice_count": int,   # Number of PET slices
            "priority_selection": int,  # Priority level for selection
            "description": str    # Description of the PET scan
        }
    }

Example JSON structure:
    {
        "study_id": "GRDNPOCP25GQPBFB",
        "CT": {
            "file_path": "/path/to/ct/files",
            "slice_count": 320,
            "description": "CT pet  4.0  Br38"
        },
        "PET": {
            "file_path": "/path/to/pet/files",
            "slice_count": 320,
            "priority_selection": 2,
            "description": "PET AC"
        }
    }
"""

import json
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from typing import List, Dict, Any
import sys
from pathlib import Path

# Configuration
CREDENTIALS_PATH = "/home/sina/gradient-data/gcs_upload_key.json"
JSON_DATA_PATH = "study_folders.json"
COLLECTION_NAME = "studies"
SKIP_EXISTING_RECORDS = True  # When True, will not replace existing records

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FirestoreLoader:
    def __init__(self, credentials_path: str):
        self.credentials_path = Path(credentials_path)
        self.db = None
        
    def initialize_firestore(self) -> bool:
        """Initialize Firestore with credentials and verify permissions."""
        try:
            if not self.credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found at {self.credentials_path}")
            
            cred = credentials.Certificate(str(self.credentials_path))
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            
            # Verify permissions by attempting to write and read a test document
            test_ref = self.db.collection('permission_test').document('test')
            test_ref.set({'test': 'data'})
            test_ref.get()
            test_ref.delete()
            
            logger.info("Successfully connected to Firestore with proper permissions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {str(e)}")
            return False

    def load_json_data(self, json_path: str) -> List[Dict[Any, Any]]:
        """Load and validate JSON data from file."""
        try:
            with open(json_path, 'r') as file:
                data = json.load(file)
            
            if not isinstance(data, list):
                raise ValueError("JSON data must be an array")
            
            # Basic validation of required fields
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError("Each item must be a dictionary")
                if "study_id" not in item:
                    raise ValueError("Each item must have a study_id")
                
            logger.info(f"Successfully loaded {len(data)} records from JSON file")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load JSON data: {str(e)}")
            raise

    def upload_to_firestore(self, data: List[Dict[Any, Any]], skip_existing: bool = True, batch_size: int = 500) -> bool:
        """Upload data to Firestore in batches."""
        try:
            total_records = len(data)
            batch_count = 0
            records_added = 0
            records_skipped = 0
            
            for i in range(0, total_records, batch_size):
                batch = self.db.batch()
                current_batch = data[i:i + batch_size]
                
                for record in current_batch:
                    study_id = record['study_id']
                    doc_ref = self.db.collection(COLLECTION_NAME).document(study_id)
                    
                    # Check if document already exists when skip_existing is True
                    if skip_existing:
                        doc = doc_ref.get()
                        if doc.exists:
                            logger.info(f"Skipping existing record with study_id: {study_id}")
                            records_skipped += 1
                            continue
                    
                    # Add or replace record
                    batch.set(doc_ref, record)
                    records_added += 1
                
                batch.commit()
                batch_count += 1
                logger.info(f"Committed batch {batch_count}, records {i+1} to {min(i+batch_size, total_records)}")
            
            if skip_existing:
                logger.info(f"Upload summary: {records_added} records added, {records_skipped} records skipped (already exist)")
            else:
                logger.info(f"Upload summary: {records_added} records added/updated")
            
            logger.info(f"Successfully processed all {total_records} records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload data to Firestore: {str(e)}")
            return False

def main():
    try:
        # Initialize loader
        loader = FirestoreLoader(CREDENTIALS_PATH)
        
        # Initialize Firestore and check permissions
        if not loader.initialize_firestore():
            logger.error("Failed to initialize Firestore. Exiting.")
            sys.exit(1)
        
        # Load JSON data
        data = loader.load_json_data(JSON_DATA_PATH)
        
        # Upload to Firestore
        if loader.upload_to_firestore(data, skip_existing=SKIP_EXISTING_RECORDS):
            logger.info("Data upload completed successfully")
        else:
            logger.error("Data upload failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()