
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
        self.suggested_codes = set()  # Memory to store previously suggested codes

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
        """
        Handle incoming messages, particularly responding to TOP messages.
        For TOP messages, either upvote existing codes containing NASA_MONTH,
        or suggest new codes that include NASA_MONTH.
        """
        if msg.startswith('TOP'):
            # Parse the list of top candidate codes
            _, *codes = msg.split()
            
            # First look for existing codes with NASA_MONTH and upvote them
            for c in codes:
                if NASA_MONTH in c:
                    await self._send('Strategist', f'SCORE {c} +1')
                    return
                    
            # If no suitable codes found, generate a new suggestion
            # Try to generate a unique suggestion (not previously suggested)
            # with a maximum of 3 attempts to avoid infinite loops
            for _ in range(3):
                pos = random.randrange(3)          # 07?? | ?07? | ??07
                digits = list(''.join(random.choices('0123456789', k=4)))
                digits[pos], digits[pos + 1] = NASA_MONTH[0], NASA_MONTH[1]
                suggestion = ''.join(digits)
                
                # Check if this is a new suggestion
                if suggestion not in self.suggested_codes:
                    # Add to memory and send
                    self.suggested_codes.add(suggestion)
                    await self._send('Generator', f'SUGGEST {suggestion}')
                    self.log('suggest', agent=self.name, code=suggestion, is_new=True)
                    break
                else:
                    # Log that we skipped a duplicate suggestion
                    self.log('suggest', agent=self.name, code=suggestion, is_new=False)
            # If we tried 3 times and still got duplicates, we don't send any suggestion this round
