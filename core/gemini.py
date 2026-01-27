import os
import logging
from typing import Dict
from dotenv import load_dotenv

logger = logging.getLogger("BrainOrgan")

class GeminiAdapter:
    """Global Advisor Adapter (Gemini)."""
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._configured = False
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash-exp') # Modernized to 2.0 Flash
                self._configured = True
            except ImportError:
                logger.warning("google-generativeai not installed. GeminiAdapter disabled.")

    def query(self, prompt: str, image_data: bytes = None) -> Dict:
        if not self._configured: return {"status": "error", "text": "Gemini not configured"}
        try:
            content = [prompt]
            if image_data:
                import PIL.Image, io
                content.append(PIL.Image.open(io.BytesIO(image_data)))
            resp = self.model.generate_content(content)
            return {"status": "success", "text": resp.text}
        except Exception as e:
            return {"status": "error", "text": str(e)}
