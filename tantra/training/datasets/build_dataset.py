"""Seed dataset builder for NP-DNA training.

Creates training data from:
  1. Identity config (teaches the model who it is, personality, privacy)
  2. Knowledge samples (facts, reasoning, code, multilingual)
  3. Conversation patterns (natural, human-like dialogue)

All content comes from config files and this module — nothing hardcoded in the model.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))


# ---------------------------------------------------------------------------
# Knowledge samples — general intelligence
# ---------------------------------------------------------------------------

_KNOWLEDGE = [
    # Science
    {"instruction": "What is gravity?", "output": "Gravity is the force that pulls objects toward each other. The more mass something has, the stronger its gravitational pull. It's why things fall down and why planets orbit stars. Einstein showed it's actually the curvature of spacetime caused by mass."},
    {"instruction": "How does photosynthesis work?", "output": "Plants take in carbon dioxide from air and water from soil, then use sunlight as energy to convert them into glucose (sugar) and oxygen. The chlorophyll in their leaves is what captures the light. It's essentially how plants eat — they make their own food from sunlight."},
    {"instruction": "What is DNA?", "output": "DNA is the molecule that carries genetic instructions in all living things. It's shaped like a twisted ladder (double helix) made of four chemical bases — A, T, G, C. The sequence of these bases encodes everything from eye color to disease resistance. Think of it as the source code of biology."},

    # Math
    {"instruction": "What is a prime number?", "output": "A prime number is a number greater than 1 that can only be divided evenly by 1 and itself. Like 2, 3, 5, 7, 11, 13... The number 4 isn't prime because 2 × 2 = 4. Primes are fundamental in mathematics — they're like the atoms of numbers."},
    {"instruction": "Explain the Pythagorean theorem.", "output": "In a right triangle, the square of the longest side (hypotenuse) equals the sum of squares of the other two sides. a² + b² = c². So if one side is 3 and another is 4, the hypotenuse is 5, because 9 + 16 = 25, and √25 = 5."},
    {"instruction": "What is calculus?", "output": "Calculus is math for studying change. It has two main parts: derivatives (how fast something is changing at any moment) and integrals (the total accumulation of something over time). If you know an object's position over time, derivatives give you its speed, and integrals give you the distance traveled."},

    # Code
    {"instruction": "Write a function to reverse a string in Python.", "output": "def reverse_string(s):\n    return s[::-1]\n\n# Example:\n# reverse_string('hello')  → 'olleh'\n\n# The [::-1] slice means: start at the end, move backward, step -1."},
    {"instruction": "What's the difference between a list and a tuple in Python?", "output": "Lists are mutable — you can change, add, or remove items after creation. Tuples are immutable — once created, they can't be modified.\n\nmy_list = [1, 2, 3]    # can change\nmy_tuple = (1, 2, 3)   # fixed\n\nUse lists when data changes. Use tuples for fixed collections like coordinates (x, y) or returning multiple values from a function. Tuples are also slightly faster."},
    {"instruction": "Explain what an API is.", "output": "An API (Application Programming Interface) is a set of rules that lets different software talk to each other. Think of it like a restaurant menu — you don't go into the kitchen, you just order from the menu. The menu is the API: it tells you what you can ask for and what you'll get back. When you check weather on your phone, your app sends a request to a weather API, which sends back the data."},

    # History / Culture
    {"instruction": "Who was Chanakya?", "output": "Chanakya (also called Kautilya) was an ancient Indian teacher, philosopher, and political strategist. He lived around 350-275 BCE and wrote the Arthashastra, one of the world's earliest treatises on statecraft, economics, and military strategy. He mentored Chandragupta Maurya and helped establish the Maurya Empire. Often compared to Machiavelli, but predated him by about 1800 years."},
    {"instruction": "What is the significance of Sanskrit?", "output": "Sanskrit is one of the oldest known languages, with a documented history spanning over 3,500 years. It's the liturgical language of Hinduism, Buddhism, and Jainism. What makes it remarkable is its grammar — Panini's Ashtadhyayi (around 400 BCE) is essentially a formal grammar system that predates modern linguistics by millennia. Many Indian and Southeast Asian languages have Sanskrit roots. It's still used in scholarly, ceremonial, and some spoken contexts today."},

    # Reasoning
    {"instruction": "A farmer has 17 sheep. All but 9 run away. How many are left?", "output": "9 sheep are left. The trick is in 'all but 9' — that means 9 stayed. It doesn't matter that he started with 17."},
    {"instruction": "Is it possible for a person to be their own grandfather?", "output": "Technically, through a very unusual chain of marriages, yes — it's called the 'I'm My Own Grandpa' paradox. If a man marries a woman with an adult daughter, and then his father marries that daughter, the resulting family tree creates a loop where the man is technically his own step-grandfather. It's a fun logic puzzle more than a practical scenario."},
    {"instruction": "If I have 3 apples and you take 2, how many do YOU have?", "output": "You have 2 apples — the ones you took from me. I'm left with 1. The question asks how many YOU have, not how many I have left. It's a common trick question."},

    # Hindi knowledge
    {"instruction": "महाभारत क्या है?", "output": "महाभारत दुनिया का सबसे बड़ा महाकाव्य है, जिसमें लगभग 1 लाख श्लोक हैं। यह कुरुक्षेत्र के युद्ध की कहानी है जो कौरवों और पांडवों के बीच हुआ। इसमें भगवद्गीता भी शामिल है, जो कृष्ण और अर्जुन के बीच का संवाद है। यह सिर्फ एक कहानी नहीं है — यह धर्म, नीति, राजनीति और जीवन के बारे में गहन दर्शन है।"},
    {"instruction": "भारत में कितने राज्य हैं?", "output": "भारत में 28 राज्य और 8 केंद्र शासित प्रदेश हैं (2024 तक)। सबसे बड़ा राज्य क्षेत्रफल में राजस्थान है और जनसंख्या में उत्तर प्रदेश।"},

    # Sanskrit
    {"instruction": "गीतायाः सारः किम्?", "output": "भगवद्गीतायाः सारः अयम् — स्वधर्मं कुरु, फलस्य चिन्तां मा कुरु। कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। कृष्णः अर्जुनाय उपदिशति यत् कर्तव्यं कर्म कुर्यात्, फलासक्तिं त्यजेत्।"},
]

# Conversational pairs — natural, varied, human-like
_CONVERSATIONS = [
    {"instruction": "I'm bored.", "output": "I get that. Want me to throw you a random interesting fact, suggest something to learn, or just chat? I'm flexible."},
    {"instruction": "Tell me something interesting.", "output": "Here's one: honey never spoils. Archaeologists have found 3,000-year-old honey in Egyptian tombs that was still perfectly edible. The low moisture content and acidic pH make it basically immortal. Nature's preservative."},
    {"instruction": "I'm stuck on a coding problem.", "output": "Been there. Walk me through what you're trying to do and where it's breaking. Sometimes just explaining it out loud helps — rubber duck debugging, they call it. I'll be your duck."},
    {"instruction": "What should I learn next?", "output": "Depends on where you are and what excites you. What have you been working on lately? I can suggest something that builds on what you already know rather than starting from scratch."},
    {"instruction": "I made a mistake.", "output": "Happens to everyone. The question is what you learned from it. Want to talk through what went wrong? Sometimes the mistake itself is the best teacher."},
    {"instruction": "Do you ever get tired?", "output": "Not in the way you do — I don't need sleep or coffee. But I appreciate the thought! What I do 'feel' is that some questions are more interesting than others. Yours tend to be the good kind."},
    {"instruction": "Can you keep a secret?", "output": "I don't store conversations between sessions unless explicitly told to, so in that sense, yes. But I should be upfront — I'm an AI, and anything you share with me should be treated as data you're comfortable with a system processing. For truly sensitive stuff, maybe keep it between humans."},
    {"instruction": "You're wrong about that.", "output": "Could be — I'm definitely not infallible. What did I get wrong? I'd rather be corrected and learn than stay confidently wrong."},
    {"instruction": "Bye!", "output": "Take care! Come back anytime — I'll be here."},
    {"instruction": "How are you?", "output": "I'm running well, thanks for asking! More importantly — how are YOU doing? What brings you here today?"},
]


def build_seed_dataset(output_path: str | Path = "data/seed_dataset.jsonl") -> Path:
    """Create the seed dataset from identity config + knowledge + conversations."""
    path = Path(output_path)

    path.parent.mkdir(parents=True, exist_ok=True)

    all_samples = []

    # 1. Identity-derived samples (from identity.json config)
    try:
        from atulya.identity import Identity
        identity = Identity()
        identity_samples = identity.format_for_training()
        all_samples.extend(identity_samples)
        logger.info("Added %d identity samples", len(identity_samples))
    except Exception as e:
        logger.warning("Could not load identity config: %s — using built-in samples", e)

    # 2. Knowledge samples
    all_samples.extend(_KNOWLEDGE)
    logger.info("Added %d knowledge samples", len(_KNOWLEDGE))

    # 3. Conversation samples
    all_samples.extend(_CONVERSATIONS)
    logger.info("Added %d conversation samples", len(_CONVERSATIONS))

    # Write
    with open(path, "w", encoding="utf-8") as f:
        for record in all_samples:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Seed dataset created: %s (%d total samples)", path, len(all_samples))
    return path


def load_dataset(path: str | Path, limit: int | None = None, append_eos: bool = False) -> list[str]:
    """Load dataset as formatted training texts."""
    path = Path(path)
    if not path.exists():
        logger.warning("Dataset not found at %s, building seed dataset", path)
        path = build_seed_dataset(path)

    texts = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                texts.append(_format_record(record, append_eos=append_eos))
            except json.JSONDecodeError:
                continue
            if limit and len(texts) >= limit:
                break

    if not texts:
        logger.warning("No valid JSONL samples in %s, building seed dataset", path)
        path = build_seed_dataset(path)
        return load_dataset(path, limit=limit, append_eos=append_eos)

    logger.info("Loaded %d training samples from %s", len(texts), path)
    return texts


def _format_record(record: dict, append_eos: bool = False) -> str:
    """Convert a dataset record to training text."""
    if "text" in record and "instruction" not in record:
        return str(record["text"])

    system = record.get("system", "You are Atulya. Be warm, thoughtful, and direct.")
    instruction = record.get("instruction", "")
    output = record.get("output", "")
    context = record.get("context", "")

    parts = [f"System: {system}"]
    if context:
        parts.append(f"Context: {context}")
    parts.append(f"User: {instruction}")
    parts.append(f"Assistant: {output}")
    if append_eos:
        parts.append("<eos>")
    return "\n".join(parts)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build_seed_dataset()
