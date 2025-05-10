
import asyncio, random

NASA_MONTH='07'

class SyntheticHuman:
    """Heuristic human: upvotes codes containing '07' or suggests new ones."""
    def __init__(self, name, inbox, outboxes, log, lifetime=90.0):
        self.name=name
        self.inbox=inbox
        self.outboxes=outboxes
        self.log=log
        self.lifetime=lifetime
        self.t0=None

    async def _send(self, recipient, msg):
        await self.outboxes[recipient].put((self.name, msg))
        self.log('msg', sender=self.name, receiver=recipient,
                 bytes=len(msg.encode()), msg=msg)

    async def run(self):
        self.t0=asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time()-self.t0 < self.lifetime:
            try:
                sender, msg=self.inbox.get_nowait()
                await self.receive(sender,msg)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.05)
        self.log('terminated', agent=self.name)

    async def receive(self, sender, msg):
        if msg.startswith('TOP'):
            _, *codes = msg.split()
            for c in codes:
                if NASA_MONTH in c:
                    await self._send('Strategist', f'SCORE {c} +1')
                    return
            # suggestion=NASA_MONTH + ''.join(random.choices('0123456789',k=2))
            pos = random.randrange(3)          # 07?? | ?07? | ??07
            digits = list(''.join(random.choices('0123456789', k=4)))
            digits[pos], digits[pos + 1] = NASA_MONTH[0], NASA_MONTH[1]
            suggestion = ''.join(digits)
            await self._send('Generator', f'SUGGEST {suggestion}')
