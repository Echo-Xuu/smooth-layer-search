#!/bin/bash
#SBATCH --job-name=polyfem_{JOB_ID}
#SBATCH --output=results/{JOB_ID}/slurm_%j.out
#SBATCH --error=results/{JOB_ID}/slurm_%j.err
#SBATCH --time={WALLTIME}
#SBATCH --nodes={NODES}
#SBATCH --cpus-per-task={CPUS}
#SBATCH --mem={MEMORY}
#SBATCH --account=myers

# Job information
echo "Job ID: {JOB_ID}"
echo "SLURM Job ID: $SLURM_JOB_ID"
echo "Config file: {CONFIG_FILE}"
echo "Started at: $(date)"
echo "Running on node: $(hostname)"

# Create results directory
mkdir -p results/{JOB_ID}

# Load modules for Ginsburg
module load python37
module load gcc/13.0.1
module load cmake/3.27.3 

# Ensure user-installed Python packages are available
export PATH=$HOME/.local/bin:$PATH
export PYTHONPATH=$HOME/.local/lib/python3.7/site-packages:$PYTHONPATH

# Load other modules as needed for your builds
# module load gcc
# module load cmake
# module load eigen

# Set environment variables
export OMP_NUM_THREADS={CPUS}
export POLYFEM_BUILD_DIR={POLYFEM_BUILD_DIR}
export MMG_BUILD_DIR={MMG_BUILD_DIR}
export FTETWILD_BUILD_DIR={FTETWILD_BUILD_DIR}

# Change to job directory
cd results/{JOB_ID}

# Copy necessary files
cp ../../configs/generated/{CONFIG_FILE} ./run_MR_Conradlow.json
cp ../../cervix_inflation_EX_V2_original/state_MR_Conradlow.json ./
cp ../../cervix_inflation_EX_V2_original/*.obj ./
cp ../../cervix_inflation_EX_V2_original/*.stl ./
cp ../../cervix_inflation_EX_V2_original/*.msh ./
cp ../../cervix_inflation_EX_V2_original/*.txt ./
cp ../../cervix_inflation_EX_V2_original/*.py ./ 2>/dev/null || true

# Run the simulation
echo "Starting polyfem simulation..."
python ../../cascaded_optimization.py \
    --opt_example cervix_inflation_EX_V2_original \
    --polyfem_build_dir $POLYFEM_BUILD_DIR \
    --mmg_build_dir $MMG_BUILD_DIR \
    --ftetwild_build_dir $FTETWILD_BUILD_DIR \
    --opt_path $(pwd) \
    --opt_algorithm L-BFGS

# Check if simulation completed successfully
if [ $? -eq 0 ]; then
    echo "Simulation completed successfully at: $(date)"
    echo "SUCCESS" > status.txt
else
    echo "Simulation failed at: $(date)"
    echo "FAILED" > status.txt
    exit 1
fi

# Compress large output files (optional)
# gzip *.vtu *.vtm 2>/dev/null || true

echo "Job completed at: $(date)"