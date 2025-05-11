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
    DOCKER_RUN_OPTS="--rm -v ${HOST_CODE_DIR}:${CONTAINER_CODE_DIR} -e LOGDIR=${CONTAINER_RESULTS_DIR}"
fi

# Print usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [build|test|run|grid|custom-grid <file>]"
    echo ""
    echo "Commands:"
    echo "  build               - Build the Docker image"
    echo "  test                - Run the test suite"
    echo "  run                 - Run a regular simulation with progress bar"
    echo "  grid                - Run full parameter grid search"
    echo "  mini-grid           - Run small grid for quick testing"
    echo "  fast-grid           - Run optimized grid search with max parallelism"
    echo "  custom-grid <file>  - Run grid search with specified grid file"
    echo ""
    echo "Examples:"
    echo "  $0 build            # Build the Docker image"
    echo "  $0 test             # Run all tests"
    echo "  $0 run              # Run a regular simulation"
    echo "  $0 custom-grid my_grid.json  # Run grid search with custom parameters"
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
        echo "Running grid search"
        # Ensure host results directory exists
        mkdir -p ${HOST_RESULTS_DIR}
        docker run ${DOCKER_RUN_OPTS} ${DOCKER_IMAGE} grid $@
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
    *)
        echo "Unknown command: $CMD"
        echo "Run '$0' without arguments to see available commands"
        exit 1
        ;;
esac