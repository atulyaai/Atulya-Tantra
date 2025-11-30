
import logging
import re
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class MemoryExtractor:
    """
    Extracts structured facts and preferences from conversation.
    Uses heuristics/regex for now (can be upgraded to LLM later).
    """
    
    def __init__(self):
        self.preference_patterns = [
            (r"i like (.+)", "likes"),
            (r"i love (.+)", "loves"),
            (r"i prefer (.+)", "prefers"),
            (r"my favorite (.+) is (.+)", "favorite"),
        ]
        
        self.fact_patterns = [
            (r"my name is (.+)", "name"),
            (r"i am (.+)", "identity"),
            (r"i live in (.+)", "location"),
            (r"i work as (.+)", "job"),
        ]

    def extract_from_message(self, user_text: str) -> List[Tuple[str, str, str]]:
        """
        Extract facts/preferences from user message
        
        Returns:
            List of (type, key/category, value)
            e.g. [("preference", "likes", "pizza"), ("fact", "name", "Atulya")]
        """
        extracted = []
        text_lower = user_text.lower().strip()
        
        # Check preferences
        for pattern, category in self.preference_patterns:
            match = re.search(pattern, text_lower)
            if match:
                if category == "favorite":
                    # "my favorite color is blue" -> key="color", value="blue"
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    extracted.append(("preference", key, value))
                else:
                    # "i like pizza" -> key="likes", value="pizza"
                    value = match.group(1).strip()
                    extracted.append(("preference", category, value))
                    
        # Check facts
        for pattern, category in self.fact_patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip()
                extracted.append(("fact", category, value))
                
        if extracted:
            logger.info(f"Extracted memory: {extracted}")
            
        return extracted
