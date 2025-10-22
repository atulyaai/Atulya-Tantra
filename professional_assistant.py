"""
Professional AI Assistant
Advanced conversational AI with dynamic response generation and action execution
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import queue
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Import our professional assistant core
from Core.assistant_core import ProfessionalAssistantCore, ConversationState
from Core.brain.llm_provider import LLMProvider
from Core.memory.conversation_memory import ConversationMemory

# Voice components
try: 
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError: 
    SPEECH_AVAILABLE = False

# TTS components
try: 
    import win32com.client
    WIN32_TTS_AVAILABLE = True
except ImportError: 
    WIN32_TTS_AVAILABLE = False

try: 
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError: 
    PYTTSX3_AVAILABLE = False

TTS_AVAILABLE = WIN32_TTS_AVAILABLE or PYTTSX3_AVAILABLE

class ProfessionalAssistant:
    """
    Professional AI Assistant with advanced conversation capabilities
    and comprehensive action execution
    """
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Professional AI Assistant")
        self.root.geometry("1200x900")
        self.root.configure(bg='#f8f9fa')
        
        # Core components
        self.assistant_core = ProfessionalAssistantCore()
        self.user_id = "user_001"  # In production, this would be dynamic
        self.session_id = f"session_{int(time.time())}"
        
        # State management
        self.running = True
        self.current_mode = "conversation"
        self.conversation_active = False
        
        # Queues for clean architecture
        self.message_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        
        # Voice components
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        
        # Initialize components
        self._initialize_voice()
        self._create_interface()
        
        # Start background threads
        threading.Thread(target=self._process_messages, daemon=True).start()
        threading.Thread(target=self._process_tts, daemon=True).start()
        
        # Start GUI updates
        self.root.after(100, self._check_queue)
        
        # Bind window close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _initialize_voice(self):
        """Initialize voice recognition and TTS"""
        # Speech Recognition
        if SPEECH_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    self.recognizer.energy_threshold = 300
                    self.recognizer.pause_threshold = 0.8
                
                print("✅ Voice recognition ready")
            except Exception as e:
                print(f"❌ Voice recognition error: {e}")
                self.recognizer = None
        
        # Text-to-Speech
        if WIN32_TTS_AVAILABLE:
            try:
                self.tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
                self.tts_engine.Rate = 0
                self.tts_engine.Volume = 85
                
                # Try to select a natural voice
                voices = self.tts_engine.GetVoices()
                for i in range(voices.Count):
                    voice = voices.Item(i)
                    if "female" in voice.GetDescription().lower() or "zira" in voice.GetDescription().lower():
                        self.tts_engine.Voice = voice
                        break
                
                print("✅ Windows SAPI TTS ready")
            except Exception as e:
                print(f"❌ Windows SAPI error: {e}")
                self.tts_engine = None
        
        elif PYTTSX3_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 170)
                self.tts_engine.setProperty('volume', 0.9)
                print("✅ pyttsx3 TTS ready")
            except Exception as e:
                print(f"❌ pyttsx3 error: {e}")
                self.tts_engine = None
    
    def _create_interface(self):
        """Create the professional interface"""
        # Header
        header = tk.Frame(self.root, bg='#ffffff', height=80)
        header.pack(fill='x', padx=20, pady=(20, 0))
        header.pack_propagate(False)
        
        # Title and status
        title_frame = tk.Frame(header, bg='#ffffff')
        title_frame.pack(side='left', fill='y')
        
        tk.Label(title_frame, text="Professional AI Assistant", 
                font=('Arial', 24, 'bold'), fg='#2c3e50', bg='#ffffff').pack(anchor='w')
        
        self.status_label = tk.Label(title_frame, text="● Ready", 
                                   font=('Arial', 12), fg='#27ae60', bg='#ffffff')
        self.status_label.pack(anchor='w')
        
        # Control buttons
        control_frame = tk.Frame(header, bg='#ffffff')
        control_frame.pack(side='right', fill='y')
        
        self.voice_btn = tk.Button(control_frame, text="🎤 Voice", 
                                 font=('Arial', 10), bg='#3498db', fg='white',
                                 relief='flat', padx=15, pady=5, command=self._toggle_voice)
        self.voice_btn.pack(side='right', padx=5)
        
        self.capabilities_btn = tk.Button(control_frame, text="ℹ️ Capabilities", 
                                        font=('Arial', 10), bg='#9b59b6', fg='white',
                                        relief='flat', padx=15, pady=5, command=self._show_capabilities)
        self.capabilities_btn.pack(side='right', padx=5)
        
        # Main conversation area
        main_frame = tk.Frame(self.root, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Conversation display
        conv_frame = tk.Frame(main_frame, bg='#ffffff', relief='solid', bd=1)
        conv_frame.pack(fill='both', expand=True, pady=(0, 20))
        
        self.conversation_text = scrolledtext.ScrolledText(
            conv_frame, font=('Segoe UI', 11), bg='#ffffff', fg='#2c3e50',
            wrap='word', state='disabled', relief='flat', bd=0, padx=20, pady=20
        )
        self.conversation_text.pack(fill='both', expand=True)
        
        # Configure text tags
        self.conversation_text.tag_configure('user', foreground='#2c3e50', 
                                           font=('Segoe UI', 11, 'bold'), spacing1=10, spacing3=10)
        self.conversation_text.tag_configure('assistant', foreground='#27ae60', 
                                           font=('Segoe UI', 11), spacing1=10, spacing3=10)
        self.conversation_text.tag_configure('system', foreground='#7f8c8d', 
                                           font=('Segoe UI', 10, 'italic'), spacing1=10, spacing3=10)
        self.conversation_text.tag_configure('action', foreground='#e74c3c', 
                                           font=('Segoe UI', 10, 'bold'), spacing1=5, spacing3=5)
        
        # Input area
        input_frame = tk.Frame(main_frame, bg='#f8f9fa')
        input_frame.pack(fill='x')
        
        input_container = tk.Frame(input_frame, bg='#ecf0f1', relief='solid', bd=1)
        input_container.pack(fill='x')
        
        self.text_input = tk.Entry(input_container, font=('Segoe UI', 12), 
                                  bg='#ffffff', fg='#2c3e50', relief='flat', bd=0, 
                                  insertbackground='#2c3e50')
        self.text_input.pack(side='left', fill='x', expand=True, padx=15, pady=12)
        self.text_input.bind('<Return>', self._send_text_message)
        
        self.send_btn = tk.Button(input_container, text="➤", font=('Arial', 16, 'bold'),
                                 bg='#27ae60', fg='#ffffff', relief='flat', bd=0,
                                 padx=20, command=self._send_text_message, cursor='hand2')
        self.send_btn.pack(side='right', padx=10, pady=8)
        
        self.text_input.focus()
        
        # Add welcome message
        self._add_message("Welcome to the Professional AI Assistant! I'm here to help you with various tasks including system control, web searches, communication, scheduling, and much more. How can I assist you today?", "assistant")
    
    def _toggle_voice(self):
        """Toggle voice conversation mode"""
        if not SPEECH_AVAILABLE or not self.recognizer:
            messagebox.showwarning("Voice Not Available", 
                                 "Voice recognition is not available. Please install required packages.")
            return
        
        if self.conversation_active:
            self.conversation_active = False
            self.voice_btn.config(text="🎤 Voice", bg='#3498db')
            self.status_label.config(text="● Ready", fg='#27ae60')
            self._add_message("Voice conversation stopped.", "system")
        else:
            self.conversation_active = True
            self.voice_btn.config(text="🔴 Stop", bg='#e74c3c')
            self.status_label.config(text="● Listening", fg='#e74c3c')
            self._add_message("Voice conversation started. I'm listening...", "system")
            threading.Thread(target=self._continuous_listen, daemon=True).start()
    
    def _continuous_listen(self):
        """Continuous voice listening"""
        while self.conversation_active and self.running:
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=10)
                
                text = self.recognizer.recognize_google(audio, language='en-US')
                
                if self._is_valid_speech(text):
                    print(f"🎤 Heard: {text}")
                    self.message_queue.put(('user_input', text))
                else:
                    print("🎤 Filtered out noise/short phrase")
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as e:
                print(f"Voice error: {e}")
                break
    
    def _is_valid_speech(self, text: str) -> bool:
        """Filter out noise and short phrases"""
        if not text or len(text.strip()) < 2:
            return False
        
        text_lower = text.lower().strip()
        noise_words = ['uh', 'um', 'ah', 'eh', 'oh', 'hmm', 'mm', 'click', 'tap']
        
        if text_lower in noise_words:
            return False
        
        if len(text_lower.split()) < 2 and len(text_lower) < 5:
            return False
        
        return True
    
    def _send_text_message(self, event=None):
        """Send text message"""
        text = self.text_input.get().strip()
        if text:
            self._add_message(text, "user")
            self.message_queue.put(('user_input', text))
            self.text_input.delete(0, 'end')
    
    def _process_messages(self):
        """Process messages from queue"""
        while self.running:
            try:
                msg_type, data = self.message_queue.get(timeout=0.1)
                
                if msg_type == 'user_input':
                    # Process with professional assistant core
                    response = self.assistant_core.process_message(
                        user_id=self.user_id,
                        message=data,
                        session_id=self.session_id
                    )
                    
                    # Display response
                    self.root.after(0, lambda: self._add_message(response['response'], "assistant"))
                    
                    # Display actions if any
                    if response.get('actions_executed'):
                        for action in response['actions_executed']:
                            if action.get('success'):
                                self.root.after(0, lambda a=action: self._add_message(
                                    f"✅ {a.get('action_type', 'Action')} completed successfully", "action"))
                            else:
                                self.root.after(0, lambda a=action: self._add_message(
                                    f"❌ {a.get('action_type', 'Action')} failed: {a.get('error', 'Unknown error')}", "action"))
                    
                    # Display follow-up questions if any
                    if response.get('follow_up_questions'):
                        for question in response['follow_up_questions']:
                            self.root.after(0, lambda q=question: self._add_message(f"💭 {q}", "system"))
                    
                    # Queue for TTS
                    self.tts_queue.put(response['response'])
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Message processing error: {e}")
    
    def _process_tts(self):
        """Process TTS queue"""
        while self.running:
            try:
                text = self.tts_queue.get(timeout=0.1)
                self._speak(text)
            except queue.Empty:
                continue
    
    def _speak(self, text: str):
        """Speak text using available TTS engine"""
        if not TTS_AVAILABLE or not text:
            return
        
        if WIN32_TTS_AVAILABLE and self.tts_engine:
            self._speak_win32(text)
        elif PYTTSX3_AVAILABLE:
            self._speak_pyttsx3(text)
    
    def _speak_win32(self, text: str):
        """Windows SAPI TTS"""
        try:
            with self.tts_lock:
                self.tts_engine.Speak(text)
        except Exception as e:
            print(f"SAPI TTS error: {e}")
            if PYTTSX3_AVAILABLE:
                self._speak_pyttsx3(text)
    
    def _speak_pyttsx3(self, text: str):
        """Fallback pyttsx3 TTS"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            engine.setProperty('volume', 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"pyttsx3 TTS error: {e}")
    
    def _add_message(self, message: str, message_type: str):
        """Add message to conversation display"""
        self.conversation_text.config(state='normal')
        
        # Add timestamp
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if message_type == 'user':
            self.conversation_text.insert('end', f"[{timestamp}] You: ", 'user')
        elif message_type == 'assistant':
            self.conversation_text.insert('end', f"[{timestamp}] Assistant: ", 'assistant')
        elif message_type == 'system':
            self.conversation_text.insert('end', f"[{timestamp}] System: ", 'system')
        elif message_type == 'action':
            self.conversation_text.insert('end', f"[{timestamp}] Action: ", 'action')
        
        self.conversation_text.insert('end', f"{message}\n\n")
        self.conversation_text.config(state='disabled')
        self.conversation_text.see('end')
    
    def _show_capabilities(self):
        """Show assistant capabilities"""
        capabilities = self.assistant_core.get_capabilities()
        
        # Create capabilities window
        cap_window = tk.Toplevel(self.root)
        cap_window.title("Assistant Capabilities")
        cap_window.geometry("600x500")
        cap_window.configure(bg='#f8f9fa')
        
        # Create scrollable text widget
        text_widget = scrolledtext.ScrolledText(cap_window, font=('Segoe UI', 10), 
                                              bg='#ffffff', fg='#2c3e50', wrap='word')
        text_widget.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Format capabilities
        content = "Professional AI Assistant Capabilities\n"
        content += "=" * 40 + "\n\n"
        
        for category, features in capabilities.items():
            content += f"{category.replace('_', ' ').title()}:\n"
            content += "-" * 20 + "\n"
            
            if isinstance(features, dict):
                for feature, value in features.items():
                    content += f"• {feature.replace('_', ' ').title()}: {value}\n"
            else:
                content += f"• {features}\n"
            
            content += "\n"
        
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')
    
    def _check_queue(self):
        """Check for GUI updates"""
        try:
            while True:
                self.root.update_idletasks()
        except:
            pass
        
        if self.running:
            self.root.after(100, self._check_queue)
    
    def _on_closing(self):
        """Handle window closing"""
        self.running = False
        self.conversation_active = False
        self.root.destroy()
    
    def run(self):
        """Start the assistant"""
        self.root.mainloop()

def main():
    """Main entry point"""
    print("🚀 Starting Professional AI Assistant...")
    print("=" * 50)
    
    try:
        assistant = ProfessionalAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("\n👋 Assistant stopped by user")
    except Exception as e:
        print(f"❌ Error starting assistant: {e}")
    finally:
        print("🔚 Assistant shutdown complete")

if __name__ == "__main__":
    main()
