import random

# ---------- formal rules ----------
def even_first_digit(code: str) -> bool:
    return int(code[0]) % 2 == 0

def exactly_two_repeats(code: str) -> bool:
    return len(set(code)) == 3 and any(code.count(d) == 2 for d in set(code))

FORMAL = [even_first_digit, exactly_two_repeats]

# ---------- semantic rule ----------
NASA_MONTH = "07"

def semantic_contains_nasa_month(code: str) -> bool:
    return NASA_MONTH in code

SEMANTIC = [semantic_contains_nasa_month]

# ---------- sample constraints ----------
def sample_constraints():
    # Select two formal constraints and one semantic constraint
    formal1, formal2 = random.sample(FORMAL, 2)   # Select 2 formal constraints
    semantic         = random.choice(SEMANTIC)
    return (formal1, formal2, semantic)
