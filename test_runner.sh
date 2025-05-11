#!/bin/bash
# Test verification script for Docker environment
# Runs all tests and verifies grid-file mode

# Load environment variables if available
if [ -f .env ]; then
    source .env
else
    echo "Warning: .env file not found, using default settings"
    DOCKER_IMAGE=can_poc
    DOCKER_RUN_OPTS="--rm -v $(pwd):/app -e LOGDIR=/app/logs"
fi

echo "============================================"
echo "    TESTING COGNITIVE AGENT NETWORK SIMULATION"
echo "============================================"
echo ""

# Check if Docker image exists
if ! docker image inspect $DOCKER_IMAGE >/dev/null 2>&1; then
    echo "Docker image $DOCKER_IMAGE not found. Building now..."
    docker build -t $DOCKER_IMAGE .
fi

echo "Running all tests..."
echo "--------------------------------------------"
docker run $DOCKER_RUN_OPTS $DOCKER_IMAGE test

if [ $? -ne 0 ]; then
    echo "❌ Test suite failed! See errors above."
    exit 1
fi

echo ""
echo "Testing grid-file mode specifically..."
echo "--------------------------------------------"

# Create a minimal test grid file for verification
TEST_GRID_FILE="test_grid_verification.json"
cat > $TEST_GRID_FILE << EOF
{
  "duration": [15],
  "sessions": [1],
  "generator.force_semantic": [true]
}
EOF

echo "Created test grid file: $TEST_GRID_FILE"

# Run a minimal grid search with the test grid
echo "Running minimal grid search with test grid file..."
docker run $DOCKER_RUN_OPTS $DOCKER_IMAGE grid-file /app/$TEST_GRID_FILE --no-grid-parallel

if [ $? -ne 0 ]; then
    echo "❌ Grid file test failed! See errors above."
    rm $TEST_GRID_FILE
    exit 1
fi

# Clean up test grid file
rm $TEST_GRID_FILE

echo ""
echo "✅ All tests passed successfully!"
echo "The grid-file mode is working as expected."
echo ""
echo "You can now use custom grid files with:"
echo "  ./docker-run.sh custom-grid my_grid.json"
echo ""