#!/usr/bin/env python3
"""
Simple script to run the PET batch merger with common configurations
"""

import subprocess
import sys
import os

def run_merger(mode='dry-run', max_folders=None):
    """
    Run the PET batch merger with specified parameters
    
    Args:
        mode: 'dry-run', 'test' (2 folders), or 'full'
        max_folders: Override number of folders to process
    """
    
    script_path = os.path.join(os.path.dirname(__file__), 'merge_pet_batch.py')
    
    cmd = [sys.executable, script_path]
    
    if mode == 'dry-run':
        cmd.append('--dry-run')
        print("Running in DRY RUN mode - no files will be copied")
    elif mode == 'test':
        cmd.extend(['--max-folders', '2'])
        print("Running in TEST mode - processing only 2 patient folders")
    elif mode == 'full':
        print("Running in FULL mode - processing all patient folders")
    
    if max_folders:
        cmd.extend(['--max-folders', str(max_folders)])
    
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\nMerge completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nError running merger: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run PET batch merger with common options')
    parser.add_argument('--mode', choices=['dry-run', 'test', 'full'], default='dry-run',
                        help='Run mode: dry-run (default), test (2 folders), or full')
    parser.add_argument('--max-folders', type=int, 
                        help='Maximum number of patient folders to process')
    
    args = parser.parse_args()
    
    success = run_merger(args.mode, args.max_folders)
    sys.exit(0 if success else 1) 