import os
import json
import tempfile
import pytest
import shutil
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grid_runner
import runner

def create_test_config():
    """Create a minimal test configuration."""
    return {
        "sessions": 2,
        "duration": 10,
        "generator": {
            "preferred_digit": 0,
            "force_semantic": False,
            "buffer_size": 25
        },
        "strategist": {
            "threshold": 1,
            "human_interval": 3,
            "top_k": 5
        },
        "synthetic_human": {
            "lifetime": 30
        }
    }

def create_test_param_grid():
    """Create a small test parameter grid."""
    return {
        "generator.force_semantic": [False, True],
        "strategist.threshold": [1, 2]
    }

def test_create_grid_configs():
    """Test that grid configurations are created correctly."""
    base_config = create_test_config()
    param_grid = create_test_param_grid()
    
    configs = grid_runner.create_grid_configs(base_config, param_grid)
    
    # Should create 2x2 = 4 configurations
    assert len(configs) == 4
    
    # Check a specific configuration
    for config, name in configs:
        if config["generator"]["force_semantic"] and config["strategist"]["threshold"] == 2:
            # Verify name includes parameters
            assert "generator.force_semantic=True" in name
            assert "strategist.threshold=2" in name
            # Verify other params unchanged
            assert config["sessions"] == base_config["sessions"]
            assert config["duration"] == base_config["duration"]
            assert config["generator"]["preferred_digit"] == base_config["generator"]["preferred_digit"]

@pytest.fixture
def mock_run_simulations():
    """Mock the run_simulations function to avoid actually running simulations."""
    with patch('runner.run_simulations') as mock:
        # When run_simulations is called, return a list of fake log paths
        def side_effect(config, logdir, parallel, processes):
            # Create the logdir to simulate real behavior
            os.makedirs(logdir, exist_ok=True)
            
            # Create some dummy log files
            baseline_paths = []
            hybrid_paths = []
            
            for i in range(config["sessions"]):
                # Create simple log file contents
                baseline_content = json.dumps({"event": "start", "t": 1000}) + "\n"
                if config["generator"]["force_semantic"] and config["strategist"]["threshold"] == 1:
                    # Success for this configuration
                    baseline_content += json.dumps({"event": "msg", "t": 1005, "text": "CONFIRM 1234"}) + "\n"
                
                hybrid_content = json.dumps({"event": "start", "t": 1000}) + "\n"
                hybrid_content += json.dumps({"event": "msg", "t": 1002, "text": "CONFIRM 5678"}) + "\n"
                
                # Write test log files
                baseline_path = os.path.join(logdir, f"baseline_{i}.jsonl")
                hybrid_path = os.path.join(logdir, f"hybrid_{i}.jsonl")
                
                with open(baseline_path, "w") as f:
                    f.write(baseline_content)
                    
                with open(hybrid_path, "w") as f:
                    f.write(hybrid_content)
                
                baseline_paths.append(baseline_path)
                hybrid_paths.append(hybrid_path)
            
            return baseline_paths, hybrid_paths
            
        mock.side_effect = side_effect
        yield mock

def test_run_grid_search(mock_run_simulations):
    """Test that grid search runs and produces expected output."""
    # Create temp directory for test output
    with tempfile.TemporaryDirectory() as tmpdirname:
        base_config = create_test_config()
        param_grid = create_test_param_grid()
        
        # Save base config to a temporary file
        config_path = os.path.join(tmpdirname, "test_config.json")
        with open(config_path, "w") as f:
            json.dump(base_config, f)
        
        # Run grid search with sequential configs (to simplify test)
        results = grid_runner.run_grid_search(
            config_path, 
            param_grid, 
            tmpdirname,
            parallel=False,
            grid_parallel=False
        )
        
        # Test analysis of the grid search
        assert len(results) == 4  # 2x2 configurations
        assert "config_id" in results[0]
        assert "baseline_success_rate" in results[0]
        assert "hybrid_success_rate" in results[0]
        
        # Check if grid directory was created
        grid_dirs = [d for d in os.listdir(tmpdirname) if d.startswith("grid_")]
        assert len(grid_dirs) > 0

        # Check if results.csv exists in the grid directory
        grid_dir = os.path.join(tmpdirname, grid_dirs[0])
        assert os.path.exists(os.path.join(grid_dir, "results.csv"))
        
        # Check that results reflect our mock data
        for result in results:
            if result["generator.force_semantic"] == True and result["strategist.threshold"] == 1:
                # This was our "success" configuration in the mock
                assert result["baseline_success_rate"] > 0
            
            # All hybrid runs succeed in our mock
            assert result["hybrid_success_rate"] == 1.0

def test_run_single_config(mock_run_simulations):
    """Test that a single configuration runs as expected."""
    # Create temp directory for test output
    with tempfile.TemporaryDirectory() as tmpdirname:
        config = create_test_config()
        config["generator"]["force_semantic"] = True  # Set to our "success" config
        param_grid = create_test_param_grid()
        config_dir = os.path.join(tmpdirname, "test_config")
        
        params = (config, "test_config", 0, config_dir, False, None, param_grid)
        
        # Run single config
        result = grid_runner.run_single_config(params)
        
        # Check result
        assert result["config_id"] == 0
        assert result["config_name"] == "test_config"
        assert result["baseline_success_rate"] > 0
        assert result["hybrid_success_rate"] == 1.0
        assert os.path.exists(os.path.join(config_dir, "result.json"))