# Cognitive Agent Network Simulation

## Overview

This project implements a Cognitive Agent Network simulation for the AGI-2025 paper, designed to explore how multiple intelligent agents can collaborate to solve problems more efficiently than individual agents alone. The simulation examines the dynamics of emergent cognition in multi-agent systems, with a particular focus on comparing algorithmic-only solutions versus hybrid human-AI collaboration.

## Problem Statement

The simulation models a network of agents attempting to collectively generate, validate, and reach consensus on 4-digit codes that must satisfy specific formal and semantic constraints:

### Formal Constraints
1. The first digit must be even
2. The code must contain exactly two repeating digits

### Semantic Constraint
- The code must contain the sequence "07" (representing "NASA_MONTH")

These constraints create a search space where successful solutions require both rule-following and pattern recognition, testing the agents' abilities to coordinate and share information effectively.

## Agent Architecture

The simulation implements a multi-agent system with distinct roles:

### 1. Generator Agent

**Purpose**: Proposes candidate solutions (4-digit codes).

**Key Features**:
- Generates random 4-digit codes based on configuration parameters
- Can be configured to prefer specific digits in generation
- Option to force semantic constraint ("07") in generated codes
- Maintains a buffer of candidate codes to propose
- Can receive focus hints to guide generation toward promising patterns
- Responds to suggestions from human agents

**Configuration Parameters**:
- `preferred_digit`: Optional digit to favor in generation (can be null, "0", "7", etc.)
- `force_semantic`: Boolean determining whether to always include "07" in generated codes
- `buffer_size`: Number of codes to pre-generate
- `focus_influence_probability`: Likelihood of applying focus hints to generation (0.0-1.0)

### 2. Checker Agent

**Purpose**: Validates proposed codes against formal and semantic constraints.

**Key Features**:
- Evaluates codes against both formal and semantic rules
- Provides binary verification (✓/✗) for each code
- Endorses valid codes that pass all constraints
- Works deterministically based on the defined rules

### 3. Strategist Agent

**Purpose**: Manages consensus and coordinates agent activities.

**Key Features**:
- Tracks endorsements for each proposed code
- Confirms consensus when threshold of endorsements is reached
- Periodically sends top candidates to human agent for review
- Implements Shared Focus mechanism to identify promising digit patterns
- Broadcasts focus hints to guide other agents toward successful patterns

**Configuration Parameters**:
- `threshold`: Required number of endorsements for consensus
- `include_human`: Whether to include human agent in the loop
- `human_interval`: How often to send top codes to human (in cycles)
- `top_k`: Number of top codes to send to human
- `focus_hint_interval`: Cycles between sending focus hints
- `focus_hint_top_n_codes`: Number of top codes to analyze for focus hints
- `focus_min_occurrences`: Minimum occurrences of a digit to be considered for a focus hint

### 4. Synthetic Human Agent

**Purpose**: Simulates human input in hybrid mode.

**Key Features**:
- Active for a limited lifetime (configurable in seconds)
- Endorses codes containing the semantic constraint ("07")
- Intelligently generates new code suggestions when none of the top candidates are suitable
- Enhances exploration by injecting human-like insights

**Configuration Parameters**:
- `lifetime`: How long the human agent remains active (in seconds)

## Communication Protocol

Agents communicate through a message-passing system using a predefined protocol:

| Message Type | Format | Description |
|--------------|--------|-------------|
| `PROPOSE` | `PROPOSE {code} {agent}` | Submit a new candidate code |
| `EVAL` | `EVAL {code} {verdict} {agent}` | Evaluation result (⊕/⊖) for a code |
| `ENDORSE` | `ENDORSE {code} {agent}` | Support for a valid code |
| `SCORE` | `SCORE {code} {delta} {agent}` | Human scoring for a code |
| `TOP` | `TOP {codes} {agent}` | List of top candidate codes |
| `FOCUS_HINT` | `FOCUS_HINT {digit} {agent}` | Hint about promising digit pattern |
| `SUGGEST` | `SUGGEST {code} {agent}` | Human suggestion for Generator |
| `CONFIRM` | `CONFIRM {code}` | Final consensus on a solution |

This protocol enables structured communication while maintaining agent independence, allowing each agent to process messages according to its role.

## Simulation Modes

The simulation can be run in two primary modes:

### 1. Baseline Mode

Only algorithmic agents are active (Generator, Checker, Strategist). This represents traditional multi-agent systems without human involvement.

### 2. Hybrid Mode

Includes the SyntheticHuman agent to simulate human-AI collaboration. The human agent introduces domain knowledge (preference for "07") and helps guide the exploration process.

## Shared Focus Mechanism

A key innovation in this simulation is the Shared Focus mechanism, which enables agents to collectively identify and exploit promising patterns:

1. The Strategist analyzes top-endorsed codes to detect frequently occurring digits
2. When a digit appears with sufficient frequency, it's broadcast as a focus hint
3. The Generator uses these hints to bias its code generation toward patterns that have shown promise
4. This creates a feedback loop that accelerates convergence on valid solutions

## Cognitive Resonance Metrics

The system calculates several key metrics to evaluate the performance of the agent network:

| Metric | Symbol | Description |
|--------|--------|-------------|
| Success Rate | S | Fraction of simulation sessions that successfully reached consensus |
| Time to Success | T | Average time (in seconds) required to reach consensus; only calculated for successful sessions |
| Bytes Exchanged | B | Average communication volume (in bytes) across all sessions |
| Progress Rate | P̊ | Inverse of time to success (1/T); higher values indicate faster solution finding |
| Communication Cost Rate | C̊ | Bytes per second during simulation; measures communication efficiency |
| Cognitive Resonance | R_CAN | Primary metric defined as `k * (P̊ / (C̊ + ε))` |

The R_CAN metric uses the following parameters:
- `k` is a scaling coefficient (default: 1024.0)
- `ε` is a small constant (1e-6) to prevent division by zero

R_CAN measures how efficiently the network achieves consensus relative to communication costs. Higher values indicate better cognitive resonance - more efficient problem-solving with less communication overhead.

## Configuration System

The simulation uses a flexible JSON-based configuration system:

### Base Configurations
- `config_a.json`: Shorter sessions with more lenient consensus requirements
- `config_b.json`: Longer sessions with stricter consensus and forced semantic constraints

### Grid Search
The system supports parameter sweeps using grid configuration files:
- `mini_grid.json`: Small grid for quick testing
- `grid_params.json`: Full parameter grid for comprehensive testing
- `focused_grid.json`: Optimized grid with fewer parameters
- `paper_grid.json`: Specific configuration used for the AGI-2025 paper results
  - Uses 50 sessions per configuration
  - Tests durations of 30 and 60 seconds
  - Varies generator preferences and semantic forcing
  - Tests different consensus thresholds and human interaction intervals
  - Examines impact of human lifetime (10 vs 60 seconds)

Key parameters that can be varied include:
- Session count and duration
- Generator parameters (preferred digits, semantic forcing)
- Strategist parameters (threshold, focus hint settings)
- Human agent lifetime

## Visualization and Analysis

The simulation includes visualization tools for analyzing results:

1. **Comparison bar charts**: Baseline vs. Hybrid for key metrics
2. **Scatter plots**: Comparing Progress Rate vs. Communication Cost Rate
3. **ECDF plots**: Empirical Cumulative Distribution Function for metrics
4. **Parameter impact analysis**: How specific parameters affect performance

These visualizations help identify conditions under which hybrid human-AI collaboration outperforms algorithmic-only approaches.

## Implementation Architecture

The codebase is structured as follows:

- **agents.py**: Defines all agent types and their behaviors
- **constraints.py**: Implements the formal and semantic constraints
- **runner.py**: Core simulation engine for running individual sessions
- **grid_runner.py**: Manages parameter grid searches across multiple configurations
- **visualize_results.py**: Creates plots and visualizations of simulation results

All operations are designed to run within Docker for consistent execution environments.

## Cognitive Agent Network Theory

This simulation implementation is based on the Cognitive Agent Network theory outlined in the paper, which proposes that:

1. Multiple agents with complementary capabilities can achieve emergent cognitive properties
2. Human-AI collaboration can significantly enhance problem-solving efficiency
3. Communication efficiency is a critical factor in multi-agent cognition
4. Strategically guided exploration is more effective than undirected search

The R_CAN metric (Cognitive Resonance) quantifies these dynamics by relating progress rate to communication costs, providing a way to compare different agent configurations and collaboration strategies.