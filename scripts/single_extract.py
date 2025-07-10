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
    Correctly identifies control point levels and main simulation times.
    
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
    
    # Patterns
    bbw_handles_pattern = r'BBW: Computing initial weights for (\d+) handles'
    lbfgs_start_pattern = r'\[adjoint-polyfem\] \[debug\] Starting L-BFGS'
    iteration_save_pattern = r'\[adjoint-polyfem\] \[info\] Saving iteration (\d+)'
    
    # Level detection patterns
    slim_warning_pattern = r'\[adjoint-polyfem\] \[warning\] Both in-line-search SLIM and after-line-search SLIM are ON!'
    full_vertex_indicator = r'\[adjoint-polyfem\] \[trace\] Using a characteristic length of 1'
    control_point_indicator = r'\[polyfem\] \[info\] Found 0 boundary loops, must be closed surface\.'
    
    # Simulation tracking patterns
    simulation_step_pattern = r'\[polyfem\] \[info\] (\d+)/(\d+)\s+t=[\d.]+$'  # e.g., "1/16 t=0.25" or "16/16 t=4"
    simulation_time_pattern = r'\[polyfem\] \[info\]\s+took\s+([\d.]+)s'
    
    target_match_pattern = r'\[adjoint-polyfem\] \[debug\] \[target_match\] ([\d.]+)'
    collision_barrier_pattern = r'\[adjoint-polyfem\] \[debug\] \[collision_barrier\] ([\d.]+)'
    smooth_layer_pattern = r'\[adjoint-polyfem\] \[debug\] \[smooth_layer_thickness\] ([\d.]+)'
    boundary_smoothing_pattern = r'\[adjoint-polyfem\] \[debug\] \[boundary_smoothing\] ([\d.]+)'
    
    # Track simulations accumulating toward current iteration
    pending_simulations = []  # Simulations completed but not yet assigned to a saved iteration
    
    # Track current simulation state
    pending_simulation = None  # Current simulation being tracked
    
    # Track level detection state
    expecting_level_type = False  # True when we just saw SLIM warning and expect level type indicator
    
    for line_idx, line in enumerate(lines):
        line = line.strip()
        
        # Check for SLIM warning (indicates start of level detection)
        if re.search(slim_warning_pattern, line):
            expecting_level_type = True
            continue
        
        # Check for level type indicators (after SLIM warning)
        if expecting_level_type:
            if re.search(full_vertex_indicator, line):
                # Process any remaining simulations from previous level
                if pending_simulations and current_level is not None:
                    for i, sim in enumerate(pending_simulations):
                        sim['simulation_in_iteration'] = i
                        if 'status' not in sim:
                            sim['status'] = 'completed'
                        simulation_data.append(sim)
                    pending_simulations = []
                
                # Start new full vertex level
                current_level = level_counter
                current_control_points = 'full'  # Full vertices
                current_iteration = None  # Will be set when L-BFGS starts
                level_counter += 1
                expecting_level_type = False
                if verbose:
                    print(f"Found full vertex level {current_level} (all vertices)")
                continue
                
            elif re.search(control_point_indicator, line):
                # Control point level - BBW pattern will follow shortly
                expecting_level_type = False
                if verbose:
                    print("Detected control point level start")
                continue
            else:
                # Neither pattern found, keep looking
                continue
        
        # Check for BBW handles computation (new control point level)
        bbw_match = re.search(bbw_handles_pattern, line)
        if bbw_match:
            # Process any remaining simulations from previous level
            if pending_simulations and current_level is not None:
                # These simulations belong to the last iteration of the previous level
                for i, sim in enumerate(pending_simulations):
                    sim['simulation_in_iteration'] = i
                    if 'status' not in sim:
                        sim['status'] = 'completed'
                    simulation_data.append(sim)
                pending_simulations = []
            
            # Start new control point level
            current_level = level_counter
            current_control_points = int(bbw_match.group(1))
            current_iteration = None  # Will be set when L-BFGS starts
            level_counter += 1
            if verbose:
                print(f"Found control point level {current_level} with {current_control_points} control points")
        
        # Check for L-BFGS start (optimization begins for current level)
        elif re.search(lbfgs_start_pattern, line):
            # Start optimization at current level
            current_iteration = 0  # We'll be working on iteration 0
            if verbose:
                cp_str = f"{current_control_points} control points" if current_control_points != 'full' else "full vertices"
                print(f"Starting optimization at level {current_level} ({cp_str})")
        
        # Check for simulation step progress (both start and completion)
        step_match = re.search(simulation_step_pattern, line)
        if step_match:
            current_step = int(step_match.group(1))
            total_steps = int(step_match.group(2))
            
            # If this is the first step of a simulation
            if current_step == 1:
                # Handle any previous incomplete simulation
                if pending_simulation is not None and not pending_simulation.get('completed', False):
                    # Previous simulation was incomplete - add to pending simulations
                    sim_record = {
                        'level': pending_simulation['level'],
                        'control_points': pending_simulation['control_points'],
                        'iteration': current_iteration if current_iteration is not None else 'pre_opt',
                        'simulation_in_iteration': -1,  # Will be set when iteration is saved
                        'simulation_time': None,  # Incomplete simulation
                        'status': 'incomplete',
                        'target_match': None,
                        'collision_barrier': None,
                        'smooth_layer_thickness': None,
                        'boundary_smoothing': None
                    }
                    pending_simulations.append(sim_record)
                    if verbose:
                        print(f"Found incomplete simulation at level {pending_simulation['level']} ({pending_simulation['control_points']} control points)" if pending_simulation['control_points'] != 'full' else f"Found incomplete simulation at level {pending_simulation['level']} (full vertices)")
                
                # Start tracking new simulation
                pending_simulation = {
                    'level': current_level,
                    'control_points': current_control_points,
                    'iteration': current_iteration if current_iteration is not None else 'pre_opt',
                    'completed': False,
                    'total_steps': total_steps
                }
            
            # If this is the last step of a simulation (completion)
            elif current_step == total_steps and pending_simulation is not None:
                pending_simulation['completed'] = True
        
        # Check for simulation timing (only if we have a completed pending simulation)
        elif pending_simulation is not None and pending_simulation.get('completed', False):
            time_match = re.search(simulation_time_pattern, line)
            if time_match:
                sim_time = float(time_match.group(1))
                if verbose:
                    level = pending_simulation['level']
                    control_points = pending_simulation['control_points']
                    iter_str = f"iteration {current_iteration}" if current_iteration is not None else "pre-optimization"
                    cp_str = f"{control_points} control points" if control_points != 'full' else "full vertices"
                    print(f"Found completed simulation: {sim_time}s at level {level} ({cp_str}) for {iter_str}")
                
                # Create simulation record
                sim_record = {
                    'level': pending_simulation['level'],
                    'control_points': pending_simulation['control_points'],
                    'iteration': pending_simulation['iteration'],
                    'simulation_in_iteration': -1,  # Will be set when iteration is saved
                    'simulation_time': sim_time,
                    'status': 'completed',
                    'target_match': None,
                    'collision_barrier': None,
                    'smooth_layer_thickness': None,
                    'boundary_smoothing': None
                }
                
                # Add to pending simulations (not final data yet)
                pending_simulations.append(sim_record)
                
                # Clear pending simulation
                pending_simulation = None
        
        # Extract objective values and apply to the last pending simulation
        if pending_simulations:
            last_sim = pending_simulations[-1]
            
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
            
            if verbose:
                print(f"Iteration {saved_iteration} saved with {len(pending_simulations)} simulations")
            
            # Move all pending simulations to final data with correct iteration info
            for i, sim in enumerate(pending_simulations):
                sim['iteration'] = saved_iteration
                sim['simulation_in_iteration'] = i
                if 'status' not in sim:
                    sim['status'] = 'completed'
                simulation_data.append(sim)
            
            # Clear pending simulations and set up for next iteration
            pending_simulations = []
            current_iteration = saved_iteration + 1  # Next iteration to work on
    
    # Handle any remaining pending simulations at end of log
    if pending_simulations:
        if verbose:
            print(f"Found {len(pending_simulations)} pending simulations at end of log")
        for i, sim in enumerate(pending_simulations):
            sim['simulation_in_iteration'] = i
            if 'status' not in sim:
                sim['status'] = 'completed'
            simulation_data.append(sim)
    
    # Handle any final incomplete simulation
    if pending_simulation is not None and not pending_simulation.get('completed', False):
        sim_record = {
            'level': pending_simulation['level'],
            'control_points': pending_simulation['control_points'],
            'iteration': current_iteration if current_iteration is not None else 'pre_opt',
            'simulation_in_iteration': len(pending_simulations),
            'simulation_time': None,
            'status': 'incomplete',
            'target_match': None,
            'collision_barrier': None,
            'smooth_layer_thickness': None,
            'boundary_smoothing': None
        }
        simulation_data.append(sim_record)
        if verbose:
            level = pending_simulation['level']
            control_points = pending_simulation['control_points']
            cp_str = f"{control_points} control points" if control_points != 'full' else "full vertices"
            print(f"Found incomplete simulation at end of log: level {level} ({cp_str})")
    
    # Write to CSV
    if simulation_data:
        try:
            with open(output_csv_path, 'w', newline='') as csvfile:
                fieldnames = ['level', 'control_points', 'iteration', 'simulation_in_iteration', 'simulation_time', 
                             'status', 'target_match', 'collision_barrier', 'smooth_layer_thickness', 'boundary_smoothing']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data
                for row in simulation_data:
                    if 'status' not in row:
                        row['status'] = 'completed'  # Default for existing records
                    writer.writerow(row)
        except Exception as e:
            if verbose:
                print(f"Error writing CSV file: {e}")
            raise
        
        # Print summary statistics only if verbose
        if verbose:
            unique_levels = set([row['level'] for row in simulation_data])
            unique_control_points = set([row['control_points'] for row in simulation_data])
            numeric_control_points = sorted([int(cp) for cp in unique_control_points if cp != 'full'])
            has_full = 'full' in unique_control_points
            total_levels = len(unique_levels)
            total_simulations = len(simulation_data)
            completed_simulations = len([row for row in simulation_data if row.get('status') == 'completed'])
            incomplete_simulations = len([row for row in simulation_data if row.get('status') == 'incomplete'])
            
            print(f"\nExtracted data saved to {output_csv_path}")
            print(f"Total optimization levels: {total_levels}")
            
            # Build control point configurations string
            config_parts = []
            if numeric_control_points:
                config_parts.append(f"{numeric_control_points} control points")
            if has_full:
                config_parts.append("full vertices")
            config_str = " + ".join(config_parts)
            print(f"Control point configurations: {config_str}")
            
            print(f"Total forward simulations: {total_simulations}")
            print(f"Completed simulations: {completed_simulations}")
            if incomplete_simulations > 0:
                print(f"Incomplete simulations: {incomplete_simulations}")
            
            # Find the highest iteration reached for each level
            highest_iterations = {}
            for row in simulation_data:
                level = row['level']
                iteration = row['iteration']
                if iteration != 'pre_opt' and isinstance(iteration, int):
                    if level not in highest_iterations or iteration > highest_iterations[level]:
                        highest_iterations[level] = iteration
            
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
                saved_iterations = [k for k in iterations.keys() if k != 'pre_opt' and isinstance(k, int)]
                
                # Count completed vs incomplete simulations at this level
                level_data = [row for row in simulation_data if row['level'] == level]
                completed_at_level = len([row for row in level_data if row.get('status') == 'completed'])
                incomplete_at_level = len([row for row in level_data if row.get('status') == 'incomplete'])
                
                status_str = ""
                if incomplete_at_level > 0:
                    status_str = f" ({incomplete_at_level} incomplete)"
                
                print(f"Level {level} ({cp} control points):" if cp != 'full' else f"Level {level} (full vertices):")
                print(f"  Total simulations: {total_sims_in_level}{status_str}")
                print(f"  Saved iterations: {len(saved_iterations)}")
                if level in highest_iterations:
                    print(f"  Highest iteration reached: {highest_iterations[level]}")
                
                # Show simulations per iteration
                for iteration in sorted(iterations.keys(), key=lambda x: -1 if x == 'pre_opt' else (float('inf') if not isinstance(x, int) else x)):
                    count = iterations[iteration]
                    level_iter_data = [row for row in level_data if row['iteration'] == iteration]
                    completed_iter = len([row for row in level_iter_data if row.get('status') == 'completed'])
                    incomplete_iter = len([row for row in level_iter_data if row.get('status') == 'incomplete'])
                    
                    iter_status_str = ""
                    if incomplete_iter > 0:
                        iter_status_str = f" ({incomplete_iter} incomplete)"
                    
                    if iteration == 'pre_opt':
                        print(f"  Pre-optimization: {count} simulations{iter_status_str}")
                    else:
                        print(f"  Iteration {iteration}: {count} simulations{iter_status_str}")
            
            # Show computational cost per iteration (only for completed simulations)
            print("\nComputational cost analysis (completed simulations only):")
            for level in sorted(level_stats.keys()):
                cp = level_stats[level]['control_points']
                level_data = [row for row in simulation_data if row['level'] == level and row.get('status') == 'completed']
                
                if not level_data:  # Skip if no completed simulations
                    continue
                
                iteration_costs = {}
                for row in level_data:
                    iter_key = row['iteration']
                    if iter_key not in iteration_costs:
                        iteration_costs[iter_key] = {'count': 0, 'total_time': 0}
                    iteration_costs[iter_key]['count'] += 1
                    if row['simulation_time'] is not None:
                        iteration_costs[iter_key]['total_time'] += row['simulation_time']
                
                print(f"Level {level} ({cp} control points):" if cp != 'full' else f"Level {level} (full vertices):")
                for iteration in sorted(iteration_costs.keys(), key=lambda x: -1 if x == 'pre_opt' else (float('inf') if not isinstance(x, int) else x)):
                    if iteration != 'pre_opt' and isinstance(iteration, int):
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