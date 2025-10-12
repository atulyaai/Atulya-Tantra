"""
System Tray Application for Atulya Tantra
Runs in background, always-on with wake word detection
Cross-platform (Windows, Linux, Mac)
"""

import sys
import threading
import time
from pathlib import Path

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image, ImageDraw
except ImportError:
    print("⚠️  Install: pip install pystray pillow")
    sys.exit(1)

class AtulyaTrayApp:
    """System tray application for Atulya"""
    
    def __init__(self):
        self.icon = None
        self.is_wake_word_active = False
        self.is_server_running = False
        
    def create_icon_image(self, color='cyan'):
        """Create system tray icon image"""
        # Create a 64x64 image with a circle
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), 'black')
        draw = ImageDraw.Draw(image)
        
        # Draw circle (AI brain)
        draw.ellipse([8, 8, 56, 56], fill=color, outline='white', width=2)
        
        # Draw "A" in center
        draw.text((22, 18), 'A', fill='black')
        
        return image
    
    def toggle_wake_word(self, icon, item):
        """Toggle wake word detection"""
        self.is_wake_word_active = not self.is_wake_word_active
        
        if self.is_wake_word_active:
            print("🎤 Wake word detection started...")
            self.start_wake_word_detection()
            icon.icon = self.create_icon_image('green')
        else:
            print("🔇 Wake word detection stopped")
            self.stop_wake_word_detection()
            icon.icon = self.create_icon_image('cyan')
    
    def toggle_server(self, icon, item):
        """Toggle server"""
        self.is_server_running = not self.is_server_running
        
        if self.is_server_running:
            print("🚀 Starting server...")
            self.start_server()
        else:
            print("🛑 Stopping server...")
            self.stop_server()
    
    def start_wake_word_detection(self):
        """Start wake word detection in background"""
        try:
            from wake_word.detector import WakeWordDetector
            
            def on_wake_word(text):
                print(f"\n✨ Atulya activated! You said: '{text}'")
                # Launch voice GUI
                import subprocess
                subprocess.Popen([sys.executable, "voice_gui.py"])
            
            self.wake_detector = WakeWordDetector(callback=on_wake_word)
            self.wake_detector.start()
            
        except Exception as e:
            print(f"⚠️  Wake word error: {e}")
    
    def stop_wake_word_detection(self):
        """Stop wake word detection"""
        if hasattr(self, 'wake_detector'):
            self.wake_detector.stop()
    
    def start_server(self):
        """Start FastAPI server in background"""
        import subprocess
        self.server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=Path(__file__).parent
        )
        print("✅ Server started on http://localhost:8000")
    
    def stop_server(self):
        """Stop server"""
        if hasattr(self, 'server_process'):
            self.server_process.terminate()
            print("✅ Server stopped")
    
    def show_status(self, icon, item):
        """Show current status"""
        print("\n" + "=" * 50)
        print("🤖 Atulya Tantra Status")
        print("=" * 50)
        print(f"Wake Word: {'🟢 Active' if self.is_wake_word_active else '🔴 Inactive'}")
        print(f"Server: {'🟢 Running' if self.is_server_running else '🔴 Stopped'}")
        print(f"Model: phi3:mini")
        print("=" * 50)
    
    def open_voice_gui(self, icon, item):
        """Open voice GUI"""
        import subprocess
        subprocess.Popen([sys.executable, "voice_gui.py"])
    
    def open_web_client(self, icon, item):
        """Open web client in browser"""
        import webbrowser
        webbrowser.open('http://localhost:8000')
    
    def quit_app(self, icon, item):
        """Quit application"""
        print("\n👋 Shutting down Atulya Tantra...")
        
        # Stop wake word
        if self.is_wake_word_active:
            self.stop_wake_word_detection()
        
        # Stop server
        if self.is_server_running:
            self.stop_server()
        
        icon.stop()
    
    def run(self):
        """Run system tray application"""
        # Create menu
        menu = Menu(
            MenuItem('🤖 Atulya Tantra', None, enabled=False),
            Menu.SEPARATOR,
            MenuItem('🎤 Voice GUI', self.open_voice_gui),
            MenuItem('🌐 Web Client', self.open_web_client),
            Menu.SEPARATOR,
            MenuItem(
                '🎙️ Wake Word Detection',
                self.toggle_wake_word,
                checked=lambda item: self.is_wake_word_active
            ),
            MenuItem(
                '🚀 Server',
                self.toggle_server,
                checked=lambda item: self.is_server_running
            ),
            Menu.SEPARATOR,
            MenuItem('📊 Status', self.show_status),
            MenuItem('❌ Quit', self.quit_app)
        )
        
        # Create icon
        icon_image = self.create_icon_image('cyan')
        self.icon = Icon('Atulya Tantra', icon_image, 'Atulya Tantra AI', menu)
        
        # Run (blocks until quit)
        print("🤖 Atulya Tantra running in system tray")
        print("Right-click tray icon for options")
        self.icon.run()

def main():
    """Main entry point"""
    print("=" * 50)
    print("🤖 Atulya Tantra - System Tray Mode")
    print("=" * 50)
    print()
    print("Starting system tray application...")
    print("Look for the 🤖 icon in your system tray!")
    print()
    
    app = AtulyaTrayApp()
    app.run()

if __name__ == "__main__":
    main()

