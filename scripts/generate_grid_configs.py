#!/usr/bin/env python3
"""
Generate parameter grid configurations for polyfem grid search.
Tests combinations of internal target match weights and pressure boundary values.
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

def load_base_state_config(state_config_path):
    """Load the base state configuration."""
    with open(state_config_path, 'r') as f:
        return json.load(f)

def load_parameter_grid(grid_config_path):
    """Load parameter grid specification."""
    with open(grid_config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_parameter_combinations(param_grid):
    """Generate all parameter combinations."""
    combinations = []
    
    # Extract parameters
    params = param_grid['parameters']
    itm_params = params['internal_target_match']
    pb_params = params['pressure_boundary']
    
    # Generate all combinations
    for itm_weight, pb_pressure in itertools.product(
        itm_params['weight'],
        pb_params['pressure_magnitude']
    ):
        combinations.append({
            'internal_target_match': {
                'weight': itm_weight
            },
            'pressure_boundary': {
                'pressure_magnitude': pb_pressure
            }
        })
    
    return combinations

def update_run_config_with_params(base_config, params):
    """Update run configuration with specific parameters."""
    config = base_config.copy()
    
    # Update internal_target_match functional weight
    if 'internal_target_match' in params:
        for i, functional in enumerate(config['functionals']):
            if (functional.get('type') == 'transient_integral' and 
                functional.get('print_energy') == 'internal_target_match'):
                itm_params = params['internal_target_match']
                config['functionals'][i]['weight'] = float(itm_params['weight'])
                break
    
    return config

def update_state_config_with_params(base_state_config, params):
    """Update state configuration with specific parameters."""
    config = base_state_config.copy()
    
    # Update pressure boundary value
    if 'pressure_boundary' in params:
        pb_params = params['pressure_boundary']
        pressure_magnitude = float(pb_params['pressure_magnitude'])
        
        # Find and update pressure boundary with id=2
        for i, boundary in enumerate(config['boundary_conditions']['pressure_boundary']):
            if boundary.get('id') == 2:
                # Replace the pressure magnitude in the expression
                # Current format: "-1200 * (t/4)"
                # New format: "-{pressure_magnitude} * (t/4)"
                config['boundary_conditions']['pressure_boundary'][i]['value'] = f"-{pressure_magnitude} * (t/4)"
                break
    
    return config

def generate_job_id(params):
    """Generate unique job ID from parameters."""
    itm = params['internal_target_match']
    pb = params['pressure_boundary']
    
    # Convert to float and format
    itm_weight = float(itm['weight'])
    pb_pressure = float(pb['pressure_magnitude'])
    
    # Create compact representations
    itm_w_str = f"{itm_weight:.0e}".replace('+', '').replace('-', 'n')
    pb_p_str = f"{pb_pressure:.0f}"
    
    return f"itm_w{itm_w_str}_pb_p{pb_p_str}"

def main():
    # Paths
    project_root = Path(__file__).parent.parent
    grid_config_path = project_root / "configs" / "parameter_grid.yaml"
    output_dir = project_root / "configs" / "generated"
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Load parameter grid config
    param_grid = load_parameter_grid(grid_config_path)
    
    # Get base config paths from parameter grid
    base_run_config_path = project_root / param_grid['base_config']['run_config']
    base_state_config_path = project_root / param_grid['base_config']['state_config']
    
    # Load base configurations
    base_run_config = load_base_config(base_run_config_path)
    base_state_config = load_base_state_config(base_state_config_path)
    
    # Generate combinations
    combinations = generate_parameter_combinations(param_grid)
    
    print(f"Generating {len(combinations)} parameter combinations...")
    
    # Generate config files and job list
    job_list = []
    
    for i, params in enumerate(combinations):
        job_id = generate_job_id(params)
        
        # Update configurations
        run_config = update_run_config_with_params(base_run_config, params)
        state_config = update_state_config_with_params(base_state_config, params)
        
        # Save run configuration
        run_config_filename = f"run_{job_id}.json"
        run_config_path = output_dir / run_config_filename
        
        with open(run_config_path, 'w') as f:
            json.dump(run_config, f, indent=2)
        
        # Save state configuration
        state_config_filename = f"state_{job_id}.json"
        state_config_path = output_dir / state_config_filename
        
        with open(state_config_path, 'w') as f:
            json.dump(state_config, f, indent=2)
        
        # Update run config to point to the new state config
        run_config['states'][0]['path'] = state_config_filename
        
        # Re-save run configuration with updated state path
        with open(run_config_path, 'w') as f:
            json.dump(run_config, f, indent=2)
        
        # Add to job list
        job_info = {
            'job_id': job_id,
            'run_config_file': run_config_filename,
            'state_config_file': state_config_filename,
            'parameters': params
        }
        job_list.append(job_info)
        
        print(f"  {i+1:3d}: {job_id}")
        print(f"       ITM: w={float(params['internal_target_match']['weight']):.0e}")
        print(f"       PB:  p={float(params['pressure_boundary']['pressure_magnitude'])}")
        print()
    
    # Save job list
    job_list_path = output_dir / "job_list.yaml"
    with open(job_list_path, 'w') as f:
        yaml.dump({
            'total_jobs': len(job_list),
            'parameter_info': {
                'internal_target_match': {
                    'description': 'Internal target match functional weight',
                    'weight_range': param_grid['parameters']['internal_target_match']['weight']
                },
                'pressure_boundary': {
                    'description': 'Pressure boundary magnitude (replaces 1200 in -1200*(t/4))',
                    'pressure_range': param_grid['parameters']['pressure_boundary']['pressure_magnitude']
                }
            },
            'jobs': job_list
        }, f, default_flow_style=False)
    
    print(f"Generated {len(combinations)} configuration pairs in {output_dir}")
    print(f"Job list saved to {job_list_path}")
    print(f"\nParameter ranges tested:")
    print(f"  Internal target match weight: {param_grid['parameters']['internal_target_match']['weight']}")
    print(f"  Pressure boundary magnitude: {param_grid['parameters']['pressure_boundary']['pressure_magnitude']}")

if __name__ == "__main__":
    main()