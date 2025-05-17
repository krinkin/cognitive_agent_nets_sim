#!/bin/bash
# Docker runner script for the Cognitive Agent Network simulation
# Uses environment variables from .env file for consistency

# Source environment variables if .env exists
if [ -f .env ]; then
    source .env
else
    echo "Warning: .env file not found, using default settings"
    # Default settings
    DOCKER_IMAGE=can_poc
    HOST_CODE_DIR=.
    CONTAINER_CODE_DIR=/app
    HOST_RESULTS_DIR=./results
    CONTAINER_RESULTS_DIR=/app/logs
    # Resource limits: 20 CPUs and 32GB memory
    DOCKER_RUN_OPTS="--rm -v ${HOST_CODE_DIR}:${CONTAINER_CODE_DIR} -e LOGDIR=${CONTAINER_RESULTS_DIR} --cpus=20 --memory=32g --memory-swap=33g"
fi

# Print usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [build|test|run|grid <file>|mini-grid|fast-grid|custom-grid <file>|visualize]"
    echo ""
    echo "Commands:"
    echo "  build               - Build the Docker image"
    echo "  test                - Run the test suite"
    echo "  run                 - Run a regular simulation with progress bar"
    echo "  grid <file>         - Run grid search with specified grid file"
    echo "  mini-grid           - Run small grid for quick testing"
    echo "  fast-grid           - Run optimized grid search with max parallelism"
    echo "  custom-grid <file>  - Run grid search with specified grid file"
    echo "  visualize           - Run visualization tool to generate plots from results.csv"
    echo ""
    echo "Examples:"
    echo "  $0 build            # Build the Docker image"
    echo "  $0 test             # Run all tests"
    echo "  $0 run              # Run a regular simulation"
    echo "  $0 grid grid_params.json  # Run grid search with specified grid file"
    echo "  $0 custom-grid my_grid.json  # Run grid search with custom parameters"
    echo "  $0 visualize        # Visualize results from results.csv"
    echo "  $0 visualize --input results2.csv --output custom_plots  # Visualize with custom paths"
    exit 1
fi

# Process command
CMD=$1
shift # Remove the command argument

case $CMD in
    build)
        echo "Building Docker image: ${DOCKER_IMAGE}"
        docker build -t ${DOCKER_IMAGE} .
        ;;
    test)
        echo "Running tests in Docker"
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} test $@
        ;;
    run)
        echo "Running regular simulation"
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} regular $@
        ;;
    grid)
        if [ $# -eq 0 ]; then
            echo "Error: grid requires a grid file parameter"
            echo "Usage: $0 grid <grid-file.json>"
            exit 1
        fi

        GRID_FILE=$1
        shift # Remove grid file argument

        # Check if file exists
        if [ ! -f "${GRID_FILE}" ]; then
            echo "Error: Grid file not found: ${GRID_FILE}"
            exit 1
        fi

        # Get absolute path for the grid file
        GRID_FILE_ABS=$(realpath ${GRID_FILE})
        CONTAINER_GRID_PATH="${CONTAINER_CODE_DIR}/$(basename ${GRID_FILE_ABS})"

        echo "Running grid search with grid file: ${GRID_FILE}"
        echo "Container grid path: ${CONTAINER_GRID_PATH}"

        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} grid-file ${CONTAINER_GRID_PATH} $@
        ;;
    mini-grid)
        echo "Running mini grid search"
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} mini-grid $@
        ;;
    fast-grid)
        echo "Running fast grid search with max parallelism"
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} fast-grid $@
        ;;
    custom-grid)
        if [ $# -eq 0 ]; then
            echo "Error: custom-grid requires a grid file parameter"
            echo "Usage: $0 custom-grid <grid-file.json>"
            exit 1
        fi
        
        GRID_FILE=$1
        shift # Remove grid file argument
        
        # Check if file exists
        if [ ! -f "${GRID_FILE}" ]; then
            echo "Error: Grid file not found: ${GRID_FILE}"
            exit 1
        fi
        
        # Get absolute path for the grid file
        GRID_FILE_ABS=$(realpath ${GRID_FILE})
        CONTAINER_GRID_PATH="${CONTAINER_CODE_DIR}/$(basename ${GRID_FILE_ABS})"
        
        echo "Running grid search with custom grid file: ${GRID_FILE}"
        echo "Container grid path: ${CONTAINER_GRID_PATH}"
        
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} grid-file ${CONTAINER_GRID_PATH} $@
        ;;
    visualize)
        echo "Running visualization tool in Docker"
        
        # Create plots directory if it doesn't exist
        mkdir -p plots
        
        # Handle command-line arguments for visualization
        VISUALIZE_ARGS=""
        
        # Parse input file argument
        if [[ "$1" == "--input" || "$1" == "-i" ]] && [ $# -ge 2 ]; then
            INPUT_FILE=$2
            shift 2
            
            # Check if file exists
            if [ ! -f "${INPUT_FILE}" ]; then
                echo "Error: Input file not found: ${INPUT_FILE}"
                exit 1
            fi
            
            # Get absolute path for the input file
            INPUT_FILE_ABS=$(realpath ${INPUT_FILE})
            # Handle path that might be inside a subdirectory
            if [[ "${INPUT_FILE}" == *"/"* ]]; then
                # Get the directory part of the path
                DIR_PART=$(dirname "${INPUT_FILE}")
                # Create the directory in the container if needed
                CONTAINER_DIR="${CONTAINER_CODE_DIR}/${DIR_PART}"
                # Full path to the input file in the container
                CONTAINER_INPUT_PATH="${CONTAINER_CODE_DIR}/${INPUT_FILE}"
                VISUALIZE_ARGS="${VISUALIZE_ARGS} --input ${CONTAINER_INPUT_PATH}"
            else
                # Simple case, file in root directory
                CONTAINER_INPUT_PATH="${CONTAINER_CODE_DIR}/$(basename ${INPUT_FILE_ABS})"
                VISUALIZE_ARGS="${VISUALIZE_ARGS} --input ${CONTAINER_INPUT_PATH}"
            fi
        fi
        
        # Parse output directory argument
        if [[ "$1" == "--output" || "$1" == "-o" ]] && [ $# -ge 2 ]; then
            OUTPUT_DIR=$2
            shift 2
            
            # Create output directory if it doesn't exist
            mkdir -p "${OUTPUT_DIR}"
            
            # Get absolute path for the output directory
            OUTPUT_DIR_ABS=$(realpath ${OUTPUT_DIR})
            CONTAINER_OUTPUT_PATH="${CONTAINER_CODE_DIR}/$(basename ${OUTPUT_DIR_ABS})"
            VISUALIZE_ARGS="${VISUALIZE_ARGS} --output ${CONTAINER_OUTPUT_PATH}"
        fi
        
        echo "Running visualization with arguments: ${VISUALIZE_ARGS}"
        
        # Run the visualization tool in Docker
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} visualize ${VISUALIZE_ARGS} $@
        ;;
    *)
        echo "Unknown command: $CMD"
        echo "Run '$0' without arguments to see available commands"
        exit 1
        ;;
esac