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
    """

    def __init__(self,
                 name: str,
                 broadcast: Callable[[str], None],
                 done_event: asyncio.Event):
        self.name          = name
        self.inbox         = asyncio.Queue()
        self.broadcast     = broadcast
        self.done_event    = done_event

    async def run(self):
        """Main coroutine: subclasses override `loop` for custom work."""
        loop_task = asyncio.create_task(self.loop())
        try:
            await self.done_event.wait()          # stop when Strategist says so
        finally:
            loop_task.cancel()

    # -- helpers ------------------------------------------------------------- #
    async def send(self, text: str):
        self.broadcast(text)

    async def recv(self) -> str:
        return await self.inbox.get()

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
        while True:
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
            except asyncio.TimeoutError:
                continue

            if msg.startswith("EVAL") and "+" in msg:
                _, c, verdict, *_ = msg.split()
                if c == code:
                    await self.send(f"ENDORSE {code} {self.name}")


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
        while True:
            msg = await self.recv()
            if msg.startswith("PROPOSE"):
                _, code, sender = msg.split()
                is_ok = (_formal_constraints(code) and
                         _semantic_constraint(code))
                verdict = "+" if is_ok else "-"
                await self.send(f"EVAL {code} {verdict} {self.name}")
                if is_ok:
                    await self.send(f"ENDORSE {code} {self.name}")


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
        while True:
            msg = await self.recv()
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


# --------------------------------------------------------------------------- #
#  Synthetic Human                                                            #
# --------------------------------------------------------------------------- #
class SyntheticHumanAgent(BaseAgent):
    def __init__(self, lifetime: int, **base_kwargs):
        super().__init__(**base_kwargs)
        self.lifetime  = lifetime
        self.start_ts  = time.time()

    async def loop(self):
        while True:
            # stop after lifetime seconds
            if time.time() - self.start_ts > self.lifetime:
                await asyncio.sleep(999)
            msg = await self.recv()
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
                    await self.send(f"PROPOSE {code} {self.name}")
                    await self.send(f"ENDORSE {code} {self.name}")
