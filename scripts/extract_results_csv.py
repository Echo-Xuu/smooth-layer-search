#!/usr/bin/env python3
"""
Extract focused optimization metrics from polyfem log output.
"""

import re
import pandas as pd
from pathlib import Path

def find_polyfem_logs(job_dir):
    """Find polyfem log files in job directory."""
    job_path = Path(job_dir)
    
    # Look for different possible log file locations
    possible_logs = [
        job_path / "polyfem.log",
        job_path / "optimization.log", 
        job_path / "log",
        *job_path.glob("slurm_*.out"),
        *job_path.glob("*.log")
    ]
    
    for log_file in possible_logs:
        if log_file.exists() and log_file.stat().st_size > 0:
            return log_file
    
    return None

def extract_optimization_data(log_content):
    """Extract control points, forward sim times, and objective progression."""
    
    # Patterns for extraction
    patterns = {
        'control_points': r'BBW: Computing initial weights for (\d+) handles',
        'forward_sim_time': r'\[polyfem\].*?took\s+([-+]?[0-9]*\.?[0-9]+)s',
        'lbfgs_iteration': r'\[L-BFGS\]\[Backtracking\].*?iter=(\d+).*?f=([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
        'lbfgs_pre_iteration': r'\[L-BFGS\]\[Backtracking\].*?pre LS iter=(\d+).*?f=([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)',
        'lbfgs_start': r'Starting L-BFGS with Backtracking solve f₀=([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'
    }
    
    lines = log_content.split('\n')
    
    # Extract highest control points
    max_control_points = 0
    for line in lines:
        cp_match = re.search(patterns['control_points'], line)
        if cp_match:
            control_points = int(cp_match.group(1))
            max_control_points = max(max_control_points, control_points)
    
    # Extract forward simulation times
    forward_sim_times = []
    for line in lines:
        time_match = re.search(patterns['forward_sim_time'], line)
        if time_match:
            forward_sim_times.append(float(time_match.group(1)))
    
    # Extract objective progression from L-BFGS
    objective_progression = []
    
    for line in lines:
        # Check for initial objective
        start_match = re.search(patterns['lbfgs_start'], line)
        if start_match:
            objective_progression.append({
                'iteration': 0,
                'objective_value': float(start_match.group(1))
            })
            continue
        
        # Check for iteration updates
        iter_match = re.search(patterns['lbfgs_iteration'], line) or re.search(patterns['lbfgs_pre_iteration'], line)
        if iter_match:
            objective_progression.append({
                'iteration': int(iter_match.group(1)),
                'objective_value': float(iter_match.group(2))
            })
    
    return max_control_points, forward_sim_times, objective_progression

def analyze_job(job_dir):
    """Analyze single job directory."""
    job_path = Path(job_dir)
    job_id = job_path.name
    
    log_file = find_polyfem_logs(job_path)
    if not log_file:
        return None, []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
    except Exception:
        return None, []
    
    max_control_points, forward_sim_times, objective_progression = extract_optimization_data(log_content)
    
    if not objective_progression:
        return None, []
    
    # Create detailed progression data
    progression_data = []
    for i, obj_data in enumerate(objective_progression):
        row = {
            'job_id': job_id,
            'max_control_points': max_control_points,
            'iteration': obj_data['iteration'],
            'objective_value': obj_data['objective_value'],
            'forward_sim_time_seconds': forward_sim_times[i] if i < len(forward_sim_times) else None
        }
        progression_data.append(row)
    
    summary = {
        'job_id': job_id,
        'max_control_points': max_control_points,
        'total_iterations': len(objective_progression),
        'total_forward_sim_time': sum(forward_sim_times),
        'final_objective_value': objective_progression[-1]['objective_value']
    }
    
    return summary, progression_data

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract focused polyfem optimization metrics')
    parser.add_argument('--results-dir', default='results', help='Results directory')
    parser.add_argument('--output-dir', default='analysis_output', help='Output directory')
    args = parser.parse_args()
    
    # Script is in scripts/ subdirectory, go up one level to project root
    project_root = Path(__file__).parent.parent
    results_dir = project_root / args.results_dir
    output_dir = project_root / args.output_dir
    output_dir.mkdir(exist_ok=True)
    
    # Find job directories
    job_dirs = [d for d in results_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    job_dirs.sort()
    
    print(f"Analyzing {len(job_dirs)} jobs...")
    
    summary_results = []
    detailed_progression = []
    
    for job_dir in job_dirs:
        summary, progression = analyze_job(job_dir)
        if summary:
            summary_results.append(summary)
            detailed_progression.extend(progression)
            print(f"  {job_dir.name}: analyzed")
        else:
            print(f"  {job_dir.name}: no data found")
    
    # Save results
    if summary_results:
        summary_df = pd.DataFrame(summary_results)
        summary_file = output_dir / "optimization_summary.csv"
        summary_df.to_csv(summary_file, index=False)
        
        progression_df = pd.DataFrame(detailed_progression)
        progression_file = output_dir / "objective_progression.csv"
        progression_df.to_csv(progression_file, index=False)
        
        print(f"\nSaved {len(summary_results)} job summaries to: {summary_file}")
        print(f"Saved {len(detailed_progression)} progression records to: {progression_file}")
    else:
        print("No valid optimization data found.")

if __name__ == "__main__":
    main()