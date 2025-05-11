# grid_runner.py - Grid parameter search for simulation
import argparse
import copy
import json
import os
import datetime
import itertools
from tqdm import tqdm
import pandas as pd
import multiprocessing
from multiprocessing import Pool
import runner

def create_grid_configs(base_config, param_grid):
    """
    Generate a grid of configurations by varying parameters.
    
    Args:
        base_config: The base configuration dictionary
        param_grid: A dictionary where keys are parameter paths (dot-separated) 
                    and values are lists of values to try
    
    Returns:
        A list of (config_dict, config_name) tuples
    """
    # Convert dot notation to nested dictionary paths
    param_paths = []
    param_values = []
    for key, values in param_grid.items():
        param_paths.append(key.split('.'))
        param_values.append(values)
    
    # param_paths and param_values are already lists
    
    configs = []
    
    # For each combination of parameter values
    for combination in itertools.product(*param_values):
        # Start with a deep copy of the base config
        config = copy.deepcopy(base_config)
        config_name_parts = []
        
        # Apply each parameter value to the config
        for i, path in enumerate(param_paths):
            value = combination[i]
            
            # Format value for config name
            if value is None:
                display_value = "null"
            else:
                display_value = value
            
            # Navigate to the right level in the config
            current = config
            for j, part in enumerate(path[:-1]):  # All but the last part
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value
            current[path[-1]] = value
            
            # Add to config name
            config_name_parts.append(f"{'.'.join(path)}={display_value}")
        
        # Create a short but descriptive name for this config
        config_name = "__".join(config_name_parts)
        
        configs.append((config, config_name))
    
    return configs

def run_single_config(params):
    """Run a single configuration in the grid.

    Args:
        params: Tuple of (config, config_name, config_id, config_dir, parallel, processes)

    Returns:
        Dictionary with results for this configuration
    """
    # When we're in a multiprocessing context, we can't use nested process pools
    # So we force sequential execution in run_simulations
    config, config_name, config_id, config_dir, parallel, processes, param_grid = params

    # When running as part of grid search, always use sequential mode for sub-simulations
    # to avoid nested process pools
    parallel = False
    
    print(f"\nRunning configuration {config_id}: {config_name}")
    
    # Save this specific configuration
    os.makedirs(config_dir, exist_ok=True)
    
    with open(os.path.join(config_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    
    # Run the simulation with this configuration
    baseline_paths, hybrid_paths = runner.run_simulations(
        config, 
        config_dir, 
        parallel=parallel, 
        processes=processes
    )
    
    # Analyze results
    Sa, Ta, Ba = runner.analyse(baseline_paths)
    Sb, Tb, Bb = runner.analyse(hybrid_paths)
    
    # Record the results
    result = {
        "config_id": config_id,
        "config_name": config_name,
        "baseline_success_rate": Sa,
        "hybrid_success_rate": Sb,
        "baseline_time": Ta,
        "hybrid_time": Tb,
        "baseline_bytes": Ba,
        "hybrid_bytes": Bb
    }
    
    # Add all the parameter values to the result
    for param_path in param_grid.keys():
        # Extract the current value for this parameter from the config
        parts = param_path.split('.')
        current = config
        for part in parts:
            if part in current:
                current = current[part]
            else:
                current = None
                break
        
        # Store the value, handling special cases
        if current is None:
            result[param_path] = "null"
        else:
            result[param_path] = current
    
    # Save individual result file for this configuration
    with open(os.path.join(config_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)
    
    return result

def load_grid_file(file_path):
    """Load a grid parameter file.

    Args:
        file_path: Path to the grid parameter file

    Returns:
        Dictionary with parameter grid specification
    """
    with open(file_path, 'r') as f:
        return json.load(f)

def run_grid_search(base_config_path, param_grid, logdir, parallel=False, processes=None, grid_parallel=True, grid_processes=None):
    """Run simulations with all combinations of parameters in the grid.

    Args:
        base_config_path: Path to base configuration file
        param_grid: Dictionary of parameters to vary or path to grid parameter file
        logdir: Directory to store logs
        parallel: Whether to run simulations in parallel
        processes: Number of processes for simulation parallelism
        grid_parallel: Whether to run grid configurations in parallel
        grid_processes: Number of processes for grid-level parallelism
    """
    # Handle case where param_grid is a file path instead of a dictionary
    if isinstance(param_grid, str):
        param_grid = load_grid_file(param_grid)

    # Load the base configuration
    with open(base_config_path) as f:
        base_config = json.load(f)
    
    # Create all parameter combinations
    print(f"Generating configuration grid...")
    configs = create_grid_configs(base_config, param_grid)
    print(f"Created {len(configs)} configurations to test")
    
    # Determine process count for grid-level parallelism
    if grid_processes is None:
        # By default, use half of available CPUs for grid-level and half for simulation-level
        cpu_count = multiprocessing.cpu_count()
        grid_processes = max(1, cpu_count // 2)
        if processes is None and parallel:
            # Use the other half for simulation-level parallelism
            processes = max(1, cpu_count // 2)
    
    # Create a directory for this grid search run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    grid_dir = os.path.join(logdir, f"grid_{timestamp}")
    os.makedirs(grid_dir, exist_ok=True)
    
    # Save the parameter grid for reference
    with open(os.path.join(grid_dir, "grid_params.json"), "w") as f:
        json.dump(param_grid, f, indent=2)
    
    # Prepare parameters for parallel execution
    config_params = []
    for i, (config, config_name) in enumerate(configs):
        config_dir = os.path.join(grid_dir, f"config_{i:03d}")
        config_params.append((
            config, 
            config_name, 
            i, 
            config_dir, 
            parallel, 
            processes,
            param_grid
        ))
    
    results = []
    
    # Run configurations - either in parallel or sequentially
    if grid_parallel and len(configs) > 1:
        print(f"Running grid search in parallel with {grid_processes} processes")
        
        # Run configurations in parallel
        with Pool(processes=grid_processes, initializer=runner.init_worker) as pool:
            configs_iter = pool.imap(run_single_config, config_params)
            
            # Use tqdm to show progress
            for result in tqdm(configs_iter, total=len(configs), desc="Grid", unit="config"):
                results.append(result)
                
                # Save incremental results after each configuration
                df = pd.DataFrame(results)
                df.to_csv(os.path.join(grid_dir, "results.csv"), index=False)
    else:
        # Run configurations sequentially
        print("Running grid search sequentially")
        for params in tqdm(config_params, desc="Configurations", unit="config"):
            result = run_single_config(params)
            results.append(result)
            
            # Save incremental results after each configuration
            df = pd.DataFrame(results)
            df.to_csv(os.path.join(grid_dir, "results.csv"), index=False)
    
    # Final results
    print("\nGrid search complete!")
    print(f"Results saved to: {os.path.join(grid_dir, 'results.csv')}")
    
    return results

def main():
    """Command-line interface for grid search."""
    parser = argparse.ArgumentParser(description="Run grid search over parameter combinations")
    parser.add_argument("--config", required=True, help="Base JSON config file")
    parser.add_argument("--logdir", required=True, help="Directory for logs")
    parser.add_argument("--grid", required=True, help="Grid parameter specification JSON file")
    
    # Simulation-level parallelism
    parser.add_argument("--parallel", action="store_true", help="Run simulations in parallel")
    parser.add_argument("--processes", type=int, default=None, 
                        help="Number of processes for simulation parallelism (default: CPU count / 2)")
    
    # Grid-level parallelism
    parser.add_argument("--no-grid-parallel", action="store_true", help="Disable grid-level parallelism")
    parser.add_argument("--grid-processes", type=int, default=None,
                        help="Number of processes for grid-level parallelism (default: CPU count / 2)")
    
    args = parser.parse_args()
    
    # Load parameter grid
    param_grid = load_grid_file(args.grid)
    
    # Run the grid search
    run_grid_search(
        args.config, 
        param_grid, 
        args.logdir, 
        parallel=args.parallel, 
        processes=args.processes,
        grid_parallel=not args.no_grid_parallel,
        grid_processes=args.grid_processes
    )

if __name__ == "__main__":
    main()