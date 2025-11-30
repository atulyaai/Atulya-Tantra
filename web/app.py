"""
Atulya Tantra - Web Interface
Thin wrapper around TantraEngine
"""

import os
import sys
import json
import logging
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from dotenv import load_dotenv

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atulya_tantra import TantraEngine
from atulya_tantra.config_loader import get_config

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

# Add Prometheus metrics
metrics = PrometheusMetrics(app)
metrics.info('app_info', 'Atulya Tantra Web Interface', version='2.0.0')

# Global Engine
engine = None

def initialize_engine():
    """Initialize the Tantra Engine"""
    global engine
    if engine is not None:
        return True
        
    try:
        logger.info("Initializing Tantra Engine...")
        hf_token = os.getenv('HUGGINGFACE_TOKEN')
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'cache')
        
        # Use config loader for dynamic configuration
        engine = TantraEngine(
            hf_token=hf_token,
            cache_dir=cache_dir
        )
        logger.info("Tantra Engine initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize engine: {e}", exc_info=True)
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

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Streaming chat endpoint for real-time responses"""
    if not engine:
        if not initialize_engine():
            return jsonify({'error': 'AI Engine failed to initialize'}), 500
    
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        def generate():
            try:
                # Get the full response (we'll simulate streaming for now)
                response_text = engine.process_message(user_message, None)
                
                # Stream word by word for better UX
                words = response_text.split()
                for i, word in enumerate(words):
                    token = word + (' ' if i < len(words) - 1 else '')
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return app.response_class(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    
    except Exception as e:
        logger.error(f"Chat stream error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    # Initialize engine on startup
    if initialize_engine():
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    else:
        logger.error("Failed to start application due to engine initialization failure")
