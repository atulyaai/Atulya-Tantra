# Atulya Tantra Server

Server-client architecture for multi-device AI access.

## 🚀 Quick Start

```bash
# Start server
cd server
python main.py
```

Server runs on: `http://localhost:8000`
WebSocket: `ws://localhost:8000/ws`
API Docs: `http://localhost:8000/docs`

## 📡 API Endpoints

### REST API

**Health Check:**
```
GET /
```

**Chat (Multi-model):**
```
POST /api/chat
Body: {
  "message": "your message",
  "model": "phi3:mini",  # optional
  "conversation_id": "conv_123"  # optional
}
```

**List Models:**
```
GET /api/models
```

**Save Memory:**
```
POST /api/memory/save
Body: {
  "conversation_id": "conv_123",
  "user_message": "hello",
  "assistant_response": "hi there",
  "model": "phi3:mini"
}
```

### WebSocket

```
WS /ws
Send: {"message": "hello", "model": "phi3:mini"}
Receive: {"message": "AI response"}
```

## 🎯 Multi-Model Router

Automatic routing based on content:
- Code questions → `codellama`
- Image analysis → `llama3.2-vision`
- Complex reasoning → `mistral`
- General chat → `phi3:mini`

Or specify model explicitly in request.

## 🏗️ Architecture

```
server/
├── main.py              # FastAPI server
├── config.py            # Settings
├── models/
│   └── model_router.py  # Multi-model routing
└── services/
    ├── ai_service.py    # AI inference
    └── memory_service.py # Conversation memory
```

## 📱 Connect from Anywhere

- Desktop app (Windows/Linux/Mac)
- Web browser
- Mobile browser
- CLI client
- Custom API clients

All connect to same server!

