#!/usr/bin/env python3
"""
Test script for the grid simulation progress bar.
This script runs a mini grid search to test the progress bar functionality.
"""

import sys
import os
import time
import grid_runner

def main():
    """Run a mini grid test to verify progress bar improvements."""
    print("Testing progress bar with mini grid...")
    
    # Create a small results directory for the test
    test_results_dir = os.path.join(os.getcwd(), "grid_test_results")
    os.makedirs(test_results_dir, exist_ok=True)
    
    # Use the mini_grid.json file for testing
    grid_path = os.path.join(os.getcwd(), "mini_grid.json")
    config_path = os.path.join(os.getcwd(), "config_a.json")
    
    # Run the grid search with the test parameters
    grid_runner.run_grid_search(
        config_path,
        grid_path,
        test_results_dir,
        parallel=True,
        processes=2,
        grid_parallel=True,
        grid_processes=2
    )
    
    print("Progress bar test completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())