#!/bin/bash
# Run grid search with grid_params.json at maximum performance
# This script optimizes CPU allocation for both grid and simulation parallelism

# Create results directory if it doesn't exist
mkdir -p results

# Get available CPU cores
CPU_COUNT=$(nproc)
# Use 2/3 of cores for grid and 1/3 for simulations to prevent oversubscription
GRID_CORES=$(( CPU_COUNT * 2 / 3 ))
SIM_CORES=$(( CPU_COUNT / 3 ))

# Ensure at least 1 core for each level
GRID_CORES=$(( GRID_CORES > 0 ? GRID_CORES : 1 ))
SIM_CORES=$(( SIM_CORES > 0 ? SIM_CORES : 1 ))

echo "Running grid search with maximum performance:"
echo "  - Using $GRID_CORES cores for grid-level parallelism"
echo "  - Using $SIM_CORES cores for simulation-level parallelism"
echo "  - Storing results in ./results"
echo ""

# Run the grid search with maximum performance
docker run --rm \
  -v $(pwd):/app \
  -e LOGDIR=/app/results \
  can_poc \
  grid \
  --parallel \
  --processes $SIM_CORES \
  --grid-processes $GRID_CORES

echo ""
echo "Grid search complete. Results saved in ./results"
echo "To view the results, check the latest grid_* directory in ./results"