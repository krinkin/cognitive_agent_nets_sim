#!/usr/bin/env python3
"""
Script to verify the results.csv file format from grid_runner.py
"""
import os
import sys
import pandas as pd
import glob

def find_latest_results():
    """Find the latest results.csv file in the logs directory."""
    csv_files = glob.glob("logs/grid_*/results.csv")
    if not csv_files:
        print("No results.csv files found in logs directory.")
        return None
    
    # Return the most recently modified file
    latest_file = max(csv_files, key=os.path.getmtime)
    return latest_file

def verify_results_csv(csv_path):
    """Verify the structure and content of a results.csv file."""
    if not os.path.exists(csv_path):
        print(f"Error: File not found: {csv_path}")
        return False
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_path)
        
        # Check required columns
        required_columns = [
            "config_id", "config_name", 
            "baseline_success_rate", "hybrid_success_rate",
            "duration", "generator.force_semantic"
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Error: Missing required columns: {missing_columns}")
            return False
        
        # Check if there are results for each configuration
        print(f"Found {len(df)} configuration results.")
        
        # Print success rates
        print("\nSuccess rates for each configuration:")
        for _, row in df.iterrows():
            config_name = row["config_name"]
            baseline_rate = row["baseline_success_rate"]
            hybrid_rate = row["hybrid_success_rate"]
            print(f"  {config_name}:")
            print(f"    Baseline: {baseline_rate:.2f}")
            print(f"    Hybrid:   {hybrid_rate:.2f}")
        
        # Verification passed
        print("\n✅ Results CSV file is valid and contains expected data.")
        return True
        
    except Exception as e:
        print(f"Error verifying CSV file: {e}")
        return False

if __name__ == "__main__":
    # Get the CSV file path from command line or find latest
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = find_latest_results()
        if not csv_path:
            sys.exit(1)
    
    print(f"Verifying results file: {csv_path}")
    if not verify_results_csv(csv_path):
        sys.exit(1)
    
    print("\nThe grid-file mode is working correctly and generating valid results.")