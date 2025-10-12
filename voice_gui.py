"""
Voice GUI for Atulya Tantra - ChatGPT-style Voice Mode & Dictation
Simple, clean interface for voice conversations
"""

import asyncio
import threading
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

try:
    import tkinter as tk
    from tkinter import scrolledtext, ttk
    import pygame
    import speech_recognition as sr
    import edge_tts
    import ollama
    import tempfile
    import os
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Install with: pip install edge-tts SpeechRecognition pygame")
    sys.exit(1)

class VoiceGUI:
    """Simple voice conversation GUI like ChatGPT voice mode"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Atulya Tantra - Voice Mode")
        self.root.geometry("900x700")
        self.root.configure(bg='#1a1a1a')
        
        # Fix window controls - enable minimize/maximize/close
        self.root.resizable(True, True)
        self.root.minsize(600, 400)
        
        # Voice components
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        pygame.mixer.init()
        
        # State
        self.is_listening = False
        self.is_speaking = False
        self.conversation_history = []
        self.pending_messages = []  # Accumulate messages during AI speech
        
        # Configure recognizer - Better understanding of casual speech
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.2  # Responsive but not too quick
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.5
        
        self.setup_ui()
        self.calibrate_microphone()
        
    def setup_ui(self):
        """Setup the user interface"""
        
        # Header
        header = tk.Frame(self.root, bg='#0a0a0a', height=80)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        title = tk.Label(header, text="🤖 Atulya Tantra", 
                        font=('Arial', 24, 'bold'),
                        bg='#0a0a0a', fg='#00ffff')
        title.pack(pady=10)
        
        subtitle = tk.Label(header, text="Voice Conversation & Dictation Mode", 
                           font=('Arial', 10),
                           bg='#0a0a0a', fg='#888888')
        subtitle.pack()
        
        # Chat display
        chat_frame = tk.Frame(self.root, bg='#1a1a1a')
        chat_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=('Consolas', 11),
            bg='#2a2a2a',
            fg='#ffffff',
            insertbackground='#00ffff',
            relief='flat',
            padx=15,
            pady=15
        )
        self.chat_display.pack(fill='both', expand=True)
        self.chat_display.config(state='disabled')
        
        # Status bar
        status_frame = tk.Frame(self.root, bg='#0a0a0a', height=40)
        status_frame.pack(fill='x')
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="Ready", 
                                     font=('Arial', 10),
                                     bg='#0a0a0a', fg='#00ff00')
        self.status_label.pack(side='left', padx=20)
        
        self.mode_label = tk.Label(status_frame, text="Mode: Idle", 
                                   font=('Arial', 10),
                                   bg='#0a0a0a', fg='#888888')
        self.mode_label.pack(side='right', padx=20)
        
        # Input area
        input_frame = tk.Frame(self.root, bg='#1a1a1a')
        input_frame.pack(fill='x', padx=20, pady=10)
        
        # Text input - SMALLER, with typing indicator
        input_row = tk.Frame(input_frame, bg='#1a1a1a')
        input_row.pack(fill='x', pady=(0, 10))
        
        self.text_input = tk.Text(input_row, height=2, font=('Arial', 11),
                                 bg='#2a2a2a', fg='#ffffff',
                                 insertbackground='#00ffff',
                                 relief='flat', padx=10, pady=8)
        self.text_input.pack(side='left', fill='both', expand=True)
        self.text_input.bind('<Control-Return>', lambda e: self.send_text_message())
        self.text_input.bind('<KeyPress>', lambda e: self.on_typing())
        
        # Typing indicator
        self.typing_indicator = tk.Label(input_row, text="✍️ ", 
                                        font=('Arial', 12),
                                        bg='#1a1a1a', fg='#00ff00')
        self.typing_indicator.pack(side='right', padx=5)
        self.typing_indicator.pack_forget()  # Hidden by default
        
        # Buttons
        button_frame = tk.Frame(input_frame, bg='#1a1a1a')
        button_frame.pack(fill='x')
        
        # Voice conversation button
        self.voice_btn = tk.Button(
            button_frame, text="🎤 Start Voice Chat",
            command=self.toggle_voice_conversation,
            font=('Arial', 12, 'bold'),
            bg='#0066cc', fg='white',
            relief='flat', padx=20, pady=10,
            cursor='hand2'
        )
        self.voice_btn.pack(side='left', padx=(0, 10))
        
        # Dictation button
        self.dictate_btn = tk.Button(
            button_frame, text="📝 Dictate",
            command=self.start_dictation,
            font=('Arial', 12, 'bold'),
            bg='#cc6600', fg='white',
            relief='flat', padx=20, pady=10,
            cursor='hand2'
        )
        self.dictate_btn.pack(side='left', padx=(0, 10))
        
        # Send text button
        send_btn = tk.Button(
            button_frame, text="📤 Send",
            command=self.send_text_message,
            font=('Arial', 12, 'bold'),
            bg='#00cc66', fg='white',
            relief='flat', padx=20, pady=10,
            cursor='hand2'
        )
        send_btn.pack(side='left', padx=(0, 10))
        
        # Clear button
        clear_btn = tk.Button(
            button_frame, text="🗑️ Clear",
            command=self.clear_chat,
            font=('Arial', 10),
            bg='#444444', fg='white',
            relief='flat', padx=15, pady=10,
            cursor='hand2'
        )
        clear_btn.pack(side='right')
        
        # Initial message
        self.add_message("System", "🤖 Atulya Tantra ready! Click 'Start Voice Chat' for hands-free conversation or type below.", "system")
    
    def calibrate_microphone(self):
        """Calibrate microphone for ambient noise"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"⚠️  Microphone calibration warning: {e}")
    
    def add_message(self, sender, message, msg_type="user"):
        """Add message to chat display"""
        self.chat_display.config(state='normal')
        
        # Color coding
        colors = {
            "user": "#00aaff",
            "ai": "#00ff00",
            "system": "#ffaa00"
        }
        
        timestamp = time.strftime("%H:%M:%S")
        
        self.chat_display.insert('end', f"\n[{timestamp}] ", 'timestamp')
        self.chat_display.insert('end', f"{sender}: ", msg_type)
        self.chat_display.insert('end', f"{message}\n", 'message')
        
        # Configure tags
        self.chat_display.tag_config('timestamp', foreground='#666666')
        self.chat_display.tag_config(msg_type, foreground=colors.get(msg_type, '#ffffff'), font=('Arial', 11, 'bold'))
        self.chat_display.tag_config('message', foreground='#ffffff')
        
        self.chat_display.see('end')
        self.chat_display.config(state='disabled')
    
    def toggle_voice_conversation(self):
        """Toggle continuous voice conversation mode"""
        if not self.is_listening:
            self.start_voice_conversation()
        else:
            self.stop_voice_conversation()
    
    def start_voice_conversation(self):
        """Start continuous voice conversation"""
        self.is_listening = True
        self.voice_btn.config(text="🔴 Stop Voice Chat", bg='#cc0000')
        self.mode_label.config(text="Mode: Voice Conversation", fg='#00ff00')
        self.status_label.config(text="Listening...", fg='#00ff00')
        
        self.add_message("System", "🎤 Voice conversation started. Speak naturally - I'll respond with voice!", "system")
        
        # Start listening thread
        threading.Thread(target=self.voice_conversation_loop, daemon=True).start()
    
    def stop_voice_conversation(self):
        """Stop voice conversation"""
        self.is_listening = False
        self.voice_btn.config(text="🎤 Start Voice Chat", bg='#0066cc')
        self.mode_label.config(text="Mode: Idle", fg='#888888')
        self.status_label.config(text="Ready", fg='#00ff00')
        
        self.add_message("System", "Voice conversation stopped.", "system")
    
    def voice_conversation_loop(self):
        """Continuous voice conversation loop with interruption & accumulation"""
        while self.is_listening:
            try:
                # Listen for speech
                self.root.after(0, lambda: self.status_label.config(text="🎤 Listening...", fg='#00ff00'))
                print("[DEBUG] Listening for speech...")
                
                # Listen - shorter time limit for responsiveness
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=12)
                
                # Recognize speech
                self.root.after(0, lambda: self.status_label.config(text="🧠 Processing...", fg='#ffaa00'))
                print("[DEBUG] Processing audio...")
                
                try:
                    text = self.recognizer.recognize_google(audio)
                    
                    # Normalize casual speech (fix "h r u" → "how are you")
                    text = text.replace(" h r u", " how are you")
                    text = text.replace("h r u", "how are you")
                    text = text.replace(" u ", " you ")
                    text = text.replace(" r ", " are ")
                    
                    print(f"[DEBUG] Recognized: {text}")
                    
                    if text.strip():
                        # If AI is speaking, interrupt and accumulate
                        if self.is_speaking:
                            self.is_speaking = False  # Signal to stop
                            pygame.mixer.music.stop()
                            print("[DEBUG] Interrupting AI - accumulating message...")
                            self.pending_messages.append(text)
                            time.sleep(0.3)  # Brief pause
                            continue  # Keep listening for more
                        
                        # Check if we have pending messages to combine
                        if self.pending_messages:
                            combined = " ".join(self.pending_messages + [text])
                            self.pending_messages = []
                            print(f"[DEBUG] Combined {len(self.pending_messages)+1} messages: {combined}")
                            text = combined
                        
                        # Add user message
                        self.root.after(0, lambda t=text: self.add_message("You", t, "user"))
                        print(f"[DEBUG] Added user message to GUI")
                        
                        # Get AI response
                        print(f"[DEBUG] Getting AI response...")
                        response = self.get_ai_response(text)
                        print(f"[DEBUG] Got AI response: {response[:50]}...")
                        
                        # Add AI message
                        self.root.after(0, lambda r=response: self.add_message("Atulya", r, "ai"))
                        print(f"[DEBUG] Added AI message to GUI")
                        
                        # Speak response
                        print(f"[DEBUG] Speaking response...")
                        self.speak_response(response)
                
                except sr.UnknownValueError:
                    print("[DEBUG] No speech detected")
                    pass
                except sr.RequestError as e:
                    print(f"[DEBUG] Speech recognition error: {e}")
                    self.root.after(0, lambda: self.status_label.config(text="⚠️  Speech recognition error", fg='#ff0000'))
                except Exception as e:
                    print(f"[DEBUG] Recognition exception: {e}")
                    import traceback
                    traceback.print_exc()
                
            except sr.WaitTimeoutError:
                pass  # Timeout, continue listening
            except Exception as e:
                print(f"[DEBUG] Voice conversation error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)
        
        self.root.after(0, lambda: self.status_label.config(text="Ready", fg='#00ff00'))
    
    def start_dictation(self):
        """Start dictation mode - speech to text"""
        self.dictate_btn.config(text="🔴 Dictating...", bg='#cc0000')
        self.status_label.config(text="🎤 Dictation mode - speak now...", fg='#00ff00')
        
        threading.Thread(target=self.dictation_worker, daemon=True).start()
    
    def dictation_worker(self):
        """Dictation worker thread"""
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=30)
            
            # Recognize speech
            try:
                text = self.recognizer.recognize_google(audio)
                
                # Insert into text input
                self.root.after(0, lambda: self.text_input.insert('1.0', text + " "))
                self.root.after(0, lambda: self.status_label.config(text="✅ Dictation complete", fg='#00ff00'))
                
            except sr.UnknownValueError:
                self.root.after(0, lambda: self.status_label.config(text="⚠️  Could not understand speech", fg='#ff0000'))
            except sr.RequestError as e:
                self.root.after(0, lambda: self.status_label.config(text=f"⚠️  Error: {e}", fg='#ff0000'))
        
        except sr.WaitTimeoutError:
            self.root.after(0, lambda: self.status_label.config(text="⚠️  No speech detected", fg='#ff0000'))
        except Exception as e:
            print(f"Dictation error: {e}")
        finally:
            self.root.after(0, lambda: self.dictate_btn.config(text="📝 Dictate", bg='#cc6600'))
    
    def send_text_message(self):
        """Send text message to AI"""
        message = self.text_input.get('1.0', 'end').strip()
        
        if not message:
            return
        
        # Clear input
        self.text_input.delete('1.0', 'end')
        
        # Add user message
        self.add_message("You", message, "user")
        
        # Get AI response in thread
        threading.Thread(target=self.process_text_message, args=(message,), daemon=True).start()
    
    def process_text_message(self, message):
        """Process text message"""
        try:
            self.root.after(0, lambda: self.status_label.config(text="🧠 Thinking...", fg='#ffaa00'))
            
            response = self.get_ai_response(message)
            
            self.root.after(0, lambda: self.add_message("Atulya", response, "ai"))
            self.root.after(0, lambda: self.status_label.config(text="Ready", fg='#00ff00'))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.add_message("System", error_msg, "system"))
            self.root.after(0, lambda: self.status_label.config(text="Error", fg='#ff0000'))
    
    def get_ai_response(self, message):
        """Get response from Ollama AI with sentiment awareness"""
        try:
            # Detect user emotion for sentiment-aware responses
            try:
                import sys, os
                sys.path.insert(0, 'server')
                from services.sentiment_analyzer import sentiment_analyzer
                sentiment = sentiment_analyzer.analyze(message)
                emotion = sentiment['emotion']
                tone_guide = sentiment['tone_guidance']
            except:
                emotion = 'neutral'
                tone_guide = 'Be friendly and helpful.'
            
            # Extract user profile (name)
            user_name = None
            for hist_msg in self.conversation_history:
                if hist_msg.get('role') == 'user':
                    content = hist_msg.get('content', '').lower()
                    if 'my name is' in content or 'i am' in content or "i'm" in content:
                        words = content.split()
                        for i, word in enumerate(words):
                            if word in ['is', 'am'] and i + 1 < len(words):
                                user_name = words[i + 1].strip('.,!?').title()
                                break
            
            name_context = f" User's name: {user_name}." if user_name else ""
            
            messages = [
                {'role': 'system', 'content': f'''You are Atulya, JARVIS-like AI.{name_context}

User emotion: {emotion}. {tone_guide}

STRICT RULES:
- Simple greetings → "Hey! How can I help?" (ONE sentence, 4-6 words!)
- ALL responses → Max 1-2 sentences
- English only, warm tone
- Use user's name when known

Be brief, caring, adaptive to emotion.'''}
            ]
            
            # Add recent history
            for msg in self.conversation_history[-6:]:
                messages.append(msg)
            
            # Add current message  
            messages.append({'role': 'user', 'content': message})
            
            print(f"[DEBUG] Sending to AI: {message}")
            start_time = time.time()
            
            # Get response from Ollama - OPTIMIZED for speed + brevity
            try:
                # Detect if simple greeting
                is_simple = len(message.split()) <= 4 and any(word in message.lower() for word in ['hi', 'hello', 'hey', 'sup'])
                
                # Try gemma2:2b (FAST!) or fallback to phi3:mini
                try:
                    response = ollama.chat(
                        model='gemma2:2b',  # Much faster!
                        messages=messages,
                        options={
                            'num_predict': 10 if is_simple else 30,  # Ultra-short!
                            'temperature': 0.8,
                            'num_ctx': 512,
                            'top_k': 10,  # Even faster
                        }
                    )
                except:
                    # Fallback to phi3:mini if gemma2 not ready
                    response = ollama.chat(
                        model='phi3:mini',
                        messages=messages,
                        options={
                            'num_predict': 10 if is_simple else 30,
                            'temperature': 0.8,
                            'num_ctx': 512,
                            'top_k': 10,
                        }
                    )
                elapsed = time.time() - start_time
                print(f"[DEBUG] AI responded in {elapsed:.1f}s")
            except Exception as e:
                print(f"[DEBUG] Ollama error: {e}")
                return f"Error getting response: {e}"
            
            # Get response content
            if not response or 'message' not in response:
                print(f"[DEBUG] Invalid response format: {response}")
                return "Error: Invalid response from AI"
            
            ai_message = response['message']['content'].strip()
            print(f"[DEBUG] Raw AI response: {ai_message[:100]}...")
            
            # Remove thinking output if present
            if '...done thinking.' in ai_message:
                parts = ai_message.split('...done thinking.')
                ai_message = parts[-1].strip()
            elif 'Thinking...' in ai_message:
                parts = ai_message.split('Thinking...')
                if len(parts) > 1:
                    ai_message = parts[-1].strip()
            
            # Remove emojis, special characters, and non-English text
            import re
            # Remove emojis and special chars
            ai_message = re.sub(r'[^\w\s.,!?\'-]', '', ai_message)
            # Remove anything that looks like instructions or prompts
            if '---' in ai_message:
                ai_message = ai_message.split('---')[0].strip()
            if 'Instruction' in ai_message:
                ai_message = ai_message.split('Instruction')[0].strip()
            # Clean spaces
            ai_message = ' '.join(ai_message.split())
            
            if not ai_message:
                ai_message = "I'm here, how can I help?"
            
            print(f"[DEBUG] Final cleaned response: {ai_message}")
            
            # Store in history
            self.conversation_history.append({'role': 'user', 'content': message})
            self.conversation_history.append({'role': 'assistant', 'content': ai_message})
            
            # Keep history manageable
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            return ai_message
            
        except ollama.ResponseError as e:
            if "model" in str(e).lower():
                return "⚠️  Qwen 3:8b model not found. Run: ollama pull qwen3:8b"
            return f"⚠️  Ollama error: {e}"
        except Exception as e:
            return f"⚠️  Error: {e}"
    
    def speak_response(self, text):
        """Speak AI response using TTS"""
        if self.is_speaking:
            return
        
        threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()
    
    def on_typing(self):
        """Show typing indicator"""
        if hasattr(self, 'typing_timer'):
            self.root.after_cancel(self.typing_timer)
        
        self.typing_indicator.pack(side='right', padx=5)
        self.typing_timer = self.root.after(1000, lambda: self.typing_indicator.pack_forget())
    
    def _speak_worker(self, text):
        """TTS worker thread - can be interrupted"""
        try:
            self.is_speaking = True
            self.root.after(0, lambda: self.status_label.config(text="🔊 Speaking...", fg='#00aaff'))
            print(f"[DEBUG] TTS: Generating audio for: {text[:50]}...")
            
            # Generate speech
            communicate = edge_tts.Communicate(text, 'en-US-AriaNeural')
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_audio = temp_file.name
            
            print(f"[DEBUG] TTS: Saving audio to {temp_audio}")
            
            # Save audio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(communicate.save(temp_audio))
            loop.close()
            
            print(f"[DEBUG] TTS: Audio saved, now playing...")
            
            # Play audio - but check if new speech detected (interrupt)
            pygame.mixer.music.load(temp_audio)
            pygame.mixer.music.play()
            
            # Monitor for interruption
            while pygame.mixer.music.get_busy() and self.is_speaking:
                time.sleep(0.1)
                # If user starts talking, stop current playback
                if not self.is_speaking:
                    pygame.mixer.music.stop()
                    print("[DEBUG] TTS interrupted by new input")
            
            print(f"[DEBUG] TTS: Playback complete")
            
            # Cleanup - wait a bit to ensure file is released
            time.sleep(0.2)
            try:
                os.unlink(temp_audio)
            except:
                pass  # File still locked, will be cleaned by OS
            
        except Exception as e:
            print(f"[DEBUG] TTS error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_speaking = False
            if not self.is_listening:
                self.root.after(0, lambda: self.status_label.config(text="Ready", fg='#00ff00'))
    
    def clear_chat(self):
        """Clear chat display"""
        self.chat_display.config(state='normal')
        self.chat_display.delete('1.0', 'end')
        self.chat_display.config(state='disabled')
        self.conversation_history.clear()
        self.add_message("System", "Chat cleared.", "system")
    
    def run(self):
        """Run the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing"""
        self.is_listening = False
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        self.root.destroy()

def main():
    """Main entry point"""
    print("🤖 Starting Atulya Tantra Voice GUI...")
    print("=" * 50)
    
    # Check dependencies
    try:
        import ollama
        ollama_available = True
        print("✅ Ollama connection ready")
    except:
        print("⚠️  Ollama not available")
        ollama_available = False
    
    # Check model
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, timeout=3)
        if b'qwen3:8b' in result.stdout:
            print("✅ Qwen 3:8b model ready")
        else:
            print("⚠️  Model not found - run: ollama pull qwen3:8b")
    except:
        pass
    
    print("\n🎤 Voice GUI Features:")
    print("  • Voice Conversation - Continuous hands-free chat")
    print("  • Dictation Mode - Speech to text")
    print("  • Text Chat - Type messages")
    print("  • All modes work together!")
    print("=" * 50)
    
    # Launch GUI
    app = VoiceGUI()
    app.run()

if __name__ == "__main__":
    main()

