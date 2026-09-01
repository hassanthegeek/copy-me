import random
from typing import List

# ---- Drawing Prompts ----
# 25+ various items that can be drawn and guessed
WORD_LIST: List[str] = [
    # Animals
    "cat",
    "dog",
    "fish",
    "bird",
    "horse",
    "elephant",
    "lion",
    "rabbit",
    "turtle",
    "snake",
    
    # Objects
    "house",
    "tree",
    "car",
    "bicycle",
    "airplane",
    "boat",
    "umbrella",
    "lamp",
    "clock",
    "book",
    
    # Food
    "pizza",
    "apple",
    "banana",
    "cake",
    "ice cream",
    
    # Nature
    "sun",
    "moon",
    "star",
    "cloud",
    "rain",
    
    # People & Things
    "robot",
    "ghost",
    "crown",
    "sword",
    "diamond",
]


def get_random_prompt(used_prompts: List[str] = None) -> str:
    """Get a random prompt that hasn't been used yet."""
    available = [w for w in WORD_LIST if w not in (used_prompts or [])]
    if not available:
        # All words used, reset
        available = WORD_LIST.copy()
    return random.choice(available)


def get_all_prompts() -> List[str]:
    """Get the full word list."""
    return WORD_LIST.copy()
