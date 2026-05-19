"""Data harvester — download training data from public sources.

Sources:
  1. Simple English Wikipedia (manageable size, clean text)
  2. Hindi Wikipedia articles
  3. Sanskrit texts from Wikisource
  4. Code samples (Python/JS from GitHub README patterns)

Usage:
  python training/dataset/harvest_data.py --output data/training_data.jsonl --limit 10000
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

# Wikipedia API endpoints
_WIKI_API = {
    "en": "https://simple.wikipedia.org/w/api.php",
    "hi": "https://hi.wikipedia.org/w/api.php",
    "sa": "https://sa.wikipedia.org/w/api.php",
}


def _fetch_json(url: str, retries: int = 3) -> dict:
    """Fetch JSON from URL with retry."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AtulyaTantra/0.1 (training data)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning("Failed to fetch %s: %s", url[:80], e)
                return {}


def _clean_wiki_text(text: str) -> str:
    """Remove wiki markup and clean text."""
    text = re.sub(r"\{\{[^}]*\}\}", "", text)      # Remove templates
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)  # [[link|text]] → text
    text = re.sub(r"<[^>]+>", "", text)             # Remove HTML tags
    text = re.sub(r"==+\s*", "\n", text)            # Section headers → newlines
    text = re.sub(r"\n{3,}", "\n\n", text)          # Collapse blank lines
    text = re.sub(r"\s+", " ", text)                # Normalize whitespace
    return text.strip()


def harvest_wikipedia(
    lang: str = "en",
    limit: int = 1000,
    min_length: int = 200,
) -> list[dict]:
    """Harvest articles from Wikipedia.

    Args:
        lang: Language code (en, hi, sa).
        limit: Max articles to fetch.
        min_length: Minimum text length to keep.

    Returns:
        List of {instruction, output} dicts.
    """
    api_url = _WIKI_API.get(lang, _WIKI_API["en"])
    samples = []
    continue_token = None
    fetched = 0

    logger.info("Harvesting %s Wikipedia (limit=%d)...", lang, limit)

    while fetched < limit:
        params = {
            "action": "query",
            "format": "json",
            "generator": "random",
            "grnnamespace": "0",
            "grnlimit": str(min(50, limit - fetched)),
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "exlimit": "max",
        }
        if continue_token:
            params["grncontinue"] = continue_token

        url = api_url + "?" + urllib.parse.urlencode(params)
        data = _fetch_json(url)

        if not data or "query" not in data:
            break

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            title = page.get("title", "")
            extract = page.get("extract", "")
            if not extract or len(extract) < min_length:
                continue

            clean = _clean_wiki_text(extract)
            if len(clean) < min_length:
                continue

            # Create instruction/output pairs
            if lang == "hi":
                instruction = f"{title} क्या है? इसके बारे में बताइए।"
            elif lang == "sa":
                instruction = f"{title} किम्? विवरणं ददातु।"
            else:
                instruction = f"What is {title}? Explain in detail."

            samples.append({
                "instruction": instruction,
                "output": clean[:2000],  # Cap at 2000 chars
                "source": f"wikipedia_{lang}",
                "topic": title.lower().replace(" ", "_"),
            })
            fetched += 1

        continue_token = data.get("continue", {}).get("grncontinue")
        if not continue_token:
            break

        logger.info("  %s: %d/%d articles", lang, fetched, limit)
        time.sleep(0.5)  # Be polite to Wikipedia

    logger.info("Harvested %d articles from %s Wikipedia", len(samples), lang)
    return samples


def harvest_code_samples() -> list[dict]:
    """Generate basic code instruction/output pairs."""
    samples = [
        {"instruction": "Write a Python function to check if a number is prime.",
         "output": "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True\n\n# Examples:\n# is_prime(7)  → True\n# is_prime(10) → False",
         "source": "code", "topic": "python_algorithms"},
        {"instruction": "Write a function to find the factorial of a number.",
         "output": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n\n# Iterative version:\ndef factorial_iter(n):\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result",
         "source": "code", "topic": "python_algorithms"},
        {"instruction": "How do you sort a list in Python?",
         "output": "# Built-in sort (in-place):\nnumbers = [3, 1, 4, 1, 5, 9]\nnumbers.sort()  # [1, 1, 3, 4, 5, 9]\n\n# sorted() returns new list:\noriginal = [3, 1, 4]\nsorted_list = sorted(original)  # [1, 3, 4]\n\n# Custom sort:\npeople = [('Alice', 25), ('Bob', 20)]\npeople.sort(key=lambda x: x[1])  # Sort by age",
         "source": "code", "topic": "python_basics"},
        {"instruction": "Explain list comprehension in Python.",
         "output": "List comprehension is a concise way to create lists:\n\n# Basic: [expression for item in iterable]\nsquares = [x**2 for x in range(10)]  # [0, 1, 4, 9, ...]\n\n# With filter: [expression for item in iterable if condition]\nevens = [x for x in range(20) if x % 2 == 0]\n\n# Nested:\nmatrix = [[1,2],[3,4]]\nflat = [x for row in matrix for x in row]  # [1, 2, 3, 4]\n\n# With transformation:\nwords = ['hello', 'world']\nupper = [w.upper() for w in words]  # ['HELLO', 'WORLD']",
         "source": "code", "topic": "python_basics"},
        {"instruction": "Write a Python class for a stack data structure.",
         "output": "class Stack:\n    def __init__(self):\n        self._items = []\n    \n    def push(self, item):\n        self._items.append(item)\n    \n    def pop(self):\n        if self.is_empty():\n            raise IndexError('pop from empty stack')\n        return self._items.pop()\n    \n    def peek(self):\n        if self.is_empty():\n            raise IndexError('peek at empty stack')\n        return self._items[-1]\n    \n    def is_empty(self):\n        return len(self._items) == 0\n    \n    def size(self):\n        return len(self._items)",
         "source": "code", "topic": "data_structures"},
        {"instruction": "How does a binary search work?",
         "output": "Binary search finds an element in a sorted array by repeatedly dividing the search range in half.\n\ndef binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1  # Not found\n\n# Time: O(log n), Space: O(1)\n# For 1 million elements: max 20 comparisons",
         "source": "code", "topic": "algorithms"},
        {"instruction": "Write a Python function to read and write JSON files.",
         "output": "import json\n\n# Write JSON\ndata = {'name': 'Atulya', 'version': 1}\nwith open('config.json', 'w') as f:\n    json.dump(data, f, indent=2)\n\n# Read JSON\nwith open('config.json') as f:\n    loaded = json.load(f)\n\n# From/to string\njson_str = json.dumps(data)\nparsed = json.loads(json_str)",
         "source": "code", "topic": "python_io"},
        {"instruction": "Explain try/except error handling in Python.",
         "output": "try:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    print('Cannot divide by zero')\nexcept (TypeError, ValueError) as e:\n    print(f'Error: {e}')\nelse:\n    print('No errors occurred')\nfinally:\n    print('This always runs')\n\n# Custom exception:\nclass InvalidInputError(Exception):\n    pass\n\ndef validate(x):\n    if x < 0:\n        raise InvalidInputError(f'Expected positive, got {x}')",
         "source": "code", "topic": "python_basics"},
    ]
    return samples


def harvest_huggingface(
    dataset_name: str = "databricks/databricks-dolly-15k",
    split: str = "train",
    limit: int = 5000,
    instruction_col: str = "instruction",
    output_col: str = "response",
) -> list[dict]:
    """Download and format a HuggingFace dataset.

    Popular open-source datasets:
      - databricks/databricks-dolly-15k (15K instruction pairs)
      - tatsu-lab/alpaca (52K instruction pairs)
      - HuggingFaceH4/no_robots (10K curated pairs)
      - iamtarun/python_code_instructions_18k_alpaca (18K code)

    Args:
        dataset_name: HuggingFace dataset identifier.
        split: Dataset split to use.
        limit: Max samples to take.
        instruction_col: Column name for instruction.
        output_col: Column name for output.

    Returns:
        List of {instruction, output} dicts.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("Install datasets: pip install datasets")
        return []

    logger.info("Downloading HF dataset: %s (limit=%d)...", dataset_name, limit)

    try:
        ds = load_dataset(dataset_name, split=split, trust_remote_code=True)
    except Exception as e:
        logger.error("Failed to load %s: %s", dataset_name, e)
        return []

    samples = []
    cols = ds.column_names

    # Auto-detect column names
    inst_col = instruction_col if instruction_col in cols else None
    out_col = output_col if output_col in cols else None

    # Common column name variants
    for candidate in ["instruction", "input", "question", "prompt", "text"]:
        if not inst_col and candidate in cols:
            inst_col = candidate
    for candidate in ["response", "output", "answer", "completion", "text"]:
        if not out_col and candidate in cols:
            out_col = candidate

    if not inst_col or not out_col:
        logger.warning("Could not auto-detect columns in %s. Columns: %s", dataset_name, cols)
        # Try using "text" as combined field
        if "text" in cols:
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                text = str(row["text"]).strip()
                if len(text) > 50:
                    samples.append({
                        "instruction": text[:200],
                        "output": text[200:] if len(text) > 200 else text,
                        "source": f"hf_{dataset_name.split('/')[-1]}",
                    })
            logger.info("Loaded %d samples from %s (text column)", len(samples), dataset_name)
            return samples
        return []

    for i, row in enumerate(ds):
        if i >= limit:
            break

        inst = str(row.get(inst_col, "")).strip()
        out = str(row.get(out_col, "")).strip()

        if not inst or not out or len(out) < 20:
            continue

        # Add context if available
        context = ""
        if "context" in cols:
            context = str(row.get("context", "")).strip()

        sample = {
            "instruction": inst,
            "output": out[:2000],
            "source": f"hf_{dataset_name.split('/')[-1]}",
        }
        if context:
            sample["context"] = context[:500]

        samples.append(sample)

    logger.info("Loaded %d samples from %s", len(samples), dataset_name)
    return samples


# Pre-configured dataset recipes
DATASET_RECIPES = {
    "dolly": ("databricks/databricks-dolly-15k", "train", 15000, "instruction", "response"),
    "alpaca": ("tatsu-lab/alpaca", "train", 52000, "instruction", "output"),
    "code": ("iamtarun/python_code_instructions_18k_alpaca", "train", 18000, "instruction", "output"),
    "hindi_qa": ("HydraIndicLM/hindi_alpaca_dolly_67k", "train", 10000, "instruction", "output"),
}


def harvest_all(
    output_path: str | Path = "data/training_data.jsonl",
    en_limit: int = 2000,
    hi_limit: int = 500,
    sa_limit: int = 200,
    hf_datasets: list[str] | None = None,
) -> Path:
    """Harvest all sources and write to JSONL.

    Args:
        output_path: Output file path.
        en_limit: English Wikipedia articles.
        hi_limit: Hindi Wikipedia articles.
        sa_limit: Sanskrit Wikipedia articles.
        hf_datasets: List of HF dataset recipe names to include.

    Returns:
        Path to output file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    all_samples = []

    # English Wikipedia
    en_samples = harvest_wikipedia("en", en_limit)
    all_samples.extend(en_samples)

    # Hindi Wikipedia
    hi_samples = harvest_wikipedia("hi", hi_limit)
    all_samples.extend(hi_samples)

    # Sanskrit Wikipedia
    sa_samples = harvest_wikipedia("sa", sa_limit)
    all_samples.extend(sa_samples)

    # Code samples
    code_samples = harvest_code_samples()
    all_samples.extend(code_samples)

    # HuggingFace datasets
    if hf_datasets:
        for name in hf_datasets:
            if name in DATASET_RECIPES:
                ds_name, split, limit, inst_col, out_col = DATASET_RECIPES[name]
                hf_samples = harvest_huggingface(ds_name, split, limit, inst_col, out_col)
            else:
                # Treat as direct HF dataset name
                hf_samples = harvest_huggingface(name)
            all_samples.extend(hf_samples)

    # Also include seed dataset samples
    try:
        from training.dataset.build_dataset import _KNOWLEDGE, _CONVERSATIONS
        all_samples.extend(_KNOWLEDGE)
        all_samples.extend(_CONVERSATIONS)
        logger.info("Added %d seed samples", len(_KNOWLEDGE) + len(_CONVERSATIONS))
    except ImportError:
        pass

    # Write
    with open(path, "w", encoding="utf-8") as f:
        for record in all_samples:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("Total: %d samples written to %s", len(all_samples), path)

    # Print breakdown
    sources = {}
    for s in all_samples:
        src = s.get("source", "seed")
        sources[src] = sources.get(src, 0) + 1
    for src, count in sorted(sources.items()):
        logger.info("  %s: %d samples", src, count)

    return path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    parser = argparse.ArgumentParser(description="Harvest training data")
    parser.add_argument("--output", default="data/training_data.jsonl")
    parser.add_argument("--en", type=int, default=2000, help="English Wikipedia articles")
    parser.add_argument("--hi", type=int, default=500, help="Hindi Wikipedia articles")
    parser.add_argument("--sa", type=int, default=200, help="Sanskrit Wikipedia articles")
    parser.add_argument("--hf", nargs="*", default=None,
                        help="HuggingFace datasets: dolly alpaca code hindi_qa (or any HF dataset name)")

    args = parser.parse_args()
    harvest_all(args.output, args.en, args.hi, args.sa, args.hf)

