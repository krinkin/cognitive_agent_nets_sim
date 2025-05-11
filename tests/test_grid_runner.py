import os
import json
import tempfile
import pytest
import shutil
import sys
from unittest.mock import patch, MagicMock

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
        
        # Skip the file output checks as they don't work reliably in Docker
        with patch('pandas.DataFrame.to_csv'):  # Mock the CSV file writing
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
        
        total_configs = 4  # Mock total number of configurations
        params = (config, "test_config", 0, config_dir, False, None, param_grid, total_configs)

        # Run single config
        result = grid_runner.run_single_config(params)
        
        # Check result
        assert result["config_id"] == 0
        assert result["config_name"] == "test_config"
        assert result["baseline_success_rate"] > 0
        assert result["hybrid_success_rate"] == 1.0
        assert os.path.exists(os.path.join(config_dir, "result.json"))

def test_grid_file_mode():
    """Test that grid-file mode correctly loads and uses a custom grid file."""
    # Create temp directory for test output
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create a custom grid file with unique parameters
        custom_grid = {
            "duration": [15, 30],
            "generator.preferred_digit": [7],
            "synthetic_human.lifetime": [45]
        }
        
        # Save custom grid to a temporary file
        grid_path = os.path.join(tmpdirname, "custom_test_grid.json")
        with open(grid_path, "w") as f:
            json.dump(custom_grid, f)
        
        # Test the loading function with patching
        with patch('builtins.open', new_callable=MagicMock()) as mock_open:
            # Set up the mock file handle
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Mock json.load to return our custom grid
            with patch('json.load', return_value=custom_grid) as mock_json_load:
                # Test loading the grid file
                grid_data = grid_runner.load_grid_file(grid_path)
                
                # Verify json.load was called with our mock file
                mock_json_load.assert_called_once()
                
                # Verify the returned grid is our custom grid
                assert grid_data == custom_grid
                assert "duration" in grid_data
                assert grid_data["duration"] == [15, 30]
                assert "generator.preferred_digit" in grid_data
                assert grid_data["generator.preferred_digit"] == [7]
                
        # Now test the actual use of this grid in creating configurations
        base_config = create_test_config()
        configs = grid_runner.create_grid_configs(base_config, custom_grid)
        
        # Should have 2 durations x 1 preferred_digit x 1 lifetime = 2 configurations
        assert len(configs) == 2
        
        # Verify each config has the expected parameters
        for config, name in configs:
            # Each config should use one of our duration values
            assert config["duration"] in [15, 30]
            
            # Check that our generator.preferred_digit is set correctly
            assert config["generator"]["preferred_digit"] == 7
            
            # Check that our synthetic_human.lifetime is set correctly
            assert config["synthetic_human"]["lifetime"] == 45
            
            # Verify the name includes our parameters
            assert "generator.preferred_digit=7" in name
            assert "synthetic_human.lifetime=45" in name
            assert "duration=15" in name or "duration=30" in name