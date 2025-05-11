import pytest
import asyncio
import json
import os
import time
import tempfile
from runner import make_logger, analyse, run_once

def test_make_logger():
    """Test the buffered logger functionality."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_name = "test_session"
        log, close, log_path = make_logger(session_name, tmp_dir, batch=2)
        
        # Check log path
        assert os.path.exists(tmp_dir)
        assert log_path == os.path.join(tmp_dir, f"{session_name}.jsonl")
        
        # Log some events
        log("start")
        log("msg", text="Hello")
        log("msg", text="World")  # This should trigger a flush (batch=2)
        
        # Close the log
        close()
        
        # Verify the log file contents
        with open(log_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            # Parse and check the events
            events = [json.loads(line) for line in lines]
            assert events[0]["event"] == "start"
            assert events[0]["session"] == session_name
            
            assert events[1]["event"] == "msg"
            assert events[1]["text"] == "Hello"
            assert events[1]["session"] == session_name
            
            assert events[2]["event"] == "msg"
            assert events[2]["text"] == "World"
            assert events[2]["session"] == session_name

def test_logger_after_close():
    """Test that logger ignores writes after close."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        log, close, log_path = make_logger("test_session", tmp_dir)
        
        # Log an event and close
        log("start")
        close()
        
        # Try to log after close (should be ignored)
        log("msg", text="Should be ignored")
        
        # Verify the log file contents
        with open(log_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            event = json.loads(lines[0])
            assert event["event"] == "start"

def test_analyse():
    """Test the log analysis function."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create test log files
        log_paths = []
        
        # Log file with a successful confirmation
        log_path1 = os.path.join(tmp_dir, "session1.jsonl")
        with open(log_path1, 'w') as f:
            start_time = time.time()
            f.write(json.dumps({"t": start_time, "event": "start"}) + "\n")
            f.write(json.dumps({"t": start_time + 1.5, "event": "msg", "text": "PROPOSE 0707 G"}) + "\n")
            f.write(json.dumps({"t": start_time + 2.0, "event": "msg", "text": "CONFIRM 0707"}) + "\n")
        log_paths.append(log_path1)
        
        # Log file without confirmation
        log_path2 = os.path.join(tmp_dir, "session2.jsonl")
        with open(log_path2, 'w') as f:
            start_time = time.time()
            f.write(json.dumps({"t": start_time, "event": "start"}) + "\n")
            f.write(json.dumps({"t": start_time + 1.0, "event": "msg", "text": "PROPOSE 1234 G"}) + "\n")
            f.write(json.dumps({"t": start_time + 1.5, "event": "msg", "text": "EVAL 1234 ⊖ C"}) + "\n")
        log_paths.append(log_path2)
        
        # Log file with a successful confirmation
        log_path3 = os.path.join(tmp_dir, "session3.jsonl")
        with open(log_path3, 'w') as f:
            start_time = time.time()
            f.write(json.dumps({"t": start_time, "event": "start"}) + "\n")
            f.write(json.dumps({"t": start_time + 2.0, "event": "msg", "text": "PROPOSE 2244 G"}) + "\n")
            f.write(json.dumps({"t": start_time + 3.0, "event": "msg", "text": "CONFIRM 2244"}) + "\n")
        log_paths.append(log_path3)
        
        # Test the analyse function
        success_rate, avg_time, avg_bytes = analyse(log_paths)
        
        # Check the analysis results
        assert success_rate == 2/3  # 2 successful confirmations out of 3 sessions
        assert avg_time > 0  # Average time to success should be positive
        assert avg_bytes > 0  # Average byte count should be positive

@pytest.mark.asyncio
async def test_run_once():
    """Test a single simulation run."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a minimal test configuration
        config = {
            "duration": 1,  # Short duration for testing
            "generator": {
                "preferred_digit": None,
                "force_semantic": True,  # Force semantic constraint to speed up success
                "buffer_size": 10
            },
            "strategist": {
                "threshold": 1,
                "human_interval": 5,
                "top_k": 3
            },
            "synthetic_human": {
                "lifetime": 10
            }
        }
        
        # Run a simulation
        log_path = await run_once(config, "test_run", tmp_dir, include_human=False)
        
        # Verify the log file was created
        assert os.path.exists(log_path)
        
        # Check log file contents
        with open(log_path, 'r') as f:
            events = [json.loads(line) for line in f.readlines()]
            
            # There should be at least a start event
            assert any(event["event"] == "start" for event in events)
            
            # There should be message events
            msg_events = [event for event in events if event["event"] == "msg"]
            assert len(msg_events) > 0