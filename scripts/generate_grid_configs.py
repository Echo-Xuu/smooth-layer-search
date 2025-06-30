#!/usr/bin/env python3
"""
Generate parameter grid configurations for polyfem grid search.
"""

import json
import yaml
import os
import itertools
from pathlib import Path

def load_base_config(base_config_path):
    """Load the base run configuration."""
    with open(base_config_path, 'r') as f:
        return json.load(f)

def load_parameter_grid(grid_config_path):
    """Load parameter grid specification."""
    with open(grid_config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_parameter_combinations(param_grid):
    """Generate all parameter combinations."""
    combinations = []
    
    # Extract smooth_layer_thickness parameters
    slt_params = param_grid['smooth_layer_thickness']
    weights = slt_params['weight']
    dhats = slt_params['dhat']
    
    # Generate all combinations
    for weight, dhat in itertools.product(weights, dhats):
        combinations.append({
            'smooth_layer_thickness': {
                'weight': weight,
                'dhat': dhat
            }
        })
    
    return combinations

def update_config_with_params(base_config, params):
    """Update base configuration with specific parameters."""
    config = base_config.copy()
    
    # Find and update smooth_layer_thickness functional
    for i, functional in enumerate(config['functionals']):
        if functional.get('type') == 'smooth_layer_thickness':
            if 'smooth_layer_thickness' in params:
                slt_params = params['smooth_layer_thickness']
                # Convert to float in case they're strings
                config['functionals'][i]['weight'] = float(slt_params['weight'])
                config['functionals'][i]['dhat'] = float(slt_params['dhat'])
            break
    
    return config

def generate_job_id(params):
    """Generate unique job ID from parameters."""
    slt = params['smooth_layer_thickness']
    
    # Convert to float in case they're strings
    weight_val = float(slt['weight'])
    dhat_val = float(slt['dhat'])
    
    # Format as scientific notation and clean up
    weight_str = f"{weight_val:.0e}".replace('+', '').replace('-', 'n')
    dhat_str = f"{dhat_val:.0e}".replace('+', '').replace('-', 'n')
    
    return f"w{weight_str}_d{dhat_str}"

def main():
    # Paths
    project_root = Path(__file__).parent.parent
    grid_config_path = project_root / "configs" / "parameter_grid.yaml"
    output_dir = project_root / "configs" / "generated"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Load parameter grid config
    param_grid = load_parameter_grid(grid_config_path)
    
    # Get base config path from parameter grid
    base_config_path = project_root / param_grid['base_config']['run_config']
    base_config = load_base_config(base_config_path)
    
    # Generate combinations
    combinations = generate_parameter_combinations(param_grid)
    
    print(f"Generating {len(combinations)} parameter combinations...")
    
    # Generate config files and job list
    job_list = []
    
    for i, params in enumerate(combinations):
        job_id = generate_job_id(params)
        config = update_config_with_params(base_config, params)
        
        # Save configuration
        config_filename = f"run_{job_id}.json"
        config_path = output_dir / config_filename
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Add to job list
        job_info = {
            'job_id': job_id,
            'config_file': config_filename,
            'parameters': params
        }
        job_list.append(job_info)
        
        print(f"  {i+1:3d}: {job_id} -> {config_filename}")
    
    # Save job list
    job_list_path = output_dir / "job_list.yaml"
    with open(job_list_path, 'w') as f:
        yaml.dump({
            'total_jobs': len(job_list),
            'jobs': job_list
        }, f, default_flow_style=False)
    
    print(f"\nGenerated {len(combinations)} configurations in {output_dir}")
    print(f"Job list saved to {job_list_path}")

if __name__ == "__main__":
    main()