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
    
    # Check that the agent proposed and endorsed a new code containing '07'
    assert len(broadcast_callback.messages) == 2
    assert broadcast_callback.messages[0].startswith("PROPOSE ")
    assert broadcast_callback.messages[0].endswith(" H")
    assert "07" in broadcast_callback.messages[0].split()[1]
    assert broadcast_callback.messages[1].startswith("ENDORSE ")
    assert broadcast_callback.messages[1].endswith(" H")