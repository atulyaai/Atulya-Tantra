"""
Main entry point for Atulya Tantra
Loads from the atulya_tantra package
"""

import os
import sys
import logging
from pathlib import Path
import yaml
from dotenv import load_dotenv
from colorama import init, Fore, Style
import signal

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from package
from atulya_tantra import (
    TextAI,
    ConversationManager,
    VoiceInput,
    VoiceOutput
)

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AtulyaTantra:
    """Main orchestrator for Atulya Tantra voice AI system"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize Atulya Tantra system
        
        Args:
            config_path: Path to configuration file
        """
        logger.info(f"{Fore.CYAN}{'='*60}")
        logger.info(f"{Fore.CYAN}🌟 Atulya Tantra - Voice AI System 🌟")
        logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        self.config = self.load_config(config_path)
        
        # Initialize components
        self.text_ai = None
        self.conversation = None
        self.voice_input = None
        self.voice_output = None
        
        # System state
        self.running = False
        self.wake_word_enabled = self.config.get('wake_word', {}).get('enabled', False)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ Configuration loaded from {config_path}")
            return config
        except Exception as e:
            logger.warning(f"Could not load config: {e}. Using defaults.")
            return {}
    
    def initialize(self):
        """Initialize all components"""
        logger.info(f"{Fore.YELLOW}Initializing components...{Style.RESET_ALL}")
        
        # Get HuggingFace token
        from atulya_tantra.utils import get_env_var
        from atulya_tantra.constants import MODELS_CACHE_DIR, HUGGINGFACE_TOKEN
        from atulya_tantra.config_loader import get_config
        
        hf_token = get_env_var('HUGGINGFACE_TOKEN', HUGGINGFACE_TOKEN, required=True)
        
        # Get configuration
        config_loader = get_config()
        cache_dir = str(MODELS_CACHE_DIR)
        
        # Initialize Tantra Engine (The "Brain")
        try:
            logger.info(f"{Fore.YELLOW}Initializing Tantra Engine...{Style.RESET_ALL}")
            logger.info(f"{Fore.YELLOW}Models will be cached in: {cache_dir}{Style.RESET_ALL}")
            
            from atulya_tantra.core import TantraEngine
            self.engine = TantraEngine(
                hf_token=hf_token,
                cache_dir=cache_dir,
                config_path=self.config_path
            )
        except Exception as e:
            logger.error(f"Failed to initialize Tantra Engine: {e}")
            return False
        
        # Initialize Voice Input (The "Ears")
        try:
            stt_config = self.config.get('speech_to_text', {})
            self.voice_input = VoiceInput(
                model_size=stt_config.get('model_size', 'base'),
                language=stt_config.get('language', 'en'),
                device=stt_config.get('device', 'cpu'),
                vad_enabled=stt_config.get('vad_enabled', True)
            )
        except Exception as e:
            logger.error(f"Failed to initialize Voice Input: {e}")
            return False
        
        # Initialize Voice Output (The "Mouth")
        try:
            tts_config = self.config.get('text_to_speech', {})
            self.voice_output = VoiceOutput(
                engine=tts_config.get('engine', 'piper'),
                voice=tts_config.get('voice', 'en_US-lessac-medium'),
                speaking_rate=tts_config.get('speaking_rate', 1.0),
                volume=tts_config.get('volume', 0.8),
                use_gpu=(device == 'cuda')
            )
        except Exception as e:
            logger.warning(f"Voice Output initialization had issues: {e}")
            logger.warning("Continuing anyway - speech may use system defaults")
        
        logger.info(f"{Fore.GREEN}✓ All components initialized successfully!{Style.RESET_ALL}")
        return True
    
    def process_command(self, text: str) -> bool:
        """
        Process special commands
        
        Args:
            text: User input text
            
        Returns:
            True if command was handled
        """
        text_lower = text.lower().strip()
        
        # Exit commands
        if text_lower in ['exit', 'quit', 'goodbye', 'bye']:
            self.voice_output.speak("Goodbye! It was nice talking to you.")
            return True
        
        # Clear conversation
        if 'clear conversation' in text_lower or 'forget everything' in text_lower:
            self.engine.conversation.clear_history()
            self.voice_output.speak("Conversation history cleared.")
            return True
        
        return False
    
    def conversation_loop(self):
        """Main conversation loop"""
        logger.info(f"{Fore.GREEN}{'='*60}")
        logger.info(f"{Fore.GREEN}🎤 Atulya Tantra is ready! Start speaking...{Style.RESET_ALL}")
        logger.info(f"{Fore.CYAN}Say 'exit' or 'goodbye' to quit{Style.RESET_ALL}")
        logger.info(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
        
        # Welcome message
        self.voice_output.speak("Hello! I am Atulya Tantra, your AI assistant. How can I help you today?")
        
        self.running = True
        
        while self.running:
            try:
                # Listen for user input
                print(f"\n{Fore.YELLOW}🎤 Listening...{Style.RESET_ALL}")
                user_text = self.voice_input.listen_and_transcribe()
                
                if not user_text or len(user_text.strip()) == 0:
                    continue
                
                print(f"{Fore.CYAN}You: {user_text}{Style.RESET_ALL}")
                
                # Check for exit command
                if user_text.lower().strip() in ['exit', 'quit', 'goodbye', 'bye']:
                    self.voice_output.speak("Goodbye! It was nice talking to you.")
                    break
                
                # Process special commands
                if self.process_command(user_text):
                    continue
                
                # Generate response using Engine (Brain)
                print(f"{Fore.YELLOW}🤔 Thinking...{Style.RESET_ALL}")
                
                # The engine handles tools, memory, and generation
                response = self.engine.process_message(user_text)
                
                # Speak response
                print(f"{Fore.GREEN}Atulya: {response}{Style.RESET_ALL}")
                self.voice_output.speak(response)
                
            except KeyboardInterrupt:
                logger.info("\nInterrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in conversation loop: {e}")
                self.voice_output.speak("I'm sorry, I encountered an error. Please try again.")
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        logger.info(f"\n{Fore.YELLOW}Shutting down gracefully...{Style.RESET_ALL}")
        self.running = False
        self.shutdown()
        sys.exit(0)
    
    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Cleaning up...")
        
        if self.text_ai:
            del self.text_ai.model
            del self.text_ai.tokenizer
        
        logger.info(f"{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
    
    def run(self):
        """Main entry point"""
        if not self.initialize():
            logger.error("Initialization failed. Exiting.")
            return
        
        try:
            self.conversation_loop()
        finally:
            self.shutdown()


def main():
    """Main entry point"""
    atulya = AtulyaTantra()
    atulya.run()


if __name__ == "__main__":
    main()
