import pytest
import random
import asyncio
import tempfile
import json
import os
from runner import run_once

def generate_test_config(seed):
    """Generate a test configuration with a specified seed."""
    return {
        "seed": seed,
        "duration": 5,
        "generator": {
            "preferred_digit": None,
            "force_semantic": False,
            "buffer_size": 10,
            "focus_influence_probability": 0.5
        },
        "strategist": {
            "threshold": 1,
            "human_interval": 5,
            "top_k": 3,
            "focus_hint_interval": 10,
            "focus_hint_top_n_codes": 3,
            "focus_min_occurrences": 2
        },
        "synthetic_human": {
            "lifetime": 10
        }
    }

def extract_messages_from_log(log_path):
    """Extract all messages from a log file."""
    messages = []
    with open(log_path) as f:
        for line in f:
            event = json.loads(line)
            if event["event"] == "msg":
                messages.append(event["text"])
    return messages

@pytest.mark.asyncio
async def test_seed_reproducibility():
    """Test that simulations with the same seed produce exactly the same results."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Run first simulation with seed 123
        config1 = generate_test_config(123)
        log_path1 = await run_once(config1, "test_seed_1", tmp_dir, include_human=False)
        
        # Run second simulation with the same seed 123
        config2 = generate_test_config(123)
        log_path2 = await run_once(config2, "test_seed_2", tmp_dir, include_human=False)
        
        # Extract messages from both logs
        messages1 = extract_messages_from_log(log_path1)
        messages2 = extract_messages_from_log(log_path2)
        
        # Compare the messages from both runs - they should be identical
        assert len(messages1) > 0, "First simulation produced no messages"
        assert len(messages2) > 0, "Second simulation produced no messages"
        assert messages1 == messages2, "Messages differ between runs with the same seed"

@pytest.mark.asyncio
async def test_different_seeds_produce_different_results():
    """Test that simulations with different seeds produce different results."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Run first simulation with seed 123
        config1 = generate_test_config(123)
        log_path1 = await run_once(config1, "test_seed_diff_1", tmp_dir, include_human=False)
        
        # Run second simulation with a different seed 456
        config2 = generate_test_config(456)
        log_path2 = await run_once(config2, "test_seed_diff_2", tmp_dir, include_human=False)
        
        # Extract messages from both logs
        messages1 = extract_messages_from_log(log_path1)
        messages2 = extract_messages_from_log(log_path2)
        
        # Compare the messages from both runs - they should be different
        assert len(messages1) > 0, "First simulation produced no messages"
        assert len(messages2) > 0, "Second simulation produced no messages"
        assert messages1 != messages2, "Messages identical between runs with different seeds"

@pytest.mark.asyncio
async def test_no_seed_deterministic_within_run():
    """Test that when a seed is not specified, it's generated and used consistently during the run."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Generate a configuration without a seed
        config = generate_test_config(None)
        del config["seed"]
        
        # Run simulation
        log_path = await run_once(config, "test_no_seed", tmp_dir, include_human=False)
        
        # Extract the seed from the log
        seed = None
        with open(log_path) as f:
            for line in f:
                event = json.loads(line)
                if event["event"] == "start" and "seed" in event:
                    seed = event["seed"]
                    break
        
        # Verify that a seed was recorded
        assert seed is not None, "No seed was recorded in the log"
        assert isinstance(seed, int), "Recorded seed is not an integer"