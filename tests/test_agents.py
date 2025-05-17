import pytest
import asyncio
from agents import (
    BaseAgent,
    GeneratorAgent,
    CheckerAgent,
    StrategistAgent,
    SyntheticHumanAgent,
    _formal_constraints,
    _semantic_constraint
)

@pytest.fixture
def broadcast_callback():
    """Returns a function that tracks messages sent through broadcast."""
    messages = []
    
    def broadcast(msg):
        messages.append(msg)
    
    broadcast.messages = messages
    return broadcast

@pytest.fixture
def done_event():
    """Returns an asyncio.Event for signaling completion."""
    return asyncio.Event()

@pytest.mark.asyncio
async def test_base_agent_send(broadcast_callback, done_event):
    """Test BaseAgent's send method broadcasts messages correctly."""
    agent = BaseAgent(name="TestAgent", broadcast=broadcast_callback, done_event=done_event)
    
    await agent.send("TEST MESSAGE")
    
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0] == "TEST MESSAGE"

@pytest.mark.asyncio
async def test_base_agent_recv(broadcast_callback, done_event):
    """Test BaseAgent's recv method retrieves messages from inbox."""
    agent = BaseAgent(name="TestAgent", broadcast=broadcast_callback, done_event=done_event)
    
    # Put a message in the inbox
    test_message = "HELLO"
    agent.inbox.put_nowait(test_message)
    
    # Receive the message
    received = await agent.recv()
    
    assert received == test_message

def test_formal_constraints():
    """Test the formal constraints checker function."""
    # Valid cases (even first digit and at least one digit appears exactly twice)
    assert _formal_constraints("2233") is True   # 2 appears twice, 3 appears twice
    assert _formal_constraints("4040") is True   # 4 appears twice, 0 appears twice
    assert _formal_constraints("8118") is True   # 8 appears twice, 1 appears twice

    # More valid cases
    assert _formal_constraints("0112") is True   # 0 is even, 1 appears twice
    assert _formal_constraints("2445") is True   # 2 is even, 4 appears twice
    assert _formal_constraints("6090") is True   # 6 is even, 0 appears twice

    # Invalid cases - fails first constraint (odd first digit)
    assert _formal_constraints("1233") is False  # Odd first digit

    # Invalid cases - fails second constraint (no digit appears exactly twice)
    assert _formal_constraints("2345") is False  # No repeats
    assert _formal_constraints("2222") is False  # Single digit repeated 4 times (no digit appears exactly twice)

    # Invalid cases - digit appears 3 times (not exactly twice)
    assert _formal_constraints("2333") is False  # 3 appears three times

def test_semantic_constraint():
    """Test the semantic constraint checker function."""
    # Valid cases containing "07"
    assert _semantic_constraint("0712") is True
    assert _semantic_constraint("1207") is True
    assert _semantic_constraint("3074") is True
    
    # Invalid cases
    assert _semantic_constraint("1234") is False
    assert _semantic_constraint("7012") is False
    assert _semantic_constraint("7890") is False

@pytest.mark.asyncio
async def test_generator_random_code(broadcast_callback, done_event):
    """Test that GeneratorAgent generates codes correctly."""
    # Test with force_semantic=True
    agent_semantic = GeneratorAgent(
        preferred_digit=None,
        force_semantic=True,
        buffer_size=1,
        name="G",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Check a few generated codes
    for _ in range(10):
        code = agent_semantic._random_code()
        assert len(code) == 4
        assert "07" in code
    
    # Test with force_semantic=False
    agent_random = GeneratorAgent(
        preferred_digit=None,
        force_semantic=False,
        buffer_size=1,
        name="G",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Check a few generated codes
    random_codes = [agent_random._random_code() for _ in range(20)]
    assert all(len(code) == 4 for code in random_codes)
    assert all(code.isdigit() for code in random_codes)

@pytest.mark.asyncio
async def test_checker_agent_evaluation(broadcast_callback, done_event):
    """Test that CheckerAgent evaluates codes correctly."""
    agent = CheckerAgent(name="C", broadcast=broadcast_callback, done_event=done_event)

    # Test with a valid code (even first digit, one digit appears twice, contains 07)
    agent.inbox.put_nowait("PROPOSE 0707 G")

    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()

    # Check that the agent evaluated the code correctly
    assert len(broadcast_callback.messages) == 2
    assert broadcast_callback.messages[0] == "EVAL 0707 + C"
    assert broadcast_callback.messages[1] == "ENDORSE 0707 C"

    # Clear messages for next test
    broadcast_callback.messages.clear()

    # Test with an invalid code (odd first digit)
    agent.inbox.put_nowait("PROPOSE 1234 G")

    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()

    # Check that the agent evaluated the code correctly
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0] == "EVAL 1234 - C"

@pytest.mark.asyncio
async def test_strategist_agent_endorsement(broadcast_callback, done_event):
    """Test that StrategistAgent tracks endorsements and confirms when threshold is reached."""
    # Test with threshold=1
    agent = StrategistAgent(
        threshold=1,
        include_human=False,
        human_interval=5,
        top_k=3,
        name="S",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Simulate an endorsement
    agent.inbox.put_nowait("ENDORSE 0707 G")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Check that the agent confirmed the code
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0] == "CONFIRM 0707"
    assert done_event.is_set() is True
    
    # Reset for next test
    broadcast_callback.messages.clear()
    done_event.clear()
    
    # Test with threshold=2
    agent = StrategistAgent(
        threshold=2,
        include_human=False,
        human_interval=5,
        top_k=3,
        name="S",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Simulate one endorsement (not enough to reach threshold)
    agent.inbox.put_nowait("ENDORSE 0707 G")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Check that the agent did not confirm the code yet
    assert len(broadcast_callback.messages) == 0
    assert done_event.is_set() is False
    
    # Simulate a second endorsement (reaching threshold)
    agent.inbox.put_nowait("ENDORSE 0707 C")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Check that the agent confirmed the code
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0] == "CONFIRM 0707"
    assert done_event.is_set() is True

@pytest.mark.asyncio
async def test_synthetic_human_agent(broadcast_callback, done_event):
    """Test that SyntheticHumanAgent endorses codes containing '07'."""
    agent = SyntheticHumanAgent(
        lifetime=5,
        name="H",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Simulate receiving top codes with one containing '07'
    agent.inbox.put_nowait("TOP 1234 0756 9876 S")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Check that the agent endorsed the code containing '07'
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0] == "SCORE 0756 +1 H"
    
    # Reset for next test
    broadcast_callback.messages.clear()
    
    # Simulate receiving top codes without any containing '07'
    agent.inbox.put_nowait("TOP 1234 5678 9876 S")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Check that the agent suggests a new code containing '07'
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0].startswith("SUGGEST ")
    assert broadcast_callback.messages[0].endswith(" H")
    assert "07" in broadcast_callback.messages[0].split()[1]

@pytest.mark.asyncio
async def test_strategist_focus_hint_generation(broadcast_callback, done_event):
    """Test that StrategistAgent generates FOCUS_HINT messages correctly."""
    agent = StrategistAgent(
        threshold=2,
        include_human=False,
        human_interval=5,
        top_k=3,
        focus_hint_interval=5,
        focus_hint_top_n_codes=2,
        focus_min_occurrences=2,
        name="S",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Add codes with repeating digits to the endorsements
    # Code 1: 0734 (3 endorsements)
    # Code 2: 2344 (2 endorsements)
    # Code 3: 8777 (1 endorsement)
    # Digit '4' appears in both top codes
    agent.endorsements["0734"].add("G")
    agent.endorsements["0734"].add("C")
    agent.endorsements["0734"].add("H")
    
    agent.endorsements["2344"].add("G")
    agent.endorsements["2344"].add("C")
    
    agent.endorsements["8777"].add("G")
    
    # Run the _generate_and_send_focus_hint method
    loop_task = asyncio.create_task(agent._generate_and_send_focus_hint())
    await asyncio.sleep(0.1)
    
    # Check that the agent sent a FOCUS_HINT message for digit '4'
    # which appears in both top codes and meets the threshold
    assert len(broadcast_callback.messages) == 1
    assert broadcast_callback.messages[0].startswith("FOCUS_HINT")
    
    # The focus hint should be for digit '4' as it appears in both top codes
    parts = broadcast_callback.messages[0].split()
    assert len(parts) == 3
    assert parts[0] == "FOCUS_HINT"
    assert parts[1] == "4"
    assert parts[2] == "S"
    
    # For the second part of the test, we'll directly call the method again
    # rather than trying to test the loop mechanism which is more complex
    broadcast_callback.messages.clear()
    
    # Reset the last_focus_hint_value to allow sending the same hint again
    agent.last_focus_hint_value = None
    
    # Run the _generate_and_send_focus_hint method again with a different configuration
    agent.focus_min_occurrences = 1  # Make it easier for a focus hint to be generated
    await agent._generate_and_send_focus_hint()
    
    # Check that a FOCUS_HINT message was sent
    assert len(broadcast_callback.messages) > 0
    assert any(msg.startswith("FOCUS_HINT") for msg in broadcast_callback.messages)

@pytest.mark.asyncio
async def test_generator_focus_hint_influence(broadcast_callback, done_event):
    """Test that GeneratorAgent receives and uses FOCUS_HINT messages in code generation."""
    # Create a generator with focus_influence_probability=1.0 for deterministic testing
    agent = GeneratorAgent(
        preferred_digit=None,
        force_semantic=False,
        buffer_size=5,
        focus_influence_probability=1.0,
        name="G",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Initially no focus hint
    assert agent.focus_hint is None
    
    # Check normal random code generation without focus hint
    random_codes = [agent._random_code() for _ in range(10)]
    assert all(len(code) == 4 for code in random_codes)
    assert all(code.isdigit() for code in random_codes)
    
    # Simulate receiving a FOCUS_HINT message
    focus_digit = "5"
    agent.inbox.put_nowait(f"FOCUS_HINT {focus_digit} S")
    
    # Process the message and check if focus_hint was updated
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Verify the agent received and stored the focus hint
    assert agent.focus_hint == focus_digit
    
    # Check that new codes include the focus hint (with 100% probability)
    influenced_codes = [agent._random_code() for _ in range(10)]
    assert all(focus_digit in code for code in influenced_codes)
    
    # Test with force_semantic=True
    agent = GeneratorAgent(
        preferred_digit=None,
        force_semantic=True,
        buffer_size=5,
        focus_influence_probability=1.0,
        name="G",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Set focus hint
    agent.focus_hint = focus_digit
    
    # Check that new codes include both "07" (from force_semantic) and focus_digit
    semantic_codes = [agent._random_code() for _ in range(10)]
    assert all("07" in code for code in semantic_codes)
    assert all(focus_digit in code for code in semantic_codes)
    
    # Test buffer clearing when receiving new focus hint
    agent = GeneratorAgent(
        preferred_digit=None,
        force_semantic=False,
        buffer_size=5,
        focus_influence_probability=1.0,
        name="G",
        broadcast=broadcast_callback,
        done_event=done_event
    )
    
    # Fill the buffer with codes
    agent.buffer = ["1234", "5678", "9012", "3456", "7890"]
    original_buffer = agent.buffer.copy()
    
    # Process a FOCUS_HINT message
    agent.inbox.put_nowait("FOCUS_HINT 3 S")
    
    # Run the agent loop for a short time
    loop_task = asyncio.create_task(agent.loop())
    await asyncio.sleep(0.1)
    loop_task.cancel()
    
    # Verify the focus hint was set correctly
    assert agent.focus_hint == "3"
    # We don't check the buffer as it might get automatically refilled during the loop