#!/usr/bin/env python3
"""
Delete VTU/VTM files where iteration number (second number in filename) is not 10.

File naming pattern: opt_{optimization}_{iteration}_{control_points}[_surf].{ext}
- Keep files where iteration == 10
- Delete files where iteration != 10
"""

import re
import os
from pathlib import Path

def extract_iteration_number(filename):
    """Extract iteration number from opt_X_Y_Z[_surf].ext filename."""
    
    # Pattern for opt_X_Y_Z_surf.vtu
    surf_pattern = r'opt_(\d+)_(\d+)_(\d+)_surf\.(vtu|vtm)$'
    surf_match = re.match(surf_pattern, filename)
    if surf_match:
        return int(surf_match.group(2))  # Return Y (iteration number)
    
    # Pattern for opt_X_Y_Z.vtu or opt_X_Y_Z.vtm
    regular_pattern = r'opt_(\d+)_(\d+)_(\d+)\.(vtu|vtm)$'
    regular_match = re.match(regular_pattern, filename)
    if regular_match:
        return int(regular_match.group(2))  # Return Y (iteration number)
    
    return None

def cleanup_job_folder(job_dir):
    """Clean up VTU/VTM files in a single job folder."""
    job_path = Path(job_dir)
    
    # Find all relevant files
    files_to_check = []
    for pattern in ['*.vtu', '*.vtm']:
        files_to_check.extend(job_path.glob(pattern))
    
    deleted_count = 0
    kept_count = 0
    
    for file_path in files_to_check:
        filename = file_path.name
        iteration_num = extract_iteration_number(filename)
        
        if iteration_num is not None:
            if iteration_num != 10:
                # Delete file if iteration is not 10
                try:
                    file_path.unlink()
                    deleted_count += 1
                    print(f"  Deleted: {filename} (iteration {iteration_num})")
                except Exception as e:
                    print(f"  Error deleting {filename}: {e}")
            else:
                # Keep file if iteration is 10
                kept_count += 1
                print(f"  Kept: {filename} (iteration {iteration_num})")
    
    return deleted_count, kept_count

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up VTU/VTM files keeping only iteration 10')
    parser.add_argument('--results-dir', default='results', help='Results directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    args = parser.parse_args()
    
    # Script is in scripts/ subdirectory, go up one level to project root
    project_root = Path(__file__).parent.parent
    results_dir = project_root / args.results_dir
    
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return
    
    # Find job directories
    job_dirs = [d for d in results_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    job_dirs.sort()
    
    print(f"{'DRY RUN: ' if args.dry_run else ''}Cleaning VTU/VTM files in {len(job_dirs)} job folders...")
    print("Keeping only files with iteration number = 10\n")
    
    total_deleted = 0
    total_kept = 0
    
    for job_dir in job_dirs:
        print(f"Processing {job_dir.name}:")
        
        if args.dry_run:
            # In dry run mode, just show what would be deleted
            job_path = Path(job_dir)
            files_to_check = []
            for pattern in ['*.vtu', '*.vtm']:
                files_to_check.extend(job_path.glob(pattern))
            
            would_delete = 0
            would_keep = 0
            
            for file_path in files_to_check:
                filename = file_path.name
                iteration_num = extract_iteration_number(filename)
                
                if iteration_num is not None:
                    if iteration_num != 10:
                        would_delete += 1
                        print(f"  Would delete: {filename} (iteration {iteration_num})")
                    else:
                        would_keep += 1
                        print(f"  Would keep: {filename} (iteration {iteration_num})")
            
            total_deleted += would_delete
            total_kept += would_keep
            print(f"  Summary: {would_delete} would be deleted, {would_keep} would be kept")
        else:
            # Actually delete files
            deleted, kept = cleanup_job_folder(job_dir)
            total_deleted += deleted
            total_kept += kept
            print(f"  Summary: {deleted} deleted, {kept} kept")
        
        print()
    
    action = "Would delete" if args.dry_run else "Deleted"
    action_kept = "Would keep" if args.dry_run else "Kept"
    print(f"Total: {action} {total_deleted} files, {action_kept} {total_kept} files")

if __name__ == "__main__":
    main()