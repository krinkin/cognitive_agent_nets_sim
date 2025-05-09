
import random

def even_first_digit(code:str)->bool:
    return int(code[0])%2==0

def exactly_two_repeats(code:str)->bool:
    return len(set(code))==3 and any(code.count(d)==2 for d in set(code))

NASA_MONTH='07'
def semantic_contains_nasa_month(code:str)->bool:
    return NASA_MONTH in code

FORMAL=[even_first_digit, exactly_two_repeats]
SEMANTIC=[semantic_contains_nasa_month]

def sample_constraints():
    formal   = random.choice(FORMAL)          # ← только ОДНО
    semantic = random.choice(SEMANTIC)
    return (formal, semantic)


