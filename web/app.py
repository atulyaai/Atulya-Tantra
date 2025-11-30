"""
Atulya Tantra - Web Interface
Thin wrapper around TantraEngine
"""

import os
import sys
import logging
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atulya_tantra import TantraEngine

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/atulya.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
CORS(app)

# Global Engine
engine = None

def initialize_engine():
    """Initialize the Tantra Engine"""
    global engine
    if engine is not None:
        return True
        
    try:
        hf_token = os.getenv('HUGGINGFACE_TOKEN')
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'cache')
        device = os.getenv('DEVICE', 'cpu')
        text_model_name = os.getenv('TEXT_MODEL_NAME', 'Qwen/Qwen2.5-1.5B-Instruct')
        
        engine = TantraEngine(
            text_model_name=text_model_name,
            device=device,
            hf_token=hf_token,
            cache_dir=cache_dir
        )
        return True
    except Exception as e:
        logger.error(f"Failed to initialize engine: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    if not engine:
        if not initialize_engine():
            return jsonify({'error': 'AI Engine failed to initialize'}), 500
            
    try:
        data = request.json
        user_message = data.get('message', '')
        image_data = data.get('image', None)
        
        if not user_message and not image_data:
            return jsonify({'error': 'No message provided'}), 400
            
        # Delegate to Engine
        response_text = engine.process_message(user_message, image_data)
        
        return jsonify({'response': response_text})

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/voice/synthesize', methods=['POST'])
def synthesize_voice():
    """Legacy endpoint - kept for compatibility but mostly unused"""
    return jsonify({'error': 'Use browser TTS'}), 400

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    # Initialize engine on startup
    if initialize_engine():
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    else:
        logger.error("Failed to start application due to engine initialization failure")
