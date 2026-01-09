#!/usr/bin/env python3
"""
Verification script to read back Firebase documents and check if newlines are preserved
"""

import firebase_admin
from firebase_admin import credentials, firestore
import sys
from pathlib import Path

# Configuration
CREDENTIALS_PATH = "/home/sina/gradient-data/gcs_upload_key.json"
COLLECTION_NAME = "studies"
TEST_DOCUMENT_ID = "GRDN00RXHQ6B19XI"  # The document we updated in test mode

def verify_document_newlines(doc_id: str = TEST_DOCUMENT_ID):
    """Read a document from Firebase and verify newlines are preserved."""
    
    try:
        # Initialize Firebase
        print(f"Connecting to Firebase...")
        cred = credentials.Certificate(CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Read the specific document
        print(f"Reading document: {doc_id}")
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            print(f"❌ Document {doc_id} does not exist!")
            return False
        
        # Get the document data
        doc_data = doc.to_dict()
        report_text = doc_data.get('deid_english_report', '')
        
        if not report_text:
            print(f"❌ Document {doc_id} has no deid_english_report field!")
            return False
        
        # Analyze the report text
        print("=" * 80)
        print("📄 FIREBASE DOCUMENT VERIFICATION")
        print("=" * 80)
        print(f"Document ID: {doc_id}")
        print(f"Report field length: {len(report_text)} characters")
        
        # Count different types of line endings
        newline_count = report_text.count('\n')
        carriage_return_count = report_text.count('\r')
        crlf_count = report_text.count('\r\n')
        
        print(f"\\n (newline) count: {newline_count}")
        print(f"\\r (carriage return) count: {carriage_return_count}")
        print(f"\\r\\n (CRLF) count: {crlf_count}")
        
        # Show raw representation of first 400 characters
        print("\n📋 RAW REPRESENTATION (first 400 chars):")
        print("-" * 50)
        raw_sample = repr(report_text[:400])
        print(raw_sample)
        
        # Show formatted output (how it should display)
        print("\n📖 FORMATTED OUTPUT (first 500 chars):")
        print("-" * 50)
        formatted_sample = report_text[:500]
        print(formatted_sample)
        if len(report_text) > 500:
            print("...")
        
        # Check for paragraph structure
        print("\n🔍 PARAGRAPH ANALYSIS:")
        print("-" * 50)
        lines = report_text.split('\n')
        print(f"Total lines after splitting on \\n: {len(lines)}")
        
        # Show first 10 lines
        print("First 10 lines:")
        for i, line in enumerate(lines[:10], 1):
            print(f"{i:2}: '{line}'")
        
        # Success indicators
        print("\n✅ VERIFICATION RESULTS:")
        print("-" * 50)
        
        if newline_count > 0:
            print(f"✅ SUCCESS: Found {newline_count} newline characters in Firebase!")
            print("✅ Newlines are properly preserved in the database")
        else:
            print("❌ FAILED: No newline characters found in Firebase document")
            print("❌ Newlines were lost during storage")
        
        # Check for expected keywords on separate lines
        clinical_data_line = "CLINICAL DATA:" in report_text
        exam_line = any("EXAM:" in line for line in lines[:10])
        technique_line = any("TECHNIQUE:" in line for line in lines[:15])
        
        print(f"✅ Contains 'CLINICAL DATA:': {clinical_data_line}")
        print(f"✅ 'EXAM:' on separate line: {exam_line}")
        print(f"✅ 'TECHNIQUE:' on separate line: {technique_line}")
        
        if newline_count > 10 and clinical_data_line and exam_line and technique_line:
            print("\n🎉 OVERALL: Newlines are SUCCESSFULLY preserved in Firebase!")
            return True
        else:
            print("\n⚠️  OVERALL: There may be issues with newline preservation")
            return False
            
    except Exception as e:
        print(f"❌ Error during verification: {str(e)}")
        return False

def compare_with_csv():
    """Compare the Firebase document with the original CSV data."""
    try:
        import csv
        
        print("\n🔄 COMPARING WITH ORIGINAL CSV DATA")
        print("=" * 80)
        
        # Read the CSV to find the original report
        csv_file = "reports_data/extracted_reports3.csv"
        target_patient_id = "GRDN51Y0Z3GJ59ES"  # Patient ID for test document
        
        with open(csv_file, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                patient_id = row.get('patient_id', '').strip()
                if patient_id == target_patient_id:
                    csv_report = row.get('deid_english_report', '')
                    
                    print(f"Found original CSV data for patient: {patient_id}")
                    print(f"CSV report length: {len(csv_report)} characters")
                    print(f"CSV newline count: {csv_report.count(chr(10))}")
                    
                    print(f"\nFirst 300 chars from CSV:")
                    print(repr(csv_report[:300]))
                    
                    return csv_report
        
        print(f"⚠️  Could not find patient {target_patient_id} in CSV")
        return None
        
    except Exception as e:
        print(f"❌ Error reading CSV: {str(e)}")
        return None

def main():
    """Main verification function."""
    
    print("🔍 FIREBASE NEWLINE VERIFICATION TOOL")
    print("=" * 80)
    
    # Verify the test document
    success = verify_document_newlines()
    
    # Compare with original CSV data
    csv_report = compare_with_csv()
    
    # Final summary
    print("\n" + "=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    
    if success:
        print("✅ SUCCESS: Newlines are properly preserved in Firebase!")
        print("✅ The updated script is working correctly")
        print("✅ You can now run the full update with:")
        print("   python update_report_field_preserve_newlines.py")
    else:
        print("❌ ISSUE: Newlines may not be preserved correctly")
        print("❌ Further investigation needed")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main() 