#!/usr/bin/env python3
"""
Simple test script to verify grid-file mode without requiring full test suite.
This can be run directly inside the Docker container.
"""
import os
import json
import tempfile
import grid_runner

def test_load_grid_file():
    """Test that grid files can be loaded successfully."""
    # Create a temporary grid file
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp:
        grid_data = {
            "duration": [15, 30],
            "generator.preferred_digit": [7],
            "synthetic_human.lifetime": [45]
        }
        json.dump(grid_data, temp)
        temp_path = temp.name
    
    try:
        # Test loading the file
        loaded_data = grid_runner.load_grid_file(temp_path)
        
        # Verify the loaded data
        assert loaded_data == grid_data, f"Loaded data {loaded_data} doesn't match original {grid_data}"
        print("✅ Grid file loading test passed!")
        
        # Test using the data for grid configuration
        base_config = {
            "sessions": 2,
            "duration": 10,
            "generator": {
                "preferred_digit": 0,
                "force_semantic": False
            },
            "synthetic_human": {
                "lifetime": 30
            }
        }
        
        configs = grid_runner.create_grid_configs(base_config, loaded_data)
        
        # Should have 2 x 1 x 1 = 2 configurations
        assert len(configs) == 2, f"Expected 2 configurations, got {len(configs)}"
        
        # Check configuration values
        for config, name in configs:
            assert config["duration"] in [15, 30], f"Duration not in expected range: {config['duration']}"
            assert config["generator"]["preferred_digit"] == 7, f"Preferred digit not set correctly: {config['generator']['preferred_digit']}"
            assert config["synthetic_human"]["lifetime"] == 45, f"Human lifetime not set correctly: {config['synthetic_human']['lifetime']}"
        
        print("✅ Grid configuration test passed!")
        return True
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def test_run_with_grid_file():
    """Test that the grid_runner can run with a grid file path."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as config_temp:
        config_data = {
            "sessions": 1,  # Minimal for quick test
            "duration": 5,  # Minimal for quick test
            "generator": {
                "preferred_digit": 0,
                "force_semantic": False
            },
            "strategist": {
                "threshold": 1
            },
            "synthetic_human": {
                "lifetime": 30
            }
        }
        json.dump(config_data, config_temp)
        config_path = config_temp.name
    
    # Create a temporary grid file with minimal parameters
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as grid_temp:
        grid_data = {
            "generator.force_semantic": [True]  # Just one value for quick test
        }
        json.dump(grid_data, grid_temp)
        grid_path = grid_temp.name
    
    try:
        # Create a temporary output directory
        with tempfile.TemporaryDirectory() as output_dir:
            print(f"Running minimal grid search with grid file: {grid_path}")
            
            # Try to run the grid search with the grid file path instead of direct dictionary
            results = grid_runner.run_grid_search(
                config_path,
                grid_path,  # Pass the file path directly
                output_dir,
                parallel=False,
                grid_parallel=False
            )
            
            # Verify the results
            assert len(results) == 1, f"Expected 1 configuration result, got {len(results)}"
            assert "generator.force_semantic" in results[0], "Grid parameter not found in results"
            assert results[0]["generator.force_semantic"] == True, "Grid parameter value incorrect"
            
            print("✅ Grid search with file path test passed!")
            return True
            
    finally:
        # Clean up temporary files
        if os.path.exists(config_path):
            os.unlink(config_path)
        if os.path.exists(grid_path):
            os.unlink(grid_path)

if __name__ == "__main__":
    print("Running grid-file mode tests...")
    
    file_load_result = test_load_grid_file()
    run_result = test_run_with_grid_file()
    
    if file_load_result and run_result:
        print("✅ All grid-file mode tests passed!")
        exit(0)
    else:
        print("❌ Some tests failed!")
        exit(1)