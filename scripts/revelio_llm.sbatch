#!/bin/bash
#SBATCH --job-name=revelio-llm
#SBATCH --account=kellogg
#SBATCH --partition=kellogg
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=logs/revelio_llm_%j.log

set -euo pipefail
# Compute nodes do not necessarily provide the login node's system Git.
# The batch package invokes Git while recording prepared-run provenance.
module load git/2.47.0-gcc-12.4.0
# Submit from the repository root; Slurm copies this script to its spool directory.
cd "${KLC_ROOT:-${SLURM_SUBMIT_DIR:?Submit with sbatch from the repository root}}"
.venv-llm/bin/python -c 'import subprocess; subprocess.run(["git", "--version"], check=True)'
if [[ $# -lt 1 ]]; then
    echo "Usage: sbatch scripts/revelio_llm.sbatch PROJECT_DIRECTORY [--sample-size 4] [--model llama3.1:8b]" >&2
    exit 2
fi
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
exec .venv-llm/bin/python scripts/revelio_llm.py run "$@"
