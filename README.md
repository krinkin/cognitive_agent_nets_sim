
# Cognitive Agent Network (Hybrid PoC)

Minimal reproducible prototype for the AGI‑2025 paper.

## Docker (Required)

**Important**: This project must be run inside Docker. Direct execution on the host machine is not supported.

### Basic Docker Commands

```bash
# Build Docker image
docker build -t can_poc .

# Run simulation modes:
docker run --rm can_poc                   # Default simulation
docker run --rm can_poc test              # Run tests
docker run --rm can_poc regular           # Standard simulation with progress bar
docker run --rm can_poc mini-grid         # Run small grid search
docker run --rm can_poc grid              # Run full parameter grid search
docker run --rm can_poc fast-grid         # Run optimized grid search with max parallelism
docker run --rm can_poc grid-file /app/my_grid.json  # Custom grid file
```

### Using the Docker Helper Script

For simplified Docker usage, we provide a convenient wrapper script:

```bash
# Build the Docker image
./docker-run.sh build

# Run tests
./docker-run.sh test

# Run a regular simulation
./docker-run.sh run

# Run grid search
./docker-run.sh grid
./docker-run.sh mini-grid
./docker-run.sh fast-grid

# Run with custom grid file
./docker-run.sh custom-grid my_grid.json
```

The script automatically:
- Sources environment variables from `.env`
- Creates required directories
- Manages file paths between host and container
- Handles Docker command complexity

### Directory Mapping

- Host code directory → `/app` in container
- Host results directory → `/app/logs` in container (customizable with `LOGDIR`)

Example with custom result location:
```bash
mkdir -p ./output
docker run --rm -v $(pwd):/app -e LOGDIR=/app/output can_poc mini-grid
```
