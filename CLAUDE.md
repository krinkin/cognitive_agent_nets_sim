# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project is a minimal reproducible prototype for the AGI-2025 paper, implementing a Cognitive Agent Network simulation with baseline and hybrid modes. It simulates a network of agents trying to generate, validate, and reach consensus on 4-digit codes that satisfy specific formal and semantic constraints.

## Important: Docker-Only Execution

**ALWAYS use Docker for all operations with this codebase.** Never run code directly on the host machine. This includes:
- Running simulations
- Running tests
- Running grid searches
- Building and modifying the code
- Adding new features

### Docker Directory Mapping

Data is shared between the host and Docker container using volume mounting:

```bash
docker run --rm -v $(pwd):/app -e LOGDIR=/app/results can_poc grid-file /app/my_grid.json
```

Environment variables used for configuration:
- `LOGDIR`: Directory where logs and results are stored (default: `/app/logs`)

For consistent file paths, always use the following directory structure:
- `/app`: Root directory of the application inside the container
- `/app/logs` or custom `LOGDIR`: Directory for storing simulation results

## Commands

### Building the Docker Image

```bash
# Build Docker image
docker build -t can_poc .
```

### Preferred Method: Using the Docker Helper Script

**ALWAYS use the docker-run.sh script** when running operations in Docker:

```bash
# Build the Docker image
./docker-run.sh build

# Run tests
./docker-run.sh test

# Run a simulation with progress bars
./docker-run.sh run

# Run grid search (various modes)
./docker-run.sh grid
./docker-run.sh mini-grid
./docker-run.sh fast-grid

# Run with custom grid file
./docker-run.sh custom-grid my_grid.json
```

### Alternative: Direct Docker Commands

Only if necessary, you can use direct Docker commands:

```bash
# Run default simulation
docker run --rm -v $(pwd):/app -e LOGDIR=/app/results --cpus=20 --memory=30g --memory-swap=31g can_poc

# Run with progress visualization
docker run --rm -v $(pwd):/app -e LOGDIR=/app/results --cpus=20 --memory=30g --memory-swap=31g can_poc regular

# Run grid search with custom grid file
docker run --rm -v $(pwd):/app -e LOGDIR=/app/results --cpus=20 --memory=30g --memory-swap=31g can_poc grid-file /app/my_grid.json
```

**Important**: Always include volume mapping (`-v $(pwd):/app`), environment variables (`-e LOGDIR=/app/results`), and resource limits (`--cpus=20 --memory=30g --memory-swap=31g`) for consistent file access and to prevent resource exhaustion.

### Running Tests

```bash
# Run all tests in the container
docker run --rm can_poc test
```

### Testing New Features

All new features must be tested using Docker:

```bash
# Test a specific module
docker run --rm can_poc test tests/test_grid_runner.py

# Test a specific test function
docker run --rm can_poc test tests/test_grid_runner.py::test_custom_grid_file
```

## Architecture

The codebase implements a multi-agent system with the following components:

### Agents

1. **GeneratorAgent**: Proposes random 4-digit codes and endorses them when validated.
   - Can be configured to prefer specific digits or force semantic constraints
   - Maintains a buffer of candidate codes

2. **CheckerAgent**: Validates proposed codes against formal and semantic constraints.
   - Formal constraints: even first digit, exactly two repeating digits
   - Semantic constraint: contains "07" (NASA_MONTH)

3. **StrategistAgent**: Manages consensus and coordinates with other agents.
   - Tracks endorsements for each code
   - Confirms when threshold of endorsements is reached
   - Periodically sends top candidates to human agent

4. **SyntheticHumanAgent**: Simulates human input in hybrid mode.
   - Active for a limited lifetime
   - Endorses codes containing "07"
   - Proposes new codes with "07" when no suitable candidates exist

### Communication Protocol

Agents communicate through message passing with specific formats:
- `PROPOSE {code} {agent}`: Suggest a new code
- `EVAL {code} {verdict} {agent}`: Evaluation result (⊕/⊖)
- `ENDORSE {code} {agent}`: Support for a code
- `SCORE {code} {delta} {agent}`: Human scoring
- `TOP {codes} {agent}`: Top candidates
- `FOCUS_HINT {digit} {agent}`: Hint about promising digit pattern
- `SUGGEST {code} {agent}`: Human suggestion for Generator
- `CONFIRM {code}`: Final consensus

### Simulation Modes

1. **Baseline**: Only algorithmic agents (Generator, Checker, Strategist)
2. **Hybrid**: Includes the SyntheticHuman agent to simulate human collaboration

Results compare success rates, time to success, and communication volume between modes.

## Configuration Options

### Base Configurations

Two sample configurations are provided:
- `config_a.json`: Shorter sessions with lenient consensus (threshold: 1)
- `config_b.json`: Longer sessions with stricter consensus (threshold: 2) and forced semantic constraints

### Grid Configurations

For parameter sweeps, use grid files:
- `mini_grid.json`: Small grid for quick testing
- `grid_params.json`: Full parameter grid
- `focused_grid.json`: Optimized grid with fewer parameters
- `example_grid.json`: Example template for custom grid files

To create a custom grid, copy and modify `example_grid.json`.

### Key Parameters

- `sessions`: Number of simulation runs
- `duration`: Maximum runtime per session (seconds)
- `seed`: Random seed for reproducible simulations (optional, auto-generated if not specified)
- `generator.force_semantic`: Whether to force "07" in generated codes
- `generator.preferred_digit`: Digit to prefer in generation (0, 7, or null)
- `generator.focus_influence_probability`: Probability of using focus hints in code generation
- `strategist.threshold`: Required endorsements for consensus
- `strategist.focus_hint_interval`: How often to send focus hints (cycles)
- `strategist.focus_hint_top_n_codes`: Number of top codes to analyze for focus hints
- `strategist.focus_min_occurrences`: Minimum occurrences of a digit to be considered as a focus hint
- `synthetic_human.lifetime`: How long the human agent remains active (seconds)
