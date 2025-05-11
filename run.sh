#!/bin/bash
# Main entry script for running different simulation modes

# Print usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [test|regular|grid|focused-grid|fast-grid|mini-grid]"
    exit 1
fi

MODE=$1
shift  # Remove the mode argument, leaving any additional args

case $MODE in
    test)
        python -m pytest -v
        ;;
    regular)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python runner.py --config config_a.json --logdir "$LOGDIR" --parallel "$@"
        ;;
    grid)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid grid_params.json --parallel "$@"
        ;;
    focused-grid)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid focused_grid.json --parallel "$@"
        ;;
    fast-grid)
        # Run grid with max parallelism at both levels
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        CPU_COUNT=$(nproc)
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid focused_grid.json --parallel --grid-processes $CPU_COUNT "$@"
        ;;
    mini-grid)
        # Run small grid for quick testing with both levels of parallelism
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        # We need to pass explicit grid processes - otherwise both levels will use CPU/2 processes
        # Set up CPU count for grid-level parallelism
        CPU_COUNT=$(nproc)
        GRID_PROCESSES=$(( CPU_COUNT / 2 ))
        SIM_PROCESSES=$(( CPU_COUNT / 2 ))
        echo "Running with grid processes: $GRID_PROCESSES, simulation processes: $SIM_PROCESSES"
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid mini_grid.json --parallel --processes $SIM_PROCESSES --grid-processes $GRID_PROCESSES "$@"
        ;;
    *)
        # Default to regular mode
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python runner.py --config config_a.json --logdir "$LOGDIR" --parallel "$@"
        ;;
esac