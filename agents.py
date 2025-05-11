import asyncio, random, time
from collections import defaultdict
from typing import Dict, Set, List, Optional, Callable

# --------------------------------------------------------------------------- #
#  Base class                                                                 #
# --------------------------------------------------------------------------- #
class BaseAgent:
    """
    Every agent has:
      • name              – unique id in the chat
      • inbox             – asyncio.Queue for incoming strings
      • broadcast         – callable(str): sends a message to all agents
      • done_event        – asyncio.Event() which Strategist sets on CONFIRM
      • exit_event        - asyncio.Event() which is set when EXIT message is received
    """

    def __init__(self,
                 name: str,
                 broadcast: Callable[[str], None],
                 done_event: asyncio.Event):
        self.name          = name
        self.inbox         = asyncio.Queue()
        self.broadcast     = broadcast
        self.done_event    = done_event
        self.exit_event    = asyncio.Event()

    async def run(self):
        """Main coroutine: subclasses override `loop` for custom work."""
        loop_task = asyncio.create_task(self.loop())

        try:
            # Simply wait for done_event which is set by the Strategist
            await self.done_event.wait()
        finally:
            # Signal exit
            self.exit_event.set()

            # Put an EXIT message in the inbox to break any waiting recv() calls
            self.inbox.put_nowait("EXIT")

            # Cancel the loop task if it's still running
            if not loop_task.done():
                loop_task.cancel()

            # Wait for the task to complete with a timeout
            try:
                # Use shield to prevent cancellation from propagating to the wait_for
                await asyncio.wait_for(asyncio.shield(loop_task), timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass  # Expected during cancellation

    # -- helpers ------------------------------------------------------------- #
    async def send(self, text: str):
        self.broadcast(text)

    async def recv(self) -> str:
        """
        Receive a message from the inbox.
        Raises:
            asyncio.CancelledError: If the agent is being terminated
            SystemExit: If an EXIT message is received
        """
        msg = await self.inbox.get()

        # Check for EXIT message and raise SystemExit to stop loops
        if msg == "EXIT":
            self.exit_event.set()
            raise SystemExit("Agent shutting down")

        return msg

    # -- to be implemented in subclasses ------------------------------------ #
    async def loop(self):
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#  Generator                                                                  #
# --------------------------------------------------------------------------- #
class GeneratorAgent(BaseAgent):
    def __init__(self,
                 preferred_digit: Optional[str],
                 force_semantic: bool,
                 buffer_size: int,
                 **base_kwargs):
        super().__init__(**base_kwargs)
        self.preferred_digit = preferred_digit
        self.force_semantic  = force_semantic
        self.buffer_size     = buffer_size
        self.buffer: List[str] = []

    # ----------------------------
    def _random_code(self) -> str:
        if self.force_semantic:
            # ensure 07 appears somewhere
            pos = random.randrange(3)
            digits = [random.choice('0123456789') for _ in range(4)]
            digits[pos], digits[pos + 1] = '0', '7'
            return ''.join(digits)
        return ''.join(random.choice('0123456789')
                       for _ in range(4))

    # ----------------------------
    async def loop(self):
        try:
            while not self.exit_event.is_set():
                # propose new (or buffered) code
                if not self.buffer:
                    self.buffer = [self._random_code()
                                   for _ in range(self.buffer_size)]
                code = self.buffer.pop()
                await self.send(f"PROPOSE {code} {self.name}")

                # every so often endorse what we proposed
                # (helps consensus if Checker said ⊕ already)
                try:
                    msg = await asyncio.wait_for(self.recv(), timeout=0.05)

                    if msg.startswith("EVAL") and "+" in msg:
                        _, c, verdict, *_ = msg.split()
                        if c == code:
                            await self.send(f"ENDORSE {code} {self.name}")
                    elif msg.startswith("SUGGEST"):
                        _, suggested_code, sender = msg.split()
                        # Add the suggested code to our buffer with priority
                        if sender == "H" and suggested_code not in self.buffer:
                            # Insert at beginning so it's used soon
                            self.buffer.insert(0, suggested_code)
                except asyncio.TimeoutError:
                    # Check if we should exit
                    if self.exit_event.is_set():
                        break
                    # Brief sleep to yield control
                    await asyncio.sleep(0.001)
                    continue
                except (asyncio.CancelledError, SystemExit):
                    # Exit on cancellation or system exit
                    break
        except (asyncio.CancelledError, SystemExit):
            # Ensure clean exit
            pass


# --------------------------------------------------------------------------- #
#  Checker                                                                    #
# --------------------------------------------------------------------------- #
def _formal_constraints(code: str) -> bool:
    # Example rules — replace with your own if needed
    even_first      = int(code[0]) % 2 == 0
    exactly_two_rep = any(code.count(d) == 2 for d in set(code))
    return even_first and exactly_two_rep

def _semantic_constraint(code: str) -> bool:
    return "07" in code

class CheckerAgent(BaseAgent):
    async def loop(self):
        try:
            while not self.exit_event.is_set():
                try:
                    # Add timeout to make cancellation more responsive
                    try:
                        msg = await asyncio.wait_for(self.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        # Check if we should exit
                        if self.exit_event.is_set():
                            break
                        # Brief yield to event loop
                        await asyncio.sleep(0.001)
                        continue

                    if msg.startswith("PROPOSE"):
                        _, code, sender = msg.split()
                        is_ok = (_formal_constraints(code) and
                                 _semantic_constraint(code))
                        verdict = "+" if is_ok else "-"
                        await self.send(f"EVAL {code} {verdict} {self.name}")
                        if is_ok:
                            await self.send(f"ENDORSE {code} {self.name}")
                except (asyncio.CancelledError, SystemExit):
                    # Exit loop on cancellation or system exit
                    break
        except (asyncio.CancelledError, SystemExit):
            # Ensure clean task cancellation
            pass


# --------------------------------------------------------------------------- #
#  Strategist (now with Consensus Layer)                                      #
# --------------------------------------------------------------------------- #
class StrategistAgent(BaseAgent):
    def __init__(self,
                 threshold: int,
                 include_human: bool,
                 human_interval: int,
                 top_k: int,
                 **base_kwargs):
        super().__init__(**base_kwargs)
        self.threshold       = threshold
        self.include_human   = include_human
        self.human_interval  = human_interval
        self.top_k           = top_k

        self.endorsements: Dict[str, Set[str]] = defaultdict(set)
        self.cycle = 0

    # ----------------------------
    def _endorse(self, code: str, who: str):
        votes = self.endorsements[code]
        votes.add(who)
        if len(votes) >= self.threshold:
            asyncio.create_task(self.send(f"CONFIRM {code}"))
            self.done_event.set()

    # ----------------------------
    async def loop(self):
        try:
            while not self.exit_event.is_set():
                try:
                    # Add timeout to make cancellation more responsive
                    try:
                        msg = await asyncio.wait_for(self.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        # Check if we should exit
                        if self.exit_event.is_set():
                            break

                        # Still run the periodical human ping
                        if self.include_human and self.cycle % self.human_interval == 0:
                            top = sorted(self.endorsements.items(),
                                     key=lambda kv: -len(kv[1]))[: self.top_k]
                            codes = ' '.join(c for c, _ in top)
                            if codes:
                                await self.send(f"TOP {codes} {self.name}")
                        self.cycle += 1
                        # Brief yield to event loop
                        await asyncio.sleep(0.001)
                        continue

                    parts = msg.split()

                    if parts[0] == "EVAL":
                        _, code, verdict, sender = parts
                        if verdict == "+":
                            self._endorse(code, sender)

                    elif parts[0] == "ENDORSE":
                        _, code, sender = parts
                        self._endorse(code, sender)

                    elif parts[0] == "SCORE":           # from human
                        _, code, delta, sender = parts
                        if delta.startswith('+'):
                            self._endorse(code, sender)

                    # periodically ping human with top-K
                    if self.include_human and self.cycle % self.human_interval == 0:
                        top = sorted(self.endorsements.items(),
                                     key=lambda kv: -len(kv[1]))[: self.top_k]
                        codes = ' '.join(c for c, _ in top)
                        if codes:
                            await self.send(f"TOP {codes} {self.name}")
                    self.cycle += 1
                except (asyncio.CancelledError, SystemExit):
                    # Exit loop on cancellation or system exit
                    break
        except (asyncio.CancelledError, SystemExit):
            # Ensure clean task cancellation
            pass


# --------------------------------------------------------------------------- #
#  Synthetic Human                                                            #
# --------------------------------------------------------------------------- #
class SyntheticHumanAgent(BaseAgent):
    def __init__(self, lifetime: int, **base_kwargs):
        super().__init__(**base_kwargs)
        self.lifetime  = lifetime
        self.start_ts  = time.time()

    async def loop(self):
        try:
            while not self.exit_event.is_set():
                try:
                    # stop after lifetime seconds
                    if time.time() - self.start_ts > self.lifetime:
                        # Just note that we're no longer active, but keep handling messages
                        # to ensure proper shutdown
                        await asyncio.sleep(0.5)
                        continue

                    # Set a timeout to allow periodic checking of lifetime
                    try:
                        msg = await asyncio.wait_for(self.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        # Check if we should exit
                        if self.exit_event.is_set():
                            break
                        # Brief yield to event loop
                        await asyncio.sleep(0.001)
                        continue
                    if msg.startswith("TOP"):
                        _, *codes, sender = msg.split()
                        # endorse first code that has 07
                        for code in codes:
                            if "07" in code:
                                await self.send(f"SCORE {code} +1 {self.name}")
                                break
                        else:
                            # propose new code with 07 in random position
                            pos = random.randrange(3)
                            digits = [random.choice('0123456789') for _ in range(4)]
                            digits[pos], digits[pos + 1] = '0', '7'
                            code = ''.join(digits)
                            # Use SUGGEST message to send directly to GeneratorAgent
                            await self.send(f"SUGGEST {code} {self.name}")
                except (asyncio.CancelledError, SystemExit):
                    # Exit on cancellation or system exit
                    break
        except (asyncio.CancelledError, SystemExit):
            # Ensure clean task cancellation
            pass
