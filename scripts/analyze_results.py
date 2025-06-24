#!/usr/bin/env python3
"""
Simple analysis of grid search results.
Uses only standard library + yaml (which you need anyway).
"""

import os
import yaml
import json
import re
import csv
from pathlib import Path

def extract_energy_from_log(log_path):
    """Extract final energy values from polyfem log."""
    energies = {}
    
    if not os.path.exists(log_path):
        return energies
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
        
        # Extract different energy components - look for the last occurrence
        patterns = {
            'total_energy': r'"total_energy":\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
            'target_match': r'"target_match":\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
            'collision_barrier': r'"collision_barrier":\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
            'smooth_layer_thickness': r'"smooth_layer_thickness":\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
            'boundary_smoothing': r'"boundary_smoothing":\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'
        }
        
        for energy_type, pattern in patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                # Take the last (final) value
                energies[energy_type] = float(matches[-1])
        
        # Extract convergence info
        energies['converged'] = "Reached iteration limit" not in content
            
    except Exception as e:
        print(f"Warning: Error reading log {log_path}: {e}")
    
    return energies

def check_job_status(job_dir):
    """Check if job completed successfully."""
    status_file = job_dir / "status.txt"
    if status_file.exists():
        with open(status_file, 'r') as f:
            return f.read().strip()
    
    # Check for log files to determine status
    log_files = list(job_dir.glob("slurm_*.out"))
    if log_files:
        return "COMPLETED"
    
    return "UNKNOWN"

def analyze_single_job(job_dir, job_info):
    """Analyze results from a single job."""
    result = {
        'job_id': job_info['job_id'],
        'status': check_job_status(job_dir),
    }
    
    # Add parameter values
    params = job_info['parameters']['smooth_layer_thickness']
    result['weight'] = params['weight']
    result['dhat'] = params['dhat']
    
    # Extract energies from log
    log_files = list(job_dir.glob("slurm_*.out"))
    if log_files:
        log_path = log_files[0]  # Take first log file
        energies = extract_energy_from_log(log_path)
        result.update(energies)
    
    # Check for output files
    vtu_files = list(job_dir.glob("*.vtu"))
    result['num_output_files'] = len(vtu_files)
    
    return result

def save_results_csv(results, output_path):
    """Save results to CSV file."""
    if not results:
        return
    
    # Get all possible column names
    all_keys = set()
    for result in results:
        all_keys.update(result.keys())
    
    # Sort columns for consistent output
    columns = sorted(all_keys)
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)

def print_summary(results):
    """Print a simple text summary."""
    if not results:
        print("No results found!")
        return
    
    # Count status
    status_counts = {}
    for result in results:
        status = result.get('status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n=== GRID SEARCH SUMMARY ===")
    print(f"Total jobs: {len(results)}")
    for status, count in status_counts.items():
        print(f"{status}: {count}")
    
    # Find successful jobs
    successful_results = [r for r in results if r.get('status') == 'SUCCESS' and 'total_energy' in r]
    
    if successful_results:
        # Sort by total energy
        successful_results.sort(key=lambda x: x['total_energy'])
        
        print(f"\n=== BEST PARAMETERS (Top 3) ===")
        for i, result in enumerate(successful_results[:3]):
            print(f"\n{i+1}. Job ID: {result['job_id']}")
            print(f"   Weight: {result['weight']:.2e}")
            print(f"   Dhat: {result['dhat']:.2e}")
            print(f"   Total Energy: {result['total_energy']:.6e}")
            if 'target_match' in result:
                print(f"   Target Match: {result['target_match']:.6e}")
            if 'converged' in result:
                print(f"   Converged: {result['converged']}")
    
    # Print parameter ranges tested
    weights = sorted(set(r['weight'] for r in results))
    dhats = sorted(set(r['dhat'] for r in results))
    
    print(f"\n=== PARAMETER RANGES TESTED ===")
    print(f"Weights: {[f'{w:.1e}' for w in weights]}")
    print(f"Dhats: {[f'{d:.1e}' for d in dhats]}")

def main():
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "results"
    
    # Load job list
    job_list_path = project_root / "configs" / "generated" / "job_list.yaml"
    if not job_list_path.exists():
        print("Job list not found. Run generate_grid_configs.py first!")
        return
    
    with open(job_list_path, 'r') as f:
        job_data = yaml.safe_load(f)
    
    print(f"Analyzing {len(job_data['jobs'])} jobs...")
    
    # Analyze each job
    results = []
    
    for job_info in job_data['jobs']:
        job_id = job_info['job_id']
        job_dir = results_dir / job_id
        
        if not job_dir.exists():
            print(f"  {job_id}: Directory not found")
            continue
        
        result = analyze_single_job(job_dir, job_info)
        results.append(result)
        
        print(f"  {job_id}: {result['status']}")
    
    if not results:
        print("No results found!")
        return
    
    # Save results to CSV
    results_csv = results_dir / "grid_search_results.csv"
    save_results_csv(results, results_csv)
    print(f"\nDetailed results saved to: {results_csv}")
    
    # Print summary
    print_summary(results)
    
    print(f"\nAnalysis complete!")
    print(f"Open {results_csv} in Excel/LibreOffice to explore the data further.")

if __name__ == "__main__":
    main()