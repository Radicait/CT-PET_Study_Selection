#!/usr/bin/env python3
"""
Script to merge radiology reports from CSV into Firestore study_pairs documents.

This script matches CSV rows with Firestore documents based on study UIDs:
- ct_study_uid (CSV) matches Diagnostic_CT.study_instance_uid (Firestore)
- pt_study_uid (CSV) matches PET.study_instance_uid (Firestore)

Usage:
    python merge_radiology_reports.py [--collection COLLECTION] [--dry-run] [--batch-size SIZE]
"""

import csv
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
from dataclasses import dataclass

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('merge_reports.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ReportRecord:
    """Represents a record from the CSV file."""
    pt_row_id: str
    pt_study_uid: str
    patient_id: str
    ct_study_uid: str
    combined_report: str
    # Add other fields as needed
    clinical_reason: str = ""
    primary_diagnosis: str = ""
    success: str = ""


class FirestoreReportMerger:
    """Handles merging radiology reports into Firestore documents."""
    
    def __init__(self, collection_name: str = "Gradient", gcp_key_path: str = "/home/sina/Diagnostic-CT-Pipeline/gcp_key.json"):
        self.collection_name = collection_name
        self.gcp_key_path = Path(gcp_key_path)
        self.db = None
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase connection."""
        try:
            # Check if already initialized
            try:
                firebase_admin.get_app()
                logger.info("Firebase already initialized")
            except ValueError:
                # Not initialized, proceed
                if self.gcp_key_path.exists():
                    cred = credentials.Certificate(str(self.gcp_key_path))
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase initialized with service account")
                else:
                    logger.error(f"GCP key not found at {self.gcp_key_path}")
                    raise FileNotFoundError(f"GCP key not found at {self.gcp_key_path}")
            
            self.db = firestore.client()
            logger.info(f"Connected to Firestore, using collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def load_csv_data(self, csv_path: str) -> List[ReportRecord]:
        """Load radiology reports from CSV file."""
        logger.info(f"Loading CSV data from {csv_path}")
        records = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Extract required fields
                        record = ReportRecord(
                            pt_row_id=row.get('pt_row_id', ''),
                            pt_study_uid=row.get('pt_study_uid', ''),
                            patient_id=row.get('patient_id', ''),
                            ct_study_uid=row.get('ct_study_uid', ''),
                            combined_report=row.get('combined_report', ''),
                            clinical_reason=row.get('clinical_reason', ''),
                            primary_diagnosis=row.get('primary_diagnosis', ''),
                            success=row.get('success', '')
                        )
                        
                        # Validate required fields
                        if not all([record.pt_study_uid, record.ct_study_uid, record.patient_id]):
                            logger.warning(f"Row {row_num}: Missing required fields (pt_study_uid, ct_study_uid, or patient_id)")
                            continue
                            
                        records.append(record)
                        
                    except Exception as e:
                        logger.warning(f"Row {row_num}: Error processing row: {e}")
                        continue
                
                logger.info(f"Loaded {len(records)} valid records from CSV")
                return records
                
        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise
    
    def find_matching_documents(self, records: List[ReportRecord]) -> Dict[str, tuple]:
        """
        Find Firestore documents that match CSV records based on study UIDs.
        
        Returns:
            Dictionary mapping document_id to (ReportRecord, document_data)
        """
        logger.info("Searching for matching Firestore documents...")
        
        # Create lookup dictionaries for efficient matching
        pt_uid_to_record = {record.pt_study_uid: record for record in records}
        ct_uid_to_record = {record.ct_study_uid: record for record in records}
        
        matches = {}
        collection_ref = self.db.collection(self.collection_name)
        
        # Query all documents in batches
        docs = collection_ref.stream()
        doc_count = 0
        match_count = 0
        
        for doc in docs:
            doc_count += 1
            if doc_count % 100 == 0:
                logger.info(f"Processed {doc_count} documents, found {match_count} matches")
            
            try:
                data = doc.to_dict()
                doc_id = doc.id
                
                # Extract study UIDs from Firestore document
                diagnostic_ct = data.get('Diagnostic_CT', {})
                pet = data.get('PET', {})
                
                ct_study_uid = diagnostic_ct.get('study_instance_uid')
                pt_study_uid = pet.get('study_instance_uid')
                
                # Look for matching record
                matching_record = None
                
                # Try to find a record that matches both UIDs
                for record in records:
                    if (record.ct_study_uid == ct_study_uid and 
                        record.pt_study_uid == pt_study_uid):
                        matching_record = record
                        break
                
                if matching_record:
                    matches[doc_id] = (matching_record, data)
                    match_count += 1
                    logger.debug(f"Match found: {doc_id} -> {matching_record.patient_id}")
                
            except Exception as e:
                logger.warning(f"Error processing document {doc.id}: {e}")
                continue
        
        logger.info(f"Found {match_count} matching documents out of {doc_count} total documents")
        return matches
    
    def update_documents_with_reports(self, matches: Dict[str, tuple], dry_run: bool = False, batch_size: int = 100):
        """
        Update Firestore documents with radiology reports.
        
        Args:
            matches: Dictionary mapping document_id to (ReportRecord, document_data)
            dry_run: If True, don't actually update documents
            batch_size: Number of documents to update in each batch
        """
        logger.info(f"Updating {len(matches)} documents with radiology reports (dry_run={dry_run})")
        
        if dry_run:
            logger.info("DRY RUN MODE - No actual updates will be made")
        
        collection_ref = self.db.collection(self.collection_name)
        
        # Process in batches
        doc_ids = list(matches.keys())
        total_updated = 0
        total_failed = 0
        
        for i in range(0, len(doc_ids), batch_size):
            batch_ids = doc_ids[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: documents {i+1}-{min(i+batch_size, len(doc_ids))}")
            
            if not dry_run:
                # Use a batch write for efficiency
                batch = self.db.batch()
                batch_updates = 0
            
            for doc_id in batch_ids:
                try:
                    record, current_data = matches[doc_id]
                    
                    # Prepare update data
                    update_data = {
                        "radiology_report": {
                            "combined_report": record.combined_report,
                            "clinical_reason": record.clinical_reason,
                            "primary_diagnosis": record.primary_diagnosis,
                            "pt_row_id": record.pt_row_id,
                            "updated_at": SERVER_TIMESTAMP,
                            "success_flag": record.success
                        },
                        "updated_at": SERVER_TIMESTAMP
                    }
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] Would update {doc_id} with report for patient {record.patient_id}")
                        total_updated += 1
                    else:
                        # Add to batch
                        doc_ref = collection_ref.document(doc_id)
                        batch.update(doc_ref, update_data)
                        batch_updates += 1
                        
                except Exception as e:
                    logger.error(f"Error preparing update for {doc_id}: {e}")
                    total_failed += 1
                    continue
            
            # Commit batch if not dry run
            if not dry_run and batch_updates > 0:
                try:
                    batch.commit()
                    total_updated += batch_updates
                    logger.info(f"Successfully updated {batch_updates} documents in batch")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to commit batch: {e}")
                    total_failed += batch_updates
        
        logger.info(f"Update complete: {total_updated} successful, {total_failed} failed")
    
    def verify_updates(self, matches: Dict[str, tuple], sample_size: int = 10):
        """
        Verify that updates were applied correctly by checking a sample of documents.
        """
        logger.info(f"Verifying updates on sample of {sample_size} documents...")
        
        collection_ref = self.db.collection(self.collection_name)
        doc_ids = list(matches.keys())[:sample_size]
        
        verified_count = 0
        for doc_id in doc_ids:
            try:
                doc_ref = collection_ref.document(doc_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    data = doc.to_dict()
                    if "radiology_report" in data and data["radiology_report"].get("combined_report"):
                        verified_count += 1
                        logger.debug(f"Verified update for {doc_id}")
                    else:
                        logger.warning(f"Update not found for {doc_id}")
                else:
                    logger.warning(f"Document {doc_id} not found")
                    
            except Exception as e:
                logger.error(f"Error verifying {doc_id}: {e}")
        
        logger.info(f"Verification complete: {verified_count}/{len(doc_ids)} documents verified")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Merge radiology reports into Firestore")
    parser.add_argument(
        "--csv-path", 
        default="/home/sina/gradient-data/Radiology_reports_extraction_pipeline/selected_PET_CT_studies.csv",
        help="Path to CSV file with radiology reports"
    )
    parser.add_argument(
        "--collection", 
        default="Gradient",
        help="Firestore collection name"
    )
    parser.add_argument(
        "--gcp-key", 
        default="/home/sina/Diagnostic-CT-Pipeline/gcp_key.json",
        help="Path to GCP service account key"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Run without making actual updates"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=100,
        help="Number of documents to update in each batch"
    )
    parser.add_argument(
        "--verify", 
        action="store_true",
        help="Verify updates after completion"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize merger
        merger = FirestoreReportMerger(
            collection_name=args.collection,
            gcp_key_path=args.gcp_key
        )
        
        # Load CSV data
        records = merger.load_csv_data(args.csv_path)
        
        if not records:
            logger.error("No valid records found in CSV file")
            return 1
        
        # Find matching documents
        matches = merger.find_matching_documents(records)
        
        if not matches:
            logger.error("No matching documents found in Firestore")
            return 1
        
        logger.info(f"Found {len(matches)} matches out of {len(records)} CSV records")
        
        # Update documents
        merger.update_documents_with_reports(
            matches, 
            dry_run=args.dry_run, 
            batch_size=args.batch_size
        )
        
        # Verify if requested
        if args.verify and not args.dry_run:
            merger.verify_updates(matches)
        
        logger.info("Merge operation completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Merge operation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 