import asyncio
import time
import random

# ----------------------------------------------------------------------
class BaseAgent:
    def __init__(self, name, inbox, outboxes, log, lifetime=30.0):
        self.name = name
        self.inbox = inbox
        self.outboxes = outboxes        # dict name -> queue
        self.log = log
        self.lifetime = lifetime
        self.t0 = None

    async def send(self, recipient: str, msg: str):
        await self.outboxes[recipient].put((self.name, msg))
        self.log('msg', sender=self.name, receiver=recipient,
                 bytes=len(msg.encode()), msg=msg)

    async def broadcast(self, msg: str):
        for r in self.outboxes:
            if r != self.name:
                await self.send(r, msg)

    async def run(self):
        self.t0 = time.perf_counter()
        while time.perf_counter() - self.t0 < self.lifetime:
            try:
                sender, msg = self.inbox.get_nowait()
                await self.receive(sender, msg)
            except asyncio.QueueEmpty:
                await self.idle()
                await asyncio.sleep(0.02)
        self.log('terminated', agent=self.name)

    async def idle(self):
        pass

    async def receive(self, sender, msg):
        raise NotImplementedError


# ----------------------------------------------------------------------
class GeneratorAgent(BaseAgent):
    """Генератор 4-значных кодов."""
    def __init__(self, *a,
                 buffer_size=25,
                 preferred_digit=None,
                 force_semantic=True,      # всегда содержит ‘07’
                 **kw):
        super().__init__(*a, **kw)
        self.buffer_size = buffer_size
        self.buffer = []
        self.preferred_digit = preferred_digit
        self.force_semantic = force_semantic

    def _new_code(self) -> str:
        digits = list(random.choices('0123456789', k=4))

        # делаем семантическое условие истинным
        if self.force_semantic:
            pos = random.randrange(3)          # 07?? | ?07? | ??07
            digits[pos], digits[pos + 1] = '0', '7'

        # bias первой цифры
        if self.preferred_digit and random.random() < 0.5:
            digits[random.randrange(4)] = self.preferred_digit

        return ''.join(digits)

    async def idle(self):
        if len(self.buffer) < self.buffer_size:
            code = self._new_code()
            self.buffer.append(code)
            await self.send('Checker', f'PROPOSE {code}')

    async def receive(self, sender, msg):
        if msg.startswith('EVAL'):
            _, code, verdict = msg.split()
            if verdict == '✗' and code in self.buffer:
                self.buffer.remove(code)
        elif msg.startswith('SUGGEST'):
            _, code = msg.split()
            if len(code) == 4 and code.isdigit() and code not in self.buffer:
                self.buffer.append(code)


# ----------------------------------------------------------------------
class CheckerAgent(BaseAgent):
    """Проверяет одно правило constraint(code) → ✓/✗."""
    def __init__(self, *a, constraint, **kw):
        super().__init__(*a, **kw)
        self.constraint = constraint

    async def receive(self, sender, msg):
        if msg.startswith('PROPOSE'):
            _, code = msg.split()
            verdict = '✓' if self.constraint(code) else '✗'
            await self.send('Strategist', f'EVAL {code} {verdict}')


# ----------------------------------------------------------------------
class StrategistAgent(BaseAgent):
    """Ведёт таблицу очков; подтверждает, когда набрано threshold очков."""
    def __init__(self, *a,
                 top_k=10,
                 threshold=2,          # нужно хотя бы 2 очка
                 human_interval=2,     # каждые 2 хода отправляем Human
                 **kw):
        super().__init__(*a, **kw)
        self.scores = {}
        self.top_k = top_k
        self.threshold = threshold
        self.human_interval = human_interval
        self.counter = 0

    def _best(self, k=3):
        return sorted(self.scores.items(), key=lambda kv: -kv[1])[:k]

    async def idle(self):
        self.counter += 1
        if self.counter % self.human_interval == 0:
            best = [c for c, _ in self._best()]
            if best:
                await self.send('Human', 'TOP ' + ' '.join(best))

    async def receive(self, sender, msg):
        parts = msg.split()
        kind = parts[0]

        if kind == 'EVAL':
            code, verdict = parts[1], parts[2]
            delta = 1 if verdict == '✓' else -1
            self.scores[code] = self.scores.get(code, 0) + delta
            if self.scores[code] >= self.threshold:
                await self.broadcast(f'CONFIRM {code}')

        elif kind == 'SCORE':
            code, vote = parts[1], parts[2]
            delta = 1 if vote == '+1' else -1
            self.scores[code] = self.scores.get(code, 0) + delta

        elif kind == 'SUGGEST':
            code = parts[1]
            self.scores.setdefault(code, 0)
