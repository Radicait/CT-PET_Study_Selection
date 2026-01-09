# DATA EXTRACTION PIPELINE SCRIPT

# ------------------------------------------------------------------------------------------------
#  EXTRACT DATA FROM REPORTS
# ------------------------------------------------------------------------------------------------


# ------------------------------------------------------------------------------------------------
#  MAIN SCRIPT
# ------------------------------------------------------------------------------------------------

"""
Production-quality script for parallel extraction of structured data from radiology reports.

This script:
  - Reads 'gradient_pt_ct_all_pairs_query.csv' as the source DataFrame.
  - Processes only rows missing the 'clinical_reason' value (i.e. needing extraction).
  - For each such row:
      * Submits the report text to an extraction function (with up-to-MAX_RETRIES).
      * Writes a detailed report text file in the OUTPUT_DIR using the pt_row_id as the filename.
      * Updates the row with the extracted values and appends it to the output CSV.
  - Also, rows that already have a non-empty 'clinical_reason' are appended to the CSV.
  - Extraction tasks run concurrently using threads. To safely write to the CSV file,
    a global lock is used to ensure that only one thread writes at a time.
  - Resume logic is implemented: On re-run, rows that are already present (identified by their
    unique 'pt_row_id') in the CSV are skipped.
"""

import os
import csv
import json
import logging
import threading
import concurrent.futures
from time import sleep
from typing import Dict, Any

import pandas as pd

# Import your extraction helper (assumes it returns a JSON string)
from openai_helper import extract_data

# =============================================================================
#  CONFIGURATION CONSTANTS
# =============================================================================

INPUT_CSV = '/home/sina/gradient-data/reports_data/gradient_pt_ct_all_pairs_query.csv'
OUTPUT_DIR = '/home/sina/gradient-data/reports_data/LLM_extracted_data'

OUTPUT_CSV = f"extracted_report_CT_PET.csv"
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
MAX_WORKERS = 20  # Number of parallel threads

# Configure logging (both file and stream)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extraction.log'),
        logging.StreamHandler()
    ]
)

# A global lock for CSV writes and updating shared resources
csv_lock = threading.Lock()

# =============================================================================
#  HELPER FUNCTIONS
# =============================================================================

def sanitize_filename(raw_name: str) -> str:
    """
    Sanitize a string to be used as a safe filename.
    Currently removes extraneous quotes and whitespace.
    """
    return raw_name.strip().replace("'", "").replace('"', '')


def initialize_output_csv(columns: list) -> None:
    """
    Create the output CSV file with headers if it does not exist.
    The CSV will have the same columns as the source DataFrame, plus a 'success' column.
    """
    if not os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
        logging.info(f"Created new CSV file with headers: {OUTPUT_CSV}")
    else:
        logging.info(f"CSV file {OUTPUT_CSV} already exists.")


def load_processed_row_ids() -> set:
    """
    Load the set of already processed row IDs from the output CSV.
    
    Returns:
        A set of pt_row_id strings that have already been written to OUTPUT_CSV.
    """
    processed_ids = set()
    if os.path.exists(OUTPUT_CSV):
        try:
            df_existing = pd.read_csv(OUTPUT_CSV, dtype=str)
            if 'pt_row_id' in df_existing.columns:
                processed_ids = set(df_existing['pt_row_id'].dropna().tolist())
        except Exception as e:
            logging.error(f"Error reading {OUTPUT_CSV}: {e}")
    return processed_ids


def write_report_text(row: pd.Series, extracted_data: Dict[str, Any]) -> None:
    """
    Write a detailed text file containing the row metadata, original report,
    and extracted data. The file is named using the row's 'pt_row_id' value.

    Args:
        row: A Pandas Series representing the row.
        extracted_data: The dictionary returned by the extract_data function.
                        May be None if extraction failed.
    """
    raw_row_id = str(row['pt_row_id'])
    safe_row_id = sanitize_filename(raw_row_id)
    filename = os.path.join(OUTPUT_DIR, f"{safe_row_id}.txt")
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Row ID: {raw_row_id}\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("Full Row Data:\n")
            f.write(json.dumps(row.to_dict(), indent=4))
            f.write("\n\n" + "=" * 50 + "\n\n")
            
            f.write("Original Report:\n")
            f.write(str(row['combined_report']))
            f.write("\n\n" + "=" * 50 + "\n\n")
            
            if extracted_data is not None:
                f.write("Extracted Data:\n")
                f.write(json.dumps(extracted_data, indent=4))
            else:
                f.write("No extracted data available due to extraction failure.")
        logging.info(f"Successfully wrote report text file: {filename}")
    except Exception as e:
        logging.error(f"Error writing report text file {filename}: {e}")


def update_row_with_extraction(row: pd.Series, extracted_data: Dict[str, Any]) -> pd.Series:
    """
    Update the DataFrame row with values extracted from the report.
    Expected keys in extracted_data:
        - Clinical_Reason, Primary_Diagnosis, CT_Regions, CT_Contrast_Agent,
          Lung_Nodules, Lung_Hypermetabolic_Regions, Lymph_Nodes_Hypermetabolic_Regions,
          Other_Hypermetabolic_Regions, PET_Tracer, PET_Scan_Region,
          PET_Blood_Glucose_Level, PET_Waiting_Time.
    
    This function maps these keys to the DataFrame columns:
        clinical_reason, primary_diagnosis, ct_regions, ct_contrast_agent,
        lung_nodules, lung_hypermetabolic, lymph_nodes_hypermetabolic, 
        other_hypermetabolic, pet_tracer, pet_scan_region,
        pet_blood_glucose_level, pet_waiting_time.
    
    Also sets a 'success' flag to True.
    
    Args:
        row: The Pandas Series to update.
        extracted_data: The dictionary with extracted data.
    
    Returns:
        The updated Pandas Series.
    """
    row['clinical_reason'] = extracted_data.get("Clinical_Reason", "")
    row['primary_diagnosis'] = extracted_data.get("Primary_Diagnosis", "")
    row['ct_regions'] = json.dumps(extracted_data.get("CT_Regions", []))
    row['ct_contrast_agent_extracted'] = extracted_data.get("CT_Contrast_Agent", "")
    row['lung_nodules'] = json.dumps(extracted_data.get("Lung_Nodules", []))
    row['lung_hypermetabolic'] = json.dumps(extracted_data.get("Lung_Hypermetabolic_Regions", []))
    row['lymph_nodes_hypermetabolic'] = json.dumps(extracted_data.get("Lymph_Nodes_Hypermetabolic_Regions", []))
    row['other_hypermetabolic'] = json.dumps(extracted_data.get("Other_Hypermetabolic_Regions", []))
    row['pet_tracer'] = extracted_data.get("PET_Tracer", "")
    row['pet_scan_region'] = extracted_data.get("PET_Scan_Region", "")
    row['pet_blood_glucose_level'] = extracted_data.get("PET_Blood_Glucose_Level", "")
    row['pet_waiting_time'] = extracted_data.get("PET_Waiting_Time", "")
    row['success'] = True
    return row


def extract_with_retry(report_text: str, row_id: str) -> Dict[str, Any]:
    """
    Attempt to extract data from the report text using the extract_data function.
    Retries up to MAX_RETRIES times if an error occurs.

    Args:
        report_text: The combined report text.
        row_id: The unique identifier of the row (for logging).

    Returns:
        A dictionary with the extracted data if successful, or an empty dict otherwise.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Processing pt_row_id {row_id}: Attempt {attempt}/{MAX_RETRIES}")
            extraction_result = extract_data(report_text)
            extracted_data = json.loads(extraction_result)
            logging.info(f"Extraction succeeded for pt_row_id {row_id} on attempt {attempt}")
            return extracted_data
        except Exception as e:
            logging.error(f"Attempt {attempt} failed for pt_row_id {row_id}: {e}")
            if attempt < MAX_RETRIES:
                sleep(RETRY_DELAY * attempt)
    logging.error(f"All extraction attempts failed for pt_row_id {row_id}")
    return {}


def process_row(row: pd.Series, all_columns: list, processed_ids: set) -> None:
    """
    Process a single row: if the row's 'clinical_reason' is missing, run extraction;
    otherwise, write the row as-is to the output CSV. This function writes a detailed
    report text file and appends the updated row to OUTPUT_CSV. All writes are protected
    by a global lock (csv_lock) to ensure thread safety.

    Args:
        row: The Pandas Series representing the row to process.
        all_columns: List of column names (the CSV header).
        processed_ids: A shared set of already processed pt_row_ids.
    """
    row_id = str(row.get('pt_row_id', '')).strip()
    if not row_id:
        logging.error("Row missing pt_row_id. Skipping.")
        return

    # Check if this pt_row_id has been processed (using the shared lock)
    with csv_lock:
        if row_id in processed_ids:
            logging.info(f"pt_row_id {row_id} already processed, skipping.")
            return

    # If the row already has a clinical_reason, consider it processed.
    clinical_reason = row.get('clinical_reason', '')
    if pd.notna(clinical_reason) and str(clinical_reason).strip() != "":
        row['success'] = True
        with csv_lock:
            with open(OUTPUT_CSV, 'a', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                writer.writerow(row.to_dict())
            processed_ids.add(row_id)
        logging.info(f"pt_row_id {row_id} already had clinical_reason; written to CSV.")
        return

    # Otherwise, run extraction.
    report_text = row.get('combined_report', '')
    if not report_text:
        logging.error(f"pt_row_id {row_id} missing report text, skipping extraction.")
        row['success'] = False
        with csv_lock:
            with open(OUTPUT_CSV, 'a', encoding='utf-8', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_columns)
                writer.writerow(row.to_dict())
            processed_ids.add(row_id)
        return

    extracted_data = extract_with_retry(report_text, row_id)
    if extracted_data:
        row = update_row_with_extraction(row, extracted_data)
    else:
        row['success'] = False

    # Write the detailed report text file using row_id as filename.
    write_report_text(row, extracted_data if extracted_data else None)

    # Append the updated row to the output CSV.
    with csv_lock:
        with open(OUTPUT_CSV, 'a', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=all_columns)
            writer.writerow(row.to_dict())
        processed_ids.add(row_id)
    logging.info(f"Finished processing pt_row_id {row_id} with success={row.get('success')}")


# =============================================================================
#  MAIN PROCESSING LOGIC
# =============================================================================

def main():
    """
    Main function that orchestrates the extraction process:
              1. Loads the source CSV (gradient_pt_ct_all_pairs_query.csv).
      2. Initializes the output directory and CSV.
      3. Loads already processed pt_row_ids from the output CSV.
      4. Iterates over rows and submits those that need extraction (i.e. missing
         'clinical_reason') to a thread pool for parallel processing.
    
    Note:
      - The CSV writes are protected by a global lock to avoid conflicting records.
      - If the job terminates, resume logic ensures that already processed rows are skipped.
    """
    # Load the source DataFrame.
    try:
        df = pd.read_csv(INPUT_CSV, dtype=str)
    except Exception as e:
        logging.critical(f"Failed to read source CSV {INPUT_CSV}: {e}")
        return

    # Ensure output directory exists.
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Determine the CSV header: use df columns and add extracted fields.
    all_columns = list(df.columns)
    
    # Add extracted fields
    extracted_fields = [
        'clinical_reason',
        'primary_diagnosis', 
        'ct_regions',
        'ct_contrast_agent_extracted',
        'lung_nodules',
        'lung_hypermetabolic',
        'lymph_nodes_hypermetabolic',
        'other_hypermetabolic',
        'pet_tracer',
        'pet_scan_region',
        'pet_blood_glucose_level',
        'pet_waiting_time',
        'success'
    ]
    
    # Add extracted fields that don't already exist
    for field in extracted_fields:
        if field not in all_columns:
            all_columns.append(field)
            
    initialize_output_csv(all_columns)

    # Load the set of already processed pt_row_ids.
    processed_ids = load_processed_row_ids()

    # Create a list of rows to process (those not already processed).
    rows_to_process = []
    for _, row in df.iterrows():
        row_id = str(row.get('pt_row_id', '')).strip()
        if row_id and row_id not in processed_ids:
            rows_to_process.append(row)

    logging.info(f"Total rows to process: {len(rows_to_process)}")

    # Process rows in parallel using ThreadPoolExecutor.
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_row, row, all_columns, processed_ids)
            for row in rows_to_process
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logging.error(f"Exception in thread: {e}")

if __name__ == '__main__':
    main()