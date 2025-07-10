#!/usr/bin/env python3
"""
Batch processing script for extracting PolyFEM optimization data from multiple log files.
Processes all optimization folders in 'results' directory and saves CSVs to 'csv_results'.
"""

import os
import sys
import glob
from pathlib import Path

# Import the single extraction function
# Try different possible names for the single extraction script
try:
    from single_extract import extract_optimization_data
except ImportError:
    try:
        from single_extract import extract_optimization_data
    except ImportError:
        try:
            from single_extract import extract_optimization_data
        except ImportError:
            print("Error: Could not import extract_optimization_data function.")
            print("Make sure one of these files is in the same directory as this script:")
            print("  - extract_single_log.py")
            print("  - single_extract.py") 
            print("  - extract_results_csv.py")
            print("And that it contains the extract_optimization_data function.")
            sys.exit(1)

def find_log_file(folder_path):
    """
    Find the log file in an optimization folder.
    Looks for common log file patterns.
    
    Args:
        folder_path (str): Path to the optimization folder
        
    Returns:
        str or None: Path to the log file if found, None otherwise
    """
    # Common log file names/patterns
    log_patterns = [
        'log',
        'log.txt', 
        'optimization.log',
        'polyfem.log',
        '*.log',
        'output.log'
    ]
    
    for pattern in log_patterns:
        log_path = os.path.join(folder_path, pattern)
        if '*' in pattern:
            # Use glob for wildcard patterns
            matches = glob.glob(log_path)
            if matches:
                return matches[0]  # Return first match
        else:
            # Direct file check
            if os.path.isfile(log_path):
                return log_path
    
    return None

def process_all_optimizations(results_dir="results", csv_dir="csv_results"):
    """
    Process all optimization folders and extract CSV data.
    
    Args:
        results_dir (str): Directory containing optimization folders
        csv_dir (str): Directory to save CSV results
    """
    
    # Get script directory and parent directory
    script_dir = Path(__file__).parent
    parent_dir = script_dir.parent
    
    # Set up directory paths
    results_path = parent_dir / results_dir
    csv_path = parent_dir / csv_dir
    
    # Check if results directory exists
    if not results_path.exists():
        print(f"Error: Results directory '{results_path}' does not exist!")
        return
    
    # Create CSV output directory if it doesn't exist
    csv_path.mkdir(exist_ok=True)
    print(f"Output directory: {csv_path}")
    
    # Find all optimization folders
    optimization_folders = [f for f in results_path.iterdir() if f.is_dir()]
    
    if not optimization_folders:
        print(f"No subdirectories found in '{results_path}'")
        return
    
    print(f"Found {len(optimization_folders)} optimization folders")
    print("=" * 60)
    
    # Process each folder
    successful = 0
    failed = 0
    
    for folder in sorted(optimization_folders):
        folder_name = folder.name
        print(f"\nProcessing: {folder_name}")
        
        # Find log file in this folder
        log_file = find_log_file(folder)
        
        if log_file is None:
            print(f"  ❌ No log file found in {folder}")
            failed += 1
            continue
        
        print(f"  📄 Found log file: {os.path.basename(log_file)}")
        
        # Set output CSV path
        csv_output = csv_path / f"{folder_name}.csv"
        
        try:
            # Extract data using the single extraction function
            extract_optimization_data(log_file, str(csv_output))
            print(f"  ✅ Successfully extracted to: {csv_output.name}")
            successful += 1
            
        except Exception as e:
            print(f"  ❌ Failed to process {folder_name}: {str(e)}")
            failed += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total folders processed: {len(optimization_folders)}")
    print(f"Successful extractions: {successful}")
    print(f"Failed extractions: {failed}")
    
    if successful > 0:
        print(f"\nCSV files saved in: {csv_path}")
        print("Generated files:")
        for csv_file in sorted(csv_path.glob("*.csv")):
            print(f"  - {csv_file.name}")

def main():
    """Main function with command line argument support."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch extract PolyFEM optimization data from multiple log files"
    )
    parser.add_argument(
        "--results-dir", 
        default="results",
        help="Directory containing optimization folders (default: results)"
    )
    parser.add_argument(
        "--csv-dir",
        default="csv_results", 
        help="Output directory for CSV files (default: csv_results)"
    )
    parser.add_argument(
        "--list-folders",
        action="store_true",
        help="List all folders in results directory and exit"
    )
    
    args = parser.parse_args()
    
    # List folders option
    if args.list_folders:
        script_dir = Path(__file__).parent
        parent_dir = script_dir.parent
        results_path = parent_dir / args.results_dir
        
        if results_path.exists():
            folders = [f.name for f in results_path.iterdir() if f.is_dir()]
            print(f"Optimization folders in '{results_path}':")
            for folder in sorted(folders):
                print(f"  - {folder}")
        else:
            print(f"Results directory '{results_path}' does not exist!")
        return
    
    # Process all optimizations
    process_all_optimizations(args.results_dir, args.csv_dir)

if __name__ == "__main__":
    main()