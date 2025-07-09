#!/usr/bin/env python3
"""
Single PolyFEM optimization log extraction script.
Can be used standalone or imported by batch processing scripts.
"""

import re
import csv

def extract_optimization_data(log_file_path, output_csv_path, verbose=True):
    """
    Extract optimization data from PolyFEM cascaded optimization log file.
    Correctly identifies control point vs full vertex levels and main simulation times.
    
    Args:
        log_file_path (str): Path to the log file
        output_csv_path (str): Path to output CSV file
        verbose (bool): Whether to print progress messages
    """
    
    # Read the log file
    try:
        with open(log_file_path, 'r') as file:
            lines = file.readlines()
    except FileNotFoundError:
        if verbose:
            print(f"Error: Log file '{log_file_path}' not found!")
        raise
    except Exception as e:
        if verbose:
            print(f"Error reading log file: {e}")
        raise
    
    # Data storage
    simulation_data = []
    
    # Tracking variables
    current_level = None
    current_control_points = None
    current_iteration = None
    level_counter = 0
    needs_new_full_level = False
    
    # Patterns
    bbw_handles_pattern = r'BBW: Computing initial weights for (\d+) handles'
    lbfgs_start_pattern = r'\[adjoint-polyfem\] \[debug\] Starting L-BFGS'
    iteration_save_pattern = r'\[adjoint-polyfem\] \[info\] Saving iteration (\d+)'
    
    # More specific pattern for main forward simulation completion
    # Look for lines that indicate simulation completion (like "16/16 t=4") followed by timing
    simulation_completion_pattern = r'\[polyfem\] \[info\] \d+/\d+\s+t=[\d.]+$'
    simulation_time_pattern = r'\[polyfem\] \[info\]\s+took\s+([\d.]+)s'
    
    target_match_pattern = r'\[adjoint-polyfem\] \[debug\] \[target_match\] ([\d.]+)'
    collision_barrier_pattern = r'\[adjoint-polyfem\] \[debug\] \[collision_barrier\] ([\d.]+)'
    smooth_layer_pattern = r'\[adjoint-polyfem\] \[debug\] \[smooth_layer_thickness\] ([\d.]+)'
    boundary_smoothing_pattern = r'\[adjoint-polyfem\] \[debug\] \[boundary_smoothing\] ([\d.]+)'
    
    # Track simulations within current iteration
    simulations_in_current_iteration = []
    
    # Track simulation completion state
    simulation_just_completed = False
    
    for line_idx, line in enumerate(lines):
        line = line.strip()
        
        # Check for BBW handles computation (control point level)
        bbw_match = re.search(bbw_handles_pattern, line)
        if bbw_match:
            # Process any remaining simulations from previous level
            if simulations_in_current_iteration and current_level is not None:
                for i, sim in enumerate(simulations_in_current_iteration):
                    sim['simulation_in_iteration'] = i
                    simulation_data.append(sim)
            
            # Start new control point level
            current_level = level_counter
            current_control_points = int(bbw_match.group(1))
            current_iteration = None
            simulations_in_current_iteration = []
            level_counter += 1
            if verbose:
                print(f"Found control point level {current_level} with {current_control_points} control points")
        
        # Check for L-BFGS start (only creates new level if no recent BBW)
        elif re.search(lbfgs_start_pattern, line):
            # Only create a new level if we need a new full vertex level
            if needs_new_full_level or current_control_points is None:
                # Process any remaining simulations from previous level
                if simulations_in_current_iteration and current_level is not None:
                    for i, sim in enumerate(simulations_in_current_iteration):
                        sim['simulation_in_iteration'] = i
                        simulation_data.append(sim)
                
                # Start new full vertex level
                current_level = level_counter
                current_control_points = -1  # Full vertices
                current_iteration = None
                simulations_in_current_iteration = []
                level_counter += 1
                needs_new_full_level = False
                if verbose:
                    print(f"Found full vertex level {current_level} (all vertices)")
            
            # Reset iteration tracking for optimization start
            current_iteration = 0  # We'll be working on iteration 0
        
        # Check for simulation completion marker
        elif re.search(simulation_completion_pattern, line):
            simulation_just_completed = True
        
        # Check for simulation timing (only if we just saw completion)
        elif simulation_just_completed:
            time_match = re.search(simulation_time_pattern, line)
            if time_match and current_level is not None:
                sim_time = float(time_match.group(1))
                if verbose:
                    print(f"Found main simulation time: {sim_time}s at level {current_level}")
                
                # Create simulation record
                sim_record = {
                    'level': current_level,
                    'control_points': current_control_points if current_control_points != -1 else 'full',
                    'iteration': current_iteration if current_iteration is not None else 'pre_opt',
                    'simulation_in_iteration': len(simulations_in_current_iteration),
                    'simulation_time': sim_time,
                    'target_match': None,
                    'collision_barrier': None,
                    'smooth_layer_thickness': None,
                    'boundary_smoothing': None
                }
                
                simulations_in_current_iteration.append(sim_record)
            
            # Reset completion flag
            simulation_just_completed = False
        
        # Extract objective values and apply to the last simulation
        if simulations_in_current_iteration:
            last_sim = simulations_in_current_iteration[-1]
            
            target_match = re.search(target_match_pattern, line)
            if target_match:
                last_sim['target_match'] = float(target_match.group(1))
            
            collision_barrier_match = re.search(collision_barrier_pattern, line)
            if collision_barrier_match:
                last_sim['collision_barrier'] = float(collision_barrier_match.group(1))
            
            smooth_layer_match = re.search(smooth_layer_pattern, line)
            if smooth_layer_match:
                last_sim['smooth_layer_thickness'] = float(smooth_layer_match.group(1))
            
            boundary_smoothing_match = re.search(boundary_smoothing_pattern, line)
            if boundary_smoothing_match:
                last_sim['boundary_smoothing'] = float(boundary_smoothing_match.group(1))
        
        # Check for iteration save (indicates iteration completion)
        iteration_match = re.search(iteration_save_pattern, line)
        if iteration_match:
            saved_iteration = int(iteration_match.group(1))
            
            # Add all simulations from current iteration to main data
            for i, sim in enumerate(simulations_in_current_iteration):
                sim['simulation_in_iteration'] = i
                simulation_data.append(sim)
            
            # Reset for next iteration
            current_iteration = saved_iteration + 1  # Next iteration to work on
            simulations_in_current_iteration = []
            # Mark that we need a new full vertex level after control point level
            if current_control_points != -1:
                needs_new_full_level = True
    
    # Process any remaining simulations
    if simulations_in_current_iteration and current_level is not None:
        for i, sim in enumerate(simulations_in_current_iteration):
            sim['simulation_in_iteration'] = i
            simulation_data.append(sim)
    
    # Write to CSV
    if simulation_data:
        try:
            with open(output_csv_path, 'w', newline='') as csvfile:
                fieldnames = ['level', 'control_points', 'iteration', 'simulation_in_iteration', 'simulation_time', 
                             'target_match', 'collision_barrier', 'smooth_layer_thickness', 'boundary_smoothing']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data
                for row in simulation_data:
                    writer.writerow(row)
        except Exception as e:
            if verbose:
                print(f"Error writing CSV file: {e}")
            raise
        
        # Print summary statistics only if verbose
        if verbose:
            unique_levels = set([row['level'] for row in simulation_data])
            unique_control_points = set([row['control_points'] for row in simulation_data if row['control_points'] != 'full' and row['control_points'] is not None])
            total_levels = len(unique_levels)
            total_simulations = len(simulation_data)
            
            print(f"\nExtracted data saved to {output_csv_path}")
            print(f"Total optimization levels: {total_levels}")
            print(f"Control point configurations: {sorted([int(cp) for cp in unique_control_points])} + full vertices")
            print(f"Total forward simulations: {total_simulations}")
            
            # Print detailed breakdown by control points
            level_stats = {}
            for row in simulation_data:
                level = row['level']
                control_points = row['control_points']
                iteration = row['iteration']
                
                if level not in level_stats:
                    level_stats[level] = {'control_points': control_points, 'iterations': {}}
                if iteration not in level_stats[level]['iterations']:
                    level_stats[level]['iterations'][iteration] = 0
                level_stats[level]['iterations'][iteration] += 1
            
            print("\nDetailed breakdown:")
            for level in sorted(level_stats.keys()):
                cp = level_stats[level]['control_points']
                iterations = level_stats[level]['iterations']
                total_sims_in_level = sum(iterations.values())
                total_iterations = len([k for k in iterations.keys() if k != 'pre_opt'])
                
                cp_str = f"{cp} control points" if cp != 'full' else "full vertices"
                print(f"Level {level} ({cp_str}):")
                print(f"  Total simulations: {total_sims_in_level}")
                print(f"  Total iterations: {total_iterations}")
                
                for iteration in sorted(iterations.keys(), key=lambda x: -1 if x == 'pre_opt' else x):
                    count = iterations[iteration]
                    if iteration == 'pre_opt':
                        print(f"  Pre-optimization: {count} simulations")
                    else:
                        print(f"  Iteration {iteration}: {count} simulations")
            
            # Show computational cost per iteration
            print("\nComputational cost analysis:")
            for level in sorted(level_stats.keys()):
                cp = level_stats[level]['control_points']
                level_data = [row for row in simulation_data if row['level'] == level]
                
                iteration_costs = {}
                for row in level_data:
                    iter_key = row['iteration']
                    if iter_key not in iteration_costs:
                        iteration_costs[iter_key] = {'count': 0, 'total_time': 0}
                    iteration_costs[iter_key]['count'] += 1
                    iteration_costs[iter_key]['total_time'] += row['simulation_time']
                
                cp_str = f"{cp} control points" if cp != 'full' else "full vertices"
                print(f"Level {level} ({cp_str}):")
                for iteration in sorted(iteration_costs.keys(), key=lambda x: -1 if x == 'pre_opt' else x):
                    if iteration != 'pre_opt':
                        count = iteration_costs[iteration]['count']
                        total_time = iteration_costs[iteration]['total_time']
                        avg_time = total_time / count if count > 0 else 0
                        print(f"  Iteration {iteration}: {count} sims, {total_time:.1f}s total, {avg_time:.1f}s avg")
    
    else:
        if verbose:
            print("No simulation data found in the log file.")
        raise ValueError("No simulation data found in the log file")

def main():
    """Main function for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract PolyFEM optimization data from a single log file"
    )
    parser.add_argument(
        "log_file",
        help="Path to the PolyFEM optimization log file"
    )
    parser.add_argument(
        "output_csv", 
        nargs='?',
        help="Path to output CSV file (default: same name as log file with .csv extension)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output"
    )
    
    args = parser.parse_args()
    
    # Determine output CSV path
    if args.output_csv:
        output_csv = args.output_csv
    else:
        # Generate CSV name from log file name
        log_path = args.log_file
        if log_path.endswith('.log'):
            output_csv = log_path[:-4] + '.csv'
        elif log_path.endswith('.txt'):
            output_csv = log_path[:-4] + '.csv'
        else:
            output_csv = log_path + '.csv'
    
    # Extract data
    try:
        extract_optimization_data(args.log_file, output_csv, verbose=not args.quiet)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
