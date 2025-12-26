"""
Phase B: Whisper-Large-v3-Turbo Interface
Real-time audio transcription with confidence scoring.

Features:
- Lazy model loading (only on first voice input)
- PTT buffer processing (16kHz, mono)
- Confidence scoring for transcriptions
- TraceID logging for audio events
"""

import logging
import uuid
from typing import Tuple, Dict, Optional
from pathlib import Path

logger = logging.getLogger("WhisperInterface")


class WhisperInterface:
    """
    Production Whisper-Large-v3-Turbo interface for voice transcription.
    """
    
    def __init__(self, model_name: str = "large-v3-turbo"):
        """
        Initialize Whisper interface.
        
        Args:
            model_name: Whisper model variant (tiny, base, small, medium, large-v3-turbo)
        """
        self.model_name = model_name
        self.model = None
        self.logger = logger
        
    def load(self) -> bool:
        """
        Load Whisper model with lazy initialization.
        Returns True if successful, False otherwise.
        """
        if self.model is not None:
            return True
            
        try:
            trace_id = self._generate_trace_id()
            self.logger.info(f"[{trace_id}] Loading Whisper {self.model_name}...")
            
            # Import Whisper (lazy to avoid dependency issues)
            try:
                import whisper
            except ImportError:
                self.logger.error(f"[{trace_id}] Whisper not installed. Run: pip install openai-whisper")
                return False
            
            # Load model
            import time
            start_time = time.time()
            self.model = whisper.load_model(self.model_name)
            load_time = time.time() - start_time
            
            self.logger.info(f"[{trace_id}] Whisper loaded in {load_time:.2f}s")
            return True
            
        except Exception as e:
            self.logger.error(f"[{trace_id}] Whisper loading failed: {str(e)}")
            return False
    
    def transcribe(
        self,
        audio_data,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Tuple[str, float, Dict]:
        """
        Transcribe audio with confidence scoring.
        
        Args:
            audio_data: Audio array (numpy) or file path
            language: Language code (None for auto-detect)
            task: 'transcribe' or 'translate'
            
        Returns:
            (transcription_text, confidence, metadata)
        """
        trace_id = self._generate_trace_id()
        
        if not self.load():
            return "ERROR: Whisper not loaded", 0.0, {"trace_id": trace_id, "error": "load_failed"}
        
        try:
            import time
            start_time = time.time()
            
            # Run transcription
            result = self.model.transcribe(
                audio_data,
                language=language,
                task=task,
                fp16=False,  # CPU compatibility
                verbose=False
            )
            
            transcription = result.get("text", "").strip()
            detected_language = result.get("language", "unknown")
            
            # Calculate confidence from segment probabilities
            segments = result.get("segments", [])
            if segments:
                avg_logprob = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
                # Convert log probability to confidence (0-1)
                import math
                confidence = min(1.0, max(0.0, math.exp(avg_logprob)))
            else:
                confidence = 0.5  # Default if no segments
            
            transcription_time = time.time() - start_time
            
            metadata = {
                "trace_id": trace_id,
                "transcription_time_ms": int(transcription_time * 1000),
                "detected_language": detected_language,
                "num_segments": len(segments),
                "model": f"whisper-{self.model_name}"
            }
            
            self.logger.info(
                f"[{trace_id}] Transcription complete: '{transcription[:50]}...', "
                f"{transcription_time*1000:.0f}ms, confidence={confidence:.3f}"
            )
            
            return transcription, confidence, metadata
            
        except Exception as e:
            self.logger.error(f"[{trace_id}] Transcription failed: {str(e)}")
            return f"ERROR: {str(e)}", 0.0, {"trace_id": trace_id, "error": str(e)}
    
    def transcribe_file(self, audio_path: str, **kwargs) -> Tuple[str, float, Dict]:
        """
        Transcribe audio from file path.
        
        Args:
            audio_path: Path to audio file
            **kwargs: Additional arguments for transcribe()
            
        Returns:
            (transcription_text, confidence, metadata)
        """
        if not Path(audio_path).exists():
            return f"ERROR: File not found: {audio_path}", 0.0, {"error": "file_not_found"}
        
        return self.transcribe(audio_path, **kwargs)
    
    def _generate_trace_id(self) -> str:
        """Generate 8-char TraceID for auditability."""
        return uuid.uuid4().hex[:8]
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Get current memory footprint."""
        import sys
        
        model_size = sys.getsizeof(self.model) if self.model else 0
        
        return {
            "model_mb": model_size // (1024 * 1024),
            "total_mb": model_size // (1024 * 1024)
        }
