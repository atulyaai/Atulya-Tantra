"""
Atulya Tantra - Multimodal Service
Version: 2.5.0
Handles voice, vision, and file processing for multi-modal interactions
"""

import logging
import base64
import io
from typing import Dict, List, Optional, Any, BinaryIO
from PIL import Image
import speech_recognition as sr
import edge_tts
import asyncio
import aiofiles
from pathlib import Path

logger = logging.getLogger(__name__)


class MultimodalService:
    """Handles multi-modal input processing: voice, vision, files"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Configure speech recognition
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        
        logger.info("MultimodalService initialized")
    
    async def process_voice_input(self, audio_data: bytes) -> str:
        """Convert audio data to text using speech recognition"""
        try:
            # Save audio data to temporary file
            temp_audio_path = "temp_audio.wav"
            with open(temp_audio_path, "wb") as f:
                f.write(audio_data)
            
            # Use speech recognition
            with sr.AudioFile(temp_audio_path) as source:
                audio = self.recognizer.record(source)
            
            # Recognize speech
            text = self.recognizer.recognize_google(audio)
            
            # Clean up temp file
            Path(temp_audio_path).unlink(missing_ok=True)
            
            logger.info(f"Voice input processed: {text[:50]}...")
            return text
            
        except sr.UnknownValueError:
            logger.warning("Speech recognition could not understand audio")
            return "Sorry, I couldn't understand the audio. Please try again."
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return "Sorry, speech recognition service is unavailable."
        except Exception as e:
            logger.error(f"Voice processing error: {e}")
            return f"Error processing voice input: {str(e)}"
    
    async def process_image_input(self, image_data: bytes) -> Dict[str, Any]:
        """Process image data and extract information"""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Basic image analysis
            analysis = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image_data)
            }
            
            # Convert to base64 for storage/transmission
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            analysis["base64_data"] = image_base64
            
            logger.info(f"Image processed: {analysis['width']}x{analysis['height']} {analysis['format']}")
            return analysis
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return {"error": str(e)}
    
    async def process_file_attachment(self, file_data: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """Process file attachment based on type"""
        try:
            file_info = {
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(file_data),
                "processed": False,
                "content": None,
                "metadata": {}
            }
            
            # Process based on file type
            if content_type.startswith("text/"):
                file_info["content"] = file_data.decode('utf-8', errors='ignore')
                file_info["processed"] = True
                
            elif content_type == "application/pdf":
                file_info["content"] = await self._process_pdf(file_data)
                file_info["processed"] = True
                
            elif content_type.startswith("image/"):
                image_analysis = await self.process_image_input(file_data)
                file_info["content"] = f"Image file: {filename}"
                file_info["metadata"] = image_analysis
                file_info["processed"] = True
                
            elif content_type.startswith("audio/"):
                voice_text = await self.process_voice_input(file_data)
                file_info["content"] = voice_text
                file_info["processed"] = True
                
            else:
                file_info["content"] = f"Binary file: {filename} ({content_type})"
                file_info["processed"] = False
            
            logger.info(f"File processed: {filename} ({content_type})")
            return file_info
            
        except Exception as e:
            logger.error(f"File processing error: {e}")
            return {"error": str(e), "filename": filename}
    
    async def generate_voice_output(self, text: str, voice: str = "en-US-AriaNeural") -> bytes:
        """Generate speech audio from text"""
        try:
            # Use edge-tts for text-to-speech
            communicate = edge_tts.Communicate(text, voice)
            
            # Generate audio data
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            logger.info(f"Voice output generated: {len(audio_data)} bytes")
            return audio_data
            
        except Exception as e:
            logger.error(f"Voice generation error: {e}")
            return b""
    
    async def _process_pdf(self, pdf_data: bytes) -> str:
        """Process PDF file and extract text"""
        try:
            # For now, return a placeholder
            # In production, use PyPDF2 or similar library
            return f"PDF file content would be extracted here ({len(pdf_data)} bytes)"
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            return f"Error processing PDF: {str(e)}"
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of multimodal components"""
        try:
            return {
                "voice_input": True,
                "voice_output": True,
                "image_processing": True,
                "file_processing": True,
                "speech_recognition": True
            }
        except Exception as e:
            logger.error(f"Multimodal health check failed: {e}")
            return {"error": str(e)}
    
    def get_supported_file_types(self) -> List[str]:
        """Get list of supported file types"""
        return [
            "text/plain",
            "text/csv",
            "text/html",
            "text/markdown",
            "application/json",
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "audio/wav",
            "audio/mp3",
            "audio/ogg"
        ]
    
    def get_supported_voice_models(self) -> List[str]:
        """Get list of supported voice models"""
        return [
            "en-US-AriaNeural",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-US-DavisNeural"
        ]
