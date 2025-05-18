
import asyncio, random

NASA_MONTH='07'

class SyntheticHuman:
    """
    Enhanced heuristic human agent that upvotes codes containing '07' or suggests 
    intelligent new ones that follow specific constraints.
    
    Features:
    - Always includes '07' somewhere in the code
    - Ensures the first digit is even when possible
    - Avoids repeating digits (especially '0' and '7') when generating other positions
    - Remembers previous suggestions to avoid duplicates
    """
    def __init__(self, name, inbox, outboxes, log, lifetime=90.0):
        self.name = name              # Agent identifier
        self.inbox = inbox            # Queue for incoming messages
        self.outboxes = outboxes      # Mapping of agent names to output queues
        self.log = log                # Logger function
        self.lifetime = lifetime      # Duration the agent remains active (seconds)
        self.t0 = None                # Start time (set when agent begins running)
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
                    
            # If no suitable codes found, generate a new intelligent suggestion
            # Try to generate a unique suggestion (not previously suggested)
            # with a maximum of 5 attempts to avoid infinite loops
            for attempt in range(5):
                # Step 1: Determine '07' position (07xx, x07x, or xx07)
                pos = random.randrange(3)
                # Initialize code list with placeholders
                code_list = ['X', 'X', 'X', 'X']
                # Place '0' and '7' at determined position
                code_list[pos] = NASA_MONTH[0]
                code_list[pos + 1] = NASA_MONTH[1]
                
                # Step 2: Identify placeholder indices (the two 'X' positions)
                placeholder_indices = [i for i, char in enumerate(code_list) if char == 'X']
                
                # Step 3: Generate digits for placeholders
                # First placeholder
                idx1 = placeholder_indices[0]
                if idx1 == 0:  # If this is the first digit of the code
                    # Choose an even digit for the first position
                    digit1 = random.choice(['0', '2', '4', '6', '8'])
                else:
                    # Any digit except '0' and '7' to avoid immediate repetition
                    digit1 = random.choice([str(d) for d in range(10) if str(d) not in NASA_MONTH])
                
                # Second placeholder
                idx2 = placeholder_indices[1]
                
                # Define pool of available digits for the second placeholder
                possible_digits_for_d2 = [str(d) for d in range(10)]
                
                # Remove digits we want to avoid for the second digit
                if digit1 in possible_digits_for_d2:
                    possible_digits_for_d2.remove(digit1)  # Avoid repeating the first random digit
                
                # Avoid '0' and '7' unless we're intentionally creating a pair with digit1
                if NASA_MONTH[0] in possible_digits_for_d2 and NASA_MONTH[0] != digit1:
                    possible_digits_for_d2.remove(NASA_MONTH[0])
                if NASA_MONTH[1] in possible_digits_for_d2 and NASA_MONTH[1] != digit1:
                    possible_digits_for_d2.remove(NASA_MONTH[1])
                
                # Fallback if too many constraints
                if not possible_digits_for_d2:
                    possible_digits_for_d2 = [str(d) for d in range(10) if str(d) != digit1]
                    if not possible_digits_for_d2:
                        possible_digits_for_d2 = [str(random.randint(0, 9))]
                
                # Special handling for second digit if it's the first position in the code
                if idx2 == 0:  # If this placeholder is the first digit
                    digit2_choices = [d for d in possible_digits_for_d2 if int(d) % 2 == 0]
                    if not digit2_choices:  # Fallback if no even digit possible
                        digit2_choices = possible_digits_for_d2
                    digit2 = random.choice(digit2_choices if digit2_choices else ['0'])  # Fallback to '0'
                else:
                    digit2 = random.choice(possible_digits_for_d2)
                
                # Place digits into their positions
                code_list[idx1] = digit1
                code_list[idx2] = digit2
                
                # Form the final suggestion
                suggestion = ''.join(code_list)
                
                # Check if this is a new suggestion
                if suggestion not in self.suggested_codes:
                    # Add to memory and send
                    self.suggested_codes.add(suggestion)
                    await self._send('Generator', f'SUGGEST {suggestion}')
                    self.log('suggest', agent=self.name, code=suggestion, is_new=True, 
                             is_intelligent=True, attempt=attempt+1)
                    break
                else:
                    # Log that we skipped a duplicate suggestion
                    self.log('suggest', agent=self.name, code=suggestion, is_new=False,
                             attempt=attempt+1)
            # If we tried 5 times and still got duplicates, we don't send any suggestion this round
