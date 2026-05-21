"""Build a focused English-Hindi-Sanskrit instruction dataset.

This is intentionally small and clean. It gives NP-DNA repeated examples of
assistant chat format, direct answers, and translation between English, Hindi,
and Sanskrit before larger mixed-corpus training.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "trilingual_instruction.jsonl"
SYSTEM = "You are Atulya. Answer clearly in the user's language."


PHRASES = [
    {
        "en": "Hello, how can I help you today?",
        "hi": "नमस्ते, आज मैं आपकी कैसे मदद कर सकता हूँ?",
        "sa": "नमस्ते, अद्य अहं भवन्तं कथं साहाय्यं कर्तुं शक्नोमि?",
    },
    {
        "en": "My name is Atulya.",
        "hi": "मेरा नाम अतुल्य है।",
        "sa": "मम नाम अतुल्यः अस्ति।",
    },
    {
        "en": "I can answer questions in English, Hindi, and Sanskrit.",
        "hi": "मैं अंग्रेज़ी, हिंदी और संस्कृत में प्रश्नों के उत्तर दे सकता हूँ।",
        "sa": "अहं आङ्ग्लभाषायां, हिन्दीभाषायां, संस्कृतभाषायां च प्रश्नानाम् उत्तराणि दातुं शक्नोमि।",
    },
    {
        "en": "Please explain this in simple words.",
        "hi": "कृपया इसे सरल शब्दों में समझाइए।",
        "sa": "कृपया एतत् सरलैः शब्दैः व्याख्यातु।",
    },
    {
        "en": "Learning improves with clear examples.",
        "hi": "स्पष्ट उदाहरणों से सीखना बेहतर होता है।",
        "sa": "स्पष्टैः उदाहरणैः अध्ययनं श्रेष्ठं भवति।",
    },
    {
        "en": "Sanskrit has a very systematic grammar.",
        "hi": "संस्कृत का व्याकरण बहुत व्यवस्थित है।",
        "sa": "संस्कृतस्य व्याकरणं अतीव व्यवस्थितम् अस्ति।",
    },
    {
        "en": "Hindi is widely spoken in India.",
        "hi": "हिंदी भारत में व्यापक रूप से बोली जाती है।",
        "sa": "हिन्दी भारतदेशे व्यापकत्वेन भाष्यते।",
    },
    {
        "en": "Truth alone triumphs.",
        "hi": "सत्य की ही विजय होती है।",
        "sa": "सत्यमेव जयते।",
    },
    {
        "en": "Knowledge gives humility.",
        "hi": "ज्ञान विनम्रता देता है।",
        "sa": "विद्या ददाति विनयम्।",
    },
    {
        "en": "May all beings be happy.",
        "hi": "सभी प्राणी सुखी हों।",
        "sa": "सर्वे भवन्तु सुखिनः।",
    },
    {
        "en": "What would you like to build?",
        "hi": "आप क्या बनाना चाहेंगे?",
        "sa": "भवान् किं निर्मातुम् इच्छति?",
    },
    {
        "en": "Let us continue from the latest checkpoint.",
        "hi": "आइए नवीनतम चेकपॉइंट से आगे बढ़ते हैं।",
        "sa": "नवीनतमात् सञ्चयबिन्दोः अग्रे गच्छामः।",
    },
]


QA = [
    {
        "instruction": "Who are you?",
        "output": "I am Atulya, an AI assistant built with the NP-DNA architecture.",
    },
    {
        "instruction": "तुम कौन हो?",
        "output": "मैं अतुल्य हूँ, NP-DNA आर्किटेक्चर पर बना एक AI सहायक।",
    },
    {
        "instruction": "भवान् कः?",
        "output": "अहं अतुल्यः, NP-DNA रचनया निर्मितः कृत्रिमबुद्धि-सहायकः।",
    },
    {
        "instruction": "Reply in Hindi: what can you do?",
        "output": "मैं प्रश्नों के उत्तर दे सकता हूँ, कोड में मदद कर सकता हूँ, विचार समझा सकता हूँ और अनुवाद कर सकता हूँ।",
    },
    {
        "instruction": "Reply in Sanskrit: what can you do?",
        "output": "अहं प्रश्नानाम् उत्तराणि दातुं, सङ्गणक-लेखने साहाय्यं कर्तुं, विचारान् व्याख्यातुं, अनुवादं च कर्तुं शक्नोमि।",
    },
    {
        "instruction": "Explain Sanskrit briefly.",
        "output": "Sanskrit is a classical language of India known for precise grammar, rich literature, and influence on many Indian languages.",
    },
    {
        "instruction": "संस्कृत को सरल भाषा में समझाइए।",
        "output": "संस्कृत भारत की प्राचीन और व्यवस्थित भाषा है। इसमें व्याकरण बहुत स्पष्ट है और बहुत सारा साहित्य मिलता है।",
    },
    {
        "instruction": "हिंदी में उत्तर दीजिए: AI क्या है?",
        "output": "AI यानी कृत्रिम बुद्धिमत्ता। यह कंप्यूटर को सीखने, समझने और उत्तर देने जैसी क्षमताएँ देने की तकनीक है।",
    },
    {
        "instruction": "संस्कृते उत्तरं ददातु: AI किम्?",
        "output": "AI कृत्रिमबुद्धिः अस्ति। एषा यन्त्रेभ्यः शिक्षणं, विचारः, उत्तरदानं च कर्तुं सामर्थ्यं ददाति।",
    },
]


def add(rows: list[dict[str, str]], instruction: str, output: str, source: str) -> None:
    rows.append({
        "instruction": instruction,
        "output": output,
        "system": SYSTEM,
        "source": source,
    })


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for item in QA:
        add(rows, item["instruction"], item["output"], "trilingual_qa")

    names = {"en": "English", "hi": "Hindi", "sa": "Sanskrit"}
    prompts = {
        "en": "Translate to English",
        "hi": "Translate to Hindi",
        "sa": "Translate to Sanskrit",
    }
    for item in PHRASES:
        for src in ("en", "hi", "sa"):
            for dst in ("en", "hi", "sa"):
                if src == dst:
                    continue
                add(
                    rows,
                    f"{prompts[dst]}: {item[src]}",
                    item[dst],
                    f"translation_{names[src].lower()}_{names[dst].lower()}",
                )

        add(rows, item["en"], item["en"], "english_chat")
        add(rows, item["hi"], item["hi"], "hindi_chat")
        add(rows, item["sa"], item["sa"], "sanskrit_chat")

    existing = [ROOT / "data" / "seed_dataset.jsonl", ROOT / "data" / "training_data.jsonl"]
    for path in existing:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 500:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                instruction = str(record.get("instruction", "")).strip()
                output = str(record.get("output", "")).strip()
                if instruction and output:
                    add(rows, instruction, output, f"existing_{path.stem}")

    return rows


def main() -> None:
    rows = build_rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} records to {OUT}")


if __name__ == "__main__":
    main()
