#!/usr/bin/env python3
"""
Submit polyfem grid search jobs to SLURM.
"""

import yaml
import json
import os
import subprocess
import argparse
import shutil
from pathlib import Path

def load_job_list(job_list_path):
    """Load the job list from YAML file."""
    with open(job_list_path, 'r') as f:
        return yaml.safe_load(f)

def create_job_directory(job_id, base_data_dir, results_dir):
    """Create job directory and copy necessary files."""
    job_dir = results_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"  Creating job directory: {job_dir}")
    
    # Files to copy from base data directory
    files_to_copy = [
        "state_MR_Conradlow.json",
        "*.obj", "*.stl", "*.msh", "*.txt", "*.py"
    ]
    
    # Copy files using shell globbing for wildcards
    for pattern in files_to_copy:
        source_pattern = base_data_dir / pattern
        try:
            # Use shell command for wildcard expansion
            if '*' in pattern:
                cmd = f"cp {base_data_dir}/{pattern} {job_dir}/ 2>/dev/null || true"
                subprocess.run(cmd, shell=True, check=False)
            else:
                source_file = base_data_dir / pattern
                if source_file.exists():
                    shutil.copy2(source_file, job_dir)
        except Exception as e:
            print(f"    Warning: Could not copy {pattern}: {e}")
    
    return job_dir

def fill_slurm_template(template_path, job_info, build_dirs, slurm_params):
    """Fill in the SLURM template with job-specific values."""
    with open(template_path, 'r') as f:
        template_content = f.read()
    
    # Fill in all the placeholders
    filled_content = template_content.format(
        JOB_ID=job_info['job_id'],
        CONFIG_FILE=job_info['config_file'],
        WALLTIME=slurm_params['WALLTIME'],
        NODES=slurm_params['NODES'],
        CPUS=slurm_params['CPUS'],
        MEMORY=slurm_params['MEMORY'],
        POLYFEM_BUILD_DIR=build_dirs['polyfem'],
        MMG_BUILD_DIR=build_dirs['mmg'],
        FTETWILD_BUILD_DIR=build_dirs['ftetwild']
    )
    
    return filled_content

def submit_job(job_script_path, dry_run=False):
    """Submit job to SLURM."""
    if dry_run:
        print(f"    [DRY RUN] Would submit: sbatch {job_script_path}")
        return True
    else:
        try:
            # Python 3.6 compatible version
            result = subprocess.run(['sbatch', str(job_script_path)], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, check=True)
            print(f"    Submitted: {result.stdout.strip()}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"    ERROR submitting job: {e}")
            print(f"    STDOUT: {e.stdout}")
            print(f"    STDERR: {e.stderr}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Submit polyfem grid search jobs')
    parser.add_argument('--polyfem-build-dir', required=True,
                       help='Path to polyfem build directory')
    parser.add_argument('--mmg-build-dir', required=True,
                       help='Path to mmg build directory')
    parser.add_argument('--ftetwild-build-dir', required=True,
                       help='Path to ftetwild build directory')
    parser.add_argument('--memory', default='64G',
                       help='Memory per job (default: 64G)')
    parser.add_argument('--cpus', default='16',
                       help='CPUs per job (default: 16)')
    parser.add_argument('--walltime', default='06:00:00',
                       help='Wall time per job (default: 4 hours)')
    parser.add_argument('--max-jobs', type=int, default=None,
                       help='Maximum number of jobs to submit (for testing)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually submitting')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip jobs that already have result directories')
    
    args = parser.parse_args()
    
    # Project paths
    project_root = Path(__file__).parent.parent
    job_list_path = project_root / "configs" / "generated" / "job_list.yaml"
    template_path = project_root / "job_templates" / "slurm_template.sh"
    results_dir = project_root / "results"
    base_data_dir = project_root / "cervix_inflation_EX_V2_original"
    
    # Check required files exist
    required_files = [job_list_path, template_path, base_data_dir]
    for req_file in required_files:
        if not req_file.exists():
            print(f"ERROR: Required file/directory not found: {req_file}")
            return 1
    
    # Check build directories exist
    build_dirs = {
        'polyfem': Path(args.polyfem_build_dir),
        'mmg': Path(args.mmg_build_dir),
        'ftetwild': Path(args.ftetwild_build_dir)
    }
    
    for name, build_dir in build_dirs.items():
        if not build_dir.exists():
            print(f"ERROR: {name} build directory not found: {build_dir}")
            return 1
    
    # SLURM parameters
    slurm_params = {
        'MEMORY': args.memory,
        'CPUS': args.cpus,
        'WALLTIME': args.walltime,
        'NODES': '1'
    }
    
    # Load job list
    print(f"Loading job list from: {job_list_path}")
    job_data = load_job_list(job_list_path)
    jobs = job_data['jobs']
    
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
        print(f"Limiting to first {args.max_jobs} jobs")
    
    print(f"Found {len(jobs)} jobs to process")
    print(f"Memory per job: {args.memory}")
    print(f"CPUs per job: {args.cpus}")
    print(f"Wall time per job: {args.walltime}")
    
    if args.dry_run:
        print("\n*** DRY RUN MODE - No jobs will actually be submitted ***")
    
    # Create results directory
    results_dir.mkdir(exist_ok=True)
    
    # Process each job
    submitted = 0
    skipped = 0
    failed = 0
    
    for i, job_info in enumerate(jobs, 1):
        job_id = job_info['job_id']
        print(f"\n[{i:2d}/{len(jobs)}] Processing job: {job_id}")
        
        # Check if job already exists
        job_dir = results_dir / job_id
        if args.skip_existing and job_dir.exists():
            print(f"  Skipping: directory already exists")
            skipped += 1
            continue
        
        # Create job directory and copy files
        try:
            job_dir = create_job_directory(job_id, base_data_dir, results_dir)
        except Exception as e:
            print(f"  ERROR creating job directory: {e}")
            failed += 1
            continue
        
        # Fill in SLURM template
        try:
            slurm_content = fill_slurm_template(template_path, job_info, build_dirs, slurm_params)
        except Exception as e:
            print(f"  ERROR filling template: {e}")
            failed += 1
            continue
        
        # Write job script
        job_script_path = job_dir / "slurm_job.sh"
        try:
            with open(job_script_path, 'w') as f:
                f.write(slurm_content)
            os.chmod(job_script_path, 0o755)  # Make executable
        except Exception as e:
            print(f"  ERROR writing job script: {e}")
            failed += 1
            continue
        
        # Submit job
        if submit_job(job_script_path, args.dry_run):
            submitted += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"  Jobs submitted: {submitted}")
    print(f"  Jobs skipped:   {skipped}")
    print(f"  Jobs failed:    {failed}")
    print(f"  Total jobs:     {len(jobs)}")
    
    if args.dry_run:
        print(f"\n*** This was a DRY RUN - no jobs were actually submitted ***")
        print(f"Remove --dry-run flag to actually submit jobs")
    elif submitted > 0:
        print(f"\nJobs submitted to SLURM queue. Monitor with:")
        print(f"  squeue -u $USER")
        print(f"  watch squeue -u $USER")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit(main())