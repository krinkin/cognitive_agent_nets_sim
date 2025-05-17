#!/bin/bash
# Main entry script for running different simulation modes

# Print usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [test|regular|grid|grid-file <file>|fast-grid|mini-grid|visualize]"
    echo ""
    echo "Modes:"
    echo "  test         - Run test suite"
    echo "  regular      - Run single simulation with progress bar"
    echo "  grid         - Run grid search using grid_params.json"
    echo "  grid-file <file> - Run grid search using specified grid file"
    echo "  fast-grid    - Run grid search with max parallelism using focused_grid.json"
    echo "  mini-grid    - Run small grid for quick testing"
    echo "  visualize    - Run visualization tool to generate plots from results.csv"
    echo ""
    echo "Environment variables:"
    echo "  LOGDIR       - Directory to save logs (default: /app/logs)"
    echo ""
    echo "Docker examples:"
    echo "  docker run --rm can_poc test"
    echo "  docker run --rm can_poc grid"
    echo "  docker run --rm -v \$(pwd)/results:/app/logs can_poc mini-grid"
    echo "  docker run --rm -v \$(pwd):/app -e LOGDIR=/app/results can_poc grid-file /app/my_grid.json"
    echo "  docker run --rm -v \$(pwd):/app can_poc visualize --input /app/results.csv --output /app/plots"
    exit 1
fi

MODE=$1
shift  # Remove the mode argument, leaving any additional args

# Handle grid-file mode which requires an additional argument
GRID_FILE=""
if [ "$MODE" = "grid-file" ]; then
    if [ $# -eq 0 ]; then
        echo "Error: grid-file mode requires a file path"
        echo "Usage: $0 grid-file <path-to-grid-file>"
        exit 1
    fi
    GRID_FILE="$1"
    shift  # Remove the grid file argument from remaining args
fi

case $MODE in
    test)
        python -m pytest -v
        ;;
    regular)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python runner.py --config config_a.json --logdir "$LOGDIR" --parallel "$@"
        ;;
    grid-file)
        # Use custom grid file specified by user
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        echo "Running grid search with custom grid file: $GRID_FILE"
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid "$GRID_FILE" --parallel --visualize "$@"
        ;;
    grid)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid grid_params.json --parallel --visualize "$@"
        ;;
    focused-grid)
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid focused_grid.json --parallel --visualize "$@"
        ;;
    fast-grid)
        # Run grid with max parallelism at both levels
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        CPU_COUNT=$(nproc)
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid focused_grid.json --parallel --grid-processes $CPU_COUNT --visualize "$@"
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
        python grid_runner.py --config config_a.json --logdir "$LOGDIR" --grid mini_grid.json --parallel --processes $SIM_PROCESSES --grid-processes $GRID_PROCESSES --visualize "$@"
        ;;
    visualize)
        # Run the visualization tool
        echo "Running visualization tool..."
        
        # Default input and output paths
        INPUT_FILE="/app/results.csv"
        OUTPUT_DIR="/app/plots"
        
        # Parse command line arguments
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --input|-i)
                    INPUT_FILE="$2"
                    shift 2
                    ;;
                --output|-o)
                    OUTPUT_DIR="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option for visualize mode: $1"
                    echo "Usage: $0 visualize [--input INPUT_CSV] [--output OUTPUT_DIR]"
                    exit 1
                    ;;
            esac
        done
        
        # Ensure output directory exists
        mkdir -p "$OUTPUT_DIR"
        
        echo "Input file: $INPUT_FILE"
        echo "Output directory: $OUTPUT_DIR"
        
        # Run the visualization script
        python visualize_results.py --input "$INPUT_FILE" --output "$OUTPUT_DIR"
        ;;
    *)
        # Default to regular mode
        LOGDIR=${LOGDIR:-/app/logs}  # Use LOGDIR env var if set
        python runner.py --config config_a.json --logdir "$LOGDIR" --parallel "$@"
        ;;
esac