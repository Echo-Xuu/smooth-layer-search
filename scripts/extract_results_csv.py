#!/usr/bin/env python3
"""
Extract optimization metrics from polyfem grid search results.
"""

import os
import re
import json
import pandas as pd
from pathlib import Path

def extract_optimization_data(log_content):
    """Extract optimization progression from log."""
    progression = []
    
    # Patterns for key information
    level_pattern = r'Starting multigrid level (\d+) with (\d+) control points'
    iter_pattern = r'Iteration (\d+).*?objective[:\s]+([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'
    timing_pattern = r'Forward simulation.*?(\d+\.?\d*)\s*seconds'
    
    lines = log_content.split('\n')
    current_level = 0
    current_control_points = 0
    
    for i, line in enumerate(lines):
        # Check for multigrid level
        level_match = re.search(level_pattern, line, re.IGNORECASE)
        if level_match:
            current_level = int(level_match.group(1))
            current_control_points = int(level_match.group(2))
            continue
        
        # Check for iteration results
        iter_match = re.search(iter_pattern, line, re.IGNORECASE)
        if iter_match:
            iteration = int(iter_match.group(1))
            objective = float(iter_match.group(2))
            
            # Look for timing in nearby lines
            simulation_time = None
            for search_line in lines[max(0, i-3):min(len(lines), i+5)]:
                timing_match = re.search(timing_pattern, search_line)
                if timing_match:
                    simulation_time = float(timing_match.group(1))
                    break
            
            progression.append({
                'multigrid_level': current_level,
                'control_points': current_control_points,
                'iteration': iteration,
                'objective_value': objective,
                'forward_sim_time_seconds': simulation_time
            })
    
    return progression

def get_job_parameters(job_dir):
    """Extract weight and dhat from config file."""
    config_file = job_dir / "run_MR_Conradlow.json"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            for functional in config.get('functionals', []):
                if functional.get('type') == 'smooth_layer_thickness':
                    return {
                        'weight': functional.get('weight'),
                        'dhat': functional.get('dhat')
                    }
        except:
            pass
    return {'weight': None, 'dhat': None}

def analyze_job(job_dir):
    """Analyze single job directory."""
    job_path = Path(job_dir)
    job_id = job_path.name
    
    # Get parameters
    params = get_job_parameters(job_path)
    
    # Check status
    status_file = job_path / "status.txt"
    status = "UNKNOWN"
    if status_file.exists():
        with open(status_file, 'r') as f:
            status = f.read().strip()
    
    # Read log file
    log_files = list(job_path.glob("slurm_*.out"))
    if not log_files:
        return None, []
    
    try:
        with open(log_files[0], 'r') as f:
            log_content = f.read()
    except:
        return None, []
    
    # Extract progression
    progression = extract_optimization_data(log_content)
    
    if not progression:
        return None, []
    
    # Calculate summary
    max_control_points = max(step['control_points'] for step in progression)
    max_level = max(step['multigrid_level'] for step in progression)
    total_iterations = len(progression)
    final_objective = progression[-1]['objective_value']
    
    # Add job info to each step
    for step in progression:
        step['job_id'] = job_id
        step.update(params)
    
    summary = {
        'job_id': job_id,
        'status': status,
        'max_control_points': max_control_points,
        'max_multigrid_level': max_level,
        'total_iterations': total_iterations,
        'final_objective_value': final_objective,
        **params
    }
    
    return summary, progression

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract polyfem optimization metrics')
    parser.add_argument('--results-dir', default='results', help='Results directory')
    parser.add_argument('--output-dir', default='analysis_output', help='Output directory')
    args = parser.parse_args()
    
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
            print(f"  {job_dir.name}: {summary['max_control_points']} control points, {summary['total_iterations']} iterations")
    
    # Save results
    if summary_results:
        summary_df = pd.DataFrame(summary_results)
        summary_file = output_dir / "grid_search_summary.csv"
        summary_df.to_csv(summary_file, index=False)
        
        progression_df = pd.DataFrame(detailed_progression)
        progression_file = output_dir / "optimization_progression.csv"
        progression_df.to_csv(progression_file, index=False)
        
        print(f"\nResults saved:")
        print(f"  Summary: {summary_file}")
        print(f"  Progression: {progression_file}")
        print(f"  Jobs analyzed: {len(summary_results)}")
    else:
        print("No valid results found.")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    exit(main())