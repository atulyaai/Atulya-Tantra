"""
Tantra AI Assistant - Optimized Voice-First AI Brain
Clean, minimal, fully functional with persistent Gemma2 brain
"""

import tkinter as tk
from tkinter import scrolledtext
import threading, queue, time, json, re
from datetime import datetime
import requests
import os
import subprocess
import webbrowser
import pyautogui
from Tools.tantra_tools import (
    get_user_id,
    get_session_paths,
    append_jsonl,
    backup_file,
)

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

# ----------------- PERSISTENT TANTRA BRAIN -----------------
class TantraBrain:
    """Keeps Gemma2 model loaded and responsive"""
    def __init__(self, model="gemma2:2b", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.session = requests.Session()
        self.model_loaded = False
        self.conversation_history = []  # Store conversation context
        self.load_model()
        # Keep brain alive
        threading.Thread(target=self.keep_alive, daemon=True).start()
    
    def load_model(self):
        """Pre-load model"""
        try:
            print("🧠 Initializing Tantra's brain...")
            response = self.session.post(f"{self.base_url}/api/generate",
                json={
                    'model': self.model,
                    'prompt': "Hello",
                    'stream': False,
                    'options': {'max_tokens': 5}
                }, timeout=30)
            
            if response.status_code == 200:
                self.model_loaded = True
                print("✅ Tantra's brain is ready")
            else:
                print("❌ Brain initialization failed")
        except Exception as e:
            print(f"❌ Brain error: {e}")
    
    def generate_response(self, message, max_tokens=50):
        """Generate AI response with emoji removal"""
        if not self.model_loaded:
            return "Brain not ready"
        
        try:
            # Dynamic token allocation based on question type
            message_lower = message.lower()
            
            # Detailed questions - allow more tokens
            detail_keywords = ['explain', 'tell me about', 'describe', 'how does', 'what is', 'why', 'detailed', 'more info', 'capabilities', 'what can you do']
            wants_detail = any(keyword in message_lower for keyword in detail_keywords)
            
            # Capability questions need more space to explain
            capability_keywords = ['capabilities', 'what can you do', 'what tasks', 'features', 'abilities']
            wants_capabilities = any(keyword in message_lower for keyword in capability_keywords)
            
            # Dynamic token allocation - be more generous
            if wants_capabilities:
                tokens = 300  # Much more space for capability explanations
            elif wants_detail:
                tokens = 250  # More space for detailed explanations
            elif len(message_lower.split()) > 10:
                tokens = 150  # Longer questions get longer responses
            else:
                tokens = 120  # Default for normal questions (increased from 30)
            
            # Create context-aware prompt
            context_prompt = self.build_context_prompt(message)
            
            response = self.session.post(f"{self.base_url}/api/generate",
                json={
                    'model': self.model,
                    'prompt': context_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.3,
                        'max_tokens': tokens,
                        'num_predict': tokens
                    }
                }, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                response_text = data['response'].strip()
                
                # Remove ALL emojis completely
                emoji_pattern = re.compile("["
                    u"\U0001F600-\U0001F64F"  # emoticons
                    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                    u"\U0001F680-\U0001F6FF"  # transport & map symbols
                    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                    u"\U00002702-\U000027B0"  # dingbats
                    u"\U000024C2-\U0001F251"  # enclosed characters
                    "]+", flags=re.UNICODE)
                
                clean_response = emoji_pattern.sub('', response_text).strip()
                
                # Add response to conversation history
                self.add_response_to_history(clean_response)
                
                return clean_response
            else:
                return "Brain error"
                
        except Exception as e:
            return f"Error: {e}"
    
    def build_context_prompt(self, message):
        """Build context-aware prompt with conversation history"""
        # Add current message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        # Keep only last 6 exchanges (3 user + 3 assistant) for context
        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]
        
        # Build context string
        context = """You are Tantra, a helpful AI assistant. You are NOT Gemma. Your name is Tantra.

CAPABILITIES - What Tantra can do:
1. VOICE INTERACTION: Continuous conversation, voice recognition, text-to-speech
2. SYSTEM CONTROL: Close windows, minimize/maximize, lock screen, take screenshots
3. APPLICATION CONTROL: Open Chrome, Calculator, Notepad, File Explorer
4. VOLUME CONTROL: Increase/decrease/mute system volume
5. LIVE DATA: Get current time, date, weather information
6. WEB SEARCH: Search the internet for information
7. MEMORY: Remember user's name, preferences, and conversation context
8. CONVERSATION: Natural dialogue with context awareness
9. TASK ASSISTANCE: Help with questions, explanations, problem-solving
10. INFORMATION: Provide knowledge on various topics

When asked about capabilities, explain these specific features in detail. Be helpful, direct, and provide comprehensive information. Give complete answers, not short responses.

"""
        
        # Add recent conversation context
        if len(self.conversation_history) > 1:
            context += "Recent conversation:\n"
            for i in range(max(0, len(self.conversation_history) - 6), len(self.conversation_history) - 1):
                if self.conversation_history[i]["role"] == "user":
                    context += f"User: {self.conversation_history[i]['content']}\n"
                else:
                    context += f"Tantra: {self.conversation_history[i]['content']}\n"
            context += "\n"
        
        # Add current question
        context += f"User asks: {message}\n"
        context += "Tantra responds:"
        
        return context
    
    def add_response_to_history(self, response):
        """Add Tantra's response to conversation history"""
        self.conversation_history.append({"role": "assistant", "content": response})
    
    def keep_alive(self):
        """Ping model every minute to keep loaded"""
        while True:
            time.sleep(60)
            try:
                self.generate_response("ping", 1)
            except:
                pass

# Global brain instance
tantra_brain = None

def get_ollama_client():
    global tantra_brain
    if tantra_brain is None:
        tantra_brain = TantraBrain()
    return tantra_brain

# ----------------- MAIN TANTRA GUI & VOICE -----------------
class TantraAI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Tantra AI Assistant")
        self.root.geometry("1000x800")
        self.root.configure(bg='#ffffff')
        
        # Core state
        self.user_name = "friend"
        self.current_mode = "conversation"
        self.running = True
        
        # Queues for clean architecture
        self.message_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        
        # Voice components
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.tts_lock = threading.Lock()
        
        # Memory system
        self.user_memory = {}
        self.load_memory()

        # Conversation logging (persistent)
        self.user_id = get_user_id()
        self.session_paths = get_session_paths(self.user_id)
        # Backup previous latest on new run
        try:
            backup_file(self.session_paths['latest'], self.user_id)
        except Exception:
            pass
        # Write session header
        session_meta = {
            "type": "session_start",
            "user": self.user_id,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            append_jsonl(self.session_paths['session'], session_meta)
            append_jsonl(self.session_paths['latest'], session_meta)
        except Exception:
            pass
        
        # Initialize components
        self.initialize_voice()
        self.create_interface()
        
        # Start background threads
        threading.Thread(target=self.process_messages, daemon=True).start()
        threading.Thread(target=self.process_tts, daemon=True).start()
        
        # Start GUI updates
        self.root.after(100, self.check_queue)
        self.root.after(1000, self.start_conversation_mode)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ----------------- VOICE INITIALIZATION -----------------
    def initialize_voice(self):
        """Initialize voice recognition and TTS"""
        # Speech Recognition
        if SPEECH_AVAILABLE:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                
                # Adjust for ambient noise and set better thresholds
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    # Increase energy threshold to ignore background noise
                    self.recognizer.energy_threshold = 300
                    # Increase pause threshold to avoid false triggers
                    self.recognizer.pause_threshold = 0.8
                
                print("✅ Voice recognition ready")
            except Exception as e:
                print(f"❌ Voice recognition error: {e}")
                self.recognizer = None
        
        # Text-to-Speech
        if WIN32_TTS_AVAILABLE:
            try:
                self.tts_engine = win32com.client.Dispatch("SAPI.SpVoice")
                self.tts_engine.Rate = 0  # Normal speed
                self.tts_engine.Volume = 85  # Good volume
                
                # Try to select a female voice for more natural sound
                voices = self.tts_engine.GetVoices()
                for i in range(voices.Count):
                    voice = voices.Item(i)
                    if "female" in voice.GetDescription().lower() or "zira" in voice.GetDescription().lower():
                        self.tts_engine.Voice = voice
                        break
                
                print("✅ Windows SAPI TTS ready (human-like voice)")
            except Exception as e:
                print(f"❌ Windows SAPI error: {e}")
                self.tts_engine = None
        
        elif PYTTSX3_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 170)
                self.tts_engine.setProperty('volume', 0.9)
                print("✅ pyttsx3 fallback ready")
            except Exception as e:
                print(f"❌ pyttsx3 error: {e}")
                self.tts_engine = None

    # ----------------- GUI CREATION -----------------
    def create_interface(self):
        """Create the ChatGPT-style interface"""
        # Header
        header = tk.Frame(self.root, bg='#ffffff', height=70)
        header.pack(fill='x', padx=30, pady=(20, 0))
        header.pack_propagate(False)
        
        tk.Label(header, text="Tantra", font=('Arial', 22, 'bold'), 
                fg='#000000', bg='#ffffff').pack(side='left')
        
        self.mode_label = tk.Label(header, text="● Listening", 
                                  font=('Arial', 11), fg='#10a37f', bg='#ffffff')
        self.mode_label.pack(side='right')
        
        # Conversation area
        conv_frame = tk.Frame(self.root, bg='#ffffff')
        conv_frame.pack(fill='both', expand=True, padx=30, pady=20)
        
        self.conversation_text = scrolledtext.ScrolledText(
            conv_frame, font=('Segoe UI', 11), bg='#ffffff', fg='#000000',
            wrap='word', state='disabled', relief='flat', bd=0, padx=10, pady=10
        )
        self.conversation_text.pack(fill='both', expand=True)
        
        # Configure text tags
        self.conversation_text.tag_configure('user', foreground='#000000', spacing1=10, spacing3=10)
        self.conversation_text.tag_configure('assistant', foreground='#000000', spacing1=10, spacing3=10)
        self.conversation_text.tag_configure('system', foreground='#6b7280', spacing1=10, spacing3=10)
        
        # Input area
        input_frame = tk.Frame(self.root, bg='#ffffff')
        input_frame.pack(fill='x', padx=30, pady=(0, 30))
        
        input_box = tk.Frame(input_frame, bg='#e5e7eb', bd=1, relief='flat')
        input_box.pack(fill='x')
        
        self.text_input = tk.Entry(input_box, font=('Segoe UI', 12), bg='#ffffff', 
                                  fg='#000000', relief='flat', bd=0, insertbackground='#000000')
        self.text_input.pack(side='left', fill='x', expand=True, padx=15, pady=12)
        self.text_input.bind('<Return>', self.send_text_message)
        
        self.send_btn = tk.Button(input_box, text="➤", font=('Arial', 16, 'bold'),
                                  bg='#10a37f', fg='#ffffff', relief='flat', bd=0,
                                  padx=15, command=self.send_text_message, cursor='hand2')
        self.send_btn.pack(side='right', padx=12, pady=8)
        
        self.text_input.focus()

    # ----------------- MESSAGE PROCESSING -----------------
    def start_conversation_mode(self):
        """Start continuous voice conversation"""
        if not SPEECH_AVAILABLE or not self.recognizer:
            self.add_message("Voice not available. Using text mode.", "system")
            return
        
        self.add_message("Conversation mode started. I'm listening...", "system")
        threading.Thread(target=self.continuous_listen, daemon=True).start()

    def continuous_listen(self):
        """Continuous voice listening with noise filtering"""
        consecutive_errors = 0
        
        while self.current_mode == "conversation":
            try:
                with self.microphone as source:
                    # Better noise cancellation - longer timeout, higher threshold
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=10)
                
                # Process speech
                text = self.recognizer.recognize_google(audio, language='en-US')
                
                # Filter out noise, short phrases, and key presses
                if self.is_valid_speech(text):
                    print(f"🎤 Heard: {text}")
                    self.message_queue.put(('user_input', text))
                    consecutive_errors = 0
                else:
                    print("🎤 Filtered out noise/short phrase")
                    
            except sr.WaitTimeoutError:
                consecutive_errors = 0
                continue
            except sr.UnknownValueError:
                consecutive_errors += 1
                # Only show error after multiple consecutive failures
                if consecutive_errors >= 3:
                    print("🎤 Could not understand speech (noise detected)")
                    consecutive_errors = 0
                continue
            except Exception as e:
                print(f"Voice error: {e}")
                break

    def is_valid_speech(self, text):
        """Filter out noise, short phrases, and key presses"""
        if not text or len(text.strip()) < 2:
            return False
        
        text_lower = text.lower().strip()
        
        # Filter out common noise words and key presses
        noise_words = ['uh', 'um', 'ah', 'eh', 'oh', 'hmm', 'mm', 'click', 'tap', 'key', 'button']
        if text_lower in noise_words:
            return False
        
        # Filter out very short phrases (likely noise)
        if len(text_lower.split()) < 2 and len(text_lower) < 5:
            return False
        
        # Filter out single characters or numbers
        if len(text_lower) == 1 and text_lower.isalnum():
            return False
        
        return True

    def send_text_message(self, event=None):
        """Send text message"""
        text = self.text_input.get().strip()
        if text:
            self.add_message(text, "user")
            self.process_message(text)
            self.text_input.delete(0, 'end')

    def process_message(self, message):
        """Process user message"""
        self.message_queue.put(('user_input', message))

    def process_messages(self):
        """Process messages from queue"""
        while self.running:
            try:
                msg_type, data = self.message_queue.get(timeout=0.1)
                
                if msg_type == 'user_input':
                    # Add user message to GUI
                    self.root.after(0, lambda d=data: self.add_message(d, "user"))
                    # Persist user turn
                    try:
                        entry = {"role": "user", "content": data, "timestamp": datetime.now().isoformat()}
                        append_jsonl(self.session_paths['session'], entry)
                        append_jsonl(self.session_paths['latest'], entry)
                    except Exception:
                        pass
                    
                    # Small delay to prevent rushing
                    time.sleep(0.3)
                    
                    # Generate response
                    response = self.generate_response(data)
                    
                    # Add response to GUI
                    self.root.after(0, lambda r=response: self.add_message(r, "assistant"))
                    
                    # Queue for TTS
                    self.tts_queue.put(response)
                    
                    # Persist assistant turn
                    try:
                        entry = {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}
                        append_jsonl(self.session_paths['session'], entry)
                        append_jsonl(self.session_paths['latest'], entry)
                    except Exception:
                        pass
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Message processing error: {e}")

    def generate_response(self, message):
        """Generate AI response using persistent brain"""
        # Update memory
        self.update_memory(message)
        
        # Check for system commands first
        system_response = self.execute_system_command(message)
        if system_response:
            return system_response
        
        # Check for live data
        live_response = self.get_live_data(message)
        if live_response:
            return live_response
        
        # Get response from brain
        client = get_ollama_client()
        return client.generate_response(message, max_tokens=50)
    
    def execute_system_command(self, message):
        """Execute real system commands like Jarvis"""
        message_lower = message.lower()
        
        # Window Management
        if 'close' in message_lower and ('window' in message_lower or 'tab' in message_lower):
            try:
                pyautogui.hotkey('alt', 'F4')
                return "Closing window."
            except:
                return "Cannot close window."
        
        elif 'minimize' in message_lower or 'background' in message_lower:
            try:
                pyautogui.hotkey('win', 'down')
                return "Minimizing window."
            except:
                return "Cannot minimize."
        
        elif 'maximize' in message_lower:
            try:
                pyautogui.hotkey('win', 'up')
                return "Maximizing window."
            except:
                return "Cannot maximize."
        
        # Application Control
        elif 'open' in message_lower:
            if 'chrome' in message_lower or 'browser' in message_lower:
                os.startfile('chrome')
                return "Opening Chrome browser."
            elif 'notepad' in message_lower:
                subprocess.Popen('notepad.exe')
                return "Opening Notepad."
            elif 'calculator' in message_lower:
                subprocess.Popen('calc.exe')
                return "Opening Calculator."
            elif 'file explorer' in message_lower or 'files' in message_lower:
                subprocess.Popen('explorer.exe')
                return "Opening File Explorer."
        
        # System Control
        elif 'lock' in message_lower and 'screen' in message_lower:
            try:
                pyautogui.hotkey('win', 'l')
                return "Locking screen."
            except:
                return "Cannot lock screen."
        
        # Screenshot
        elif 'screenshot' in message_lower or 'capture' in message_lower:
            try:
                screenshot = pyautogui.screenshot()
                screenshot.save('tantra_screenshot.png')
                return "Screenshot saved as tantra_screenshot.png"
            except:
                return "Cannot take screenshot."
        
        # Volume Control
        elif 'volume up' in message_lower:
            try:
                pyautogui.press('volumeup')
                return "Volume increased."
            except:
                return "Cannot change volume."
        
        elif 'volume down' in message_lower:
            try:
                pyautogui.press('volumedown')
                return "Volume decreased."
            except:
                return "Cannot change volume."
        
        elif 'mute' in message_lower:
            try:
                pyautogui.press('volumemute')
                return "Volume muted."
            except:
                return "Cannot mute volume."
        
        return None
    
    def get_live_data(self, message):
        """Get live data from the web"""
        message_lower = message.lower()
        
        # Weather
        if 'weather' in message_lower:
            try:
                city = 'Delhi'  # Default
                response = requests.get(f'https://wttr.in/{city}?format=%C+%t', timeout=3)
                if response.status_code == 200:
                    return f"Weather in {city}: {response.text}"
            except:
                pass
        
        # Time
        if 'time' in message_lower and 'what' in message_lower:
            return f"It's {datetime.now().strftime('%I:%M %p')}"
        
        # Date
        if 'date' in message_lower and 'what' in message_lower:
            return f"Today is {datetime.now().strftime('%B %d, %Y')}"
        
        # Quick search
        if 'search' in message_lower or 'find' in message_lower or 'look up' in message_lower:
            query = message_lower.replace('search', '').replace('find', '').replace('look up', '').strip()
            if query:
                try:
                    # DuckDuckGo instant answer
                    response = requests.get(f'https://api.duckduckgo.com/?q={query}&format=json', timeout=3)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('AbstractText'):
                            return data['AbstractText'][:200]
                except:
                    pass
        
        return None

    # ----------------- MEMORY SYSTEM -----------------
    def load_memory(self):
        """Load user memory from file"""
        try:
            with open('tantra_memory.json', 'r') as f:
                self.user_memory = json.load(f)
            print("✅ Memory loaded")
        except:
            self.user_memory = {'name': 'friend', 'preferences': {}}
            print("📝 Starting fresh memory")

    def save_memory(self):
        """Save user memory to file"""
        try:
            with open('tantra_memory.json', 'w') as f:
                json.dump(self.user_memory, f)
        except Exception as e:
            print(f"Memory save error: {e}")

    def update_memory(self, message):
        """Update memory based on user input"""
        message_lower = message.lower()
        
        # Extract name
        if 'my name is' in message_lower:
            name = message_lower.split('my name is')[1].strip()
            if name:
                self.user_memory['name'] = name
                self.save_memory()
        
        # Extract preferences
        if 'i like' in message_lower or 'i prefer' in message_lower:
            if 'i like' in message_lower:
                preference = message_lower.split('i like')[1].strip()
            else:
                preference = message_lower.split('i prefer')[1].strip()
            
            if preference:
                if 'preferences' not in self.user_memory:
                    self.user_memory['preferences'] = {}
                self.user_memory['preferences']['likes'] = preference
                self.save_memory()

    # ----------------- TTS PROCESSING -----------------
    def process_tts(self):
        """Dedicated thread for speaking responses"""
        while self.running:
            try:
                text = self.tts_queue.get(timeout=0.1)
                self.speak(text)
            except queue.Empty:
                continue

    def speak(self, text):
        """Speak text using available TTS engine"""
        if not TTS_AVAILABLE or not text:
            return
        
        if WIN32_TTS_AVAILABLE and self.tts_engine:
            self.speak_win32(text)
        elif PYTTSX3_AVAILABLE:
            self.speak_pyttsx3(text)

    def speak_win32(self, text):
        """Windows SAPI TTS"""
        try:
            with self.tts_lock:
                self.tts_engine.Speak(text)
                print(f"✅ Spoke (SAPI): {text}")
        except Exception as e:
            print(f"SAPI TTS error: {e}")
            # Fallback to pyttsx3
            if PYTTSX3_AVAILABLE:
                self.speak_pyttsx3(text)

    def speak_pyttsx3(self, text):
        """Fallback pyttsx3 TTS"""
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            engine.setProperty('volume', 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            print(f"✅ Spoke (PyTTSx3): {text}")
        except Exception as e:
            print(f"PyTTSx3 error: {e}")

    # ----------------- GUI UPDATES -----------------
    def add_message(self, text, sender):
        """Add message to conversation"""
        self.conversation_text.config(state='normal')
        
        if sender == 'user':
            self.conversation_text.insert(tk.END, "You\n", 'user')
        elif sender == 'assistant':
            self.conversation_text.insert(tk.END, "Tantra\n", 'assistant')
        else:
            self.conversation_text.insert(tk.END, f"{sender}\n", 'system')
        
        self.conversation_text.insert(tk.END, text + "\n\n")
        self.conversation_text.config(state='disabled')
        self.conversation_text.see(tk.END)

    def check_queue(self):
        """Check for voice input messages"""
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                if msg_type == 'voice_input':
                    self.add_message(data, "user")
                    self.process_message(data)
        except queue.Empty:
            pass
        
        self.root.after(100, self.check_queue)

    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.current_mode = "text"
        # Mark session end
        try:
            entry = {"type": "session_end", "timestamp": datetime.now().isoformat()}
            append_jsonl(self.session_paths['session'], entry)
            append_jsonl(self.session_paths['latest'], entry)
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

    def run(self):
        """Start the application"""
        self.root.mainloop()

# ----------------- MAIN -----------------
def main():
    print("🤖 Starting Tantra AI Assistant...")
    
    if not SPEECH_AVAILABLE:
        print("⚠️ Install: pip install SpeechRecognition pyaudio")
    
    if not TTS_AVAILABLE:
        print("⚠️ Install: pip install pyttsx3")
    
    app = TantraAI()
    app.run()

if __name__ == "__main__":
    main()
