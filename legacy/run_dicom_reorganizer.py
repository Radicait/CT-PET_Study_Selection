#!/usr/bin/env python3
"""
Simple script to run the DICOM reorganizer with common configurations
"""

import subprocess
import sys
import os

def run_reorganizer(mode='dry-run', max_studies=None):
    """
    Run the DICOM reorganizer with specified parameters
    
    Args:
        mode: 'dry-run', 'test' (5 studies), or 'full'
        max_studies: Override number of studies to process
    """
    
    script_path = os.path.join(os.path.dirname(__file__), 'dicom_reorganizer.py')
    
    cmd = [sys.executable, script_path]
    
    if mode == 'dry-run':
        cmd.append('--dry-run')
        print("Running in DRY RUN mode - no files will be copied")
    elif mode == 'test':
        cmd.extend(['--max-studies', '5'])
        print("Running in TEST mode - processing only 5 studies")
    elif mode == 'full':
        print("Running in FULL mode - processing all studies")
    
    if max_studies:
        cmd.extend(['--max-studies', str(max_studies)])
    
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\nReorganization completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nError running reorganizer: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run DICOM reorganizer with common options')
    parser.add_argument('--mode', choices=['dry-run', 'test', 'full'], default='dry-run',
                        help='Run mode: dry-run (default), test (5 studies), or full')
    parser.add_argument('--max-studies', type=int, 
                        help='Maximum number of studies to process')
    
    args = parser.parse_args()
    
    success = run_reorganizer(args.mode, args.max_studies)
    sys.exit(0 if success else 1) 