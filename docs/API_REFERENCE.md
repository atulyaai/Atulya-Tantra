# API Reference

Base URL: `http://localhost:8000`

## Authentication

Most endpoints require a bearer token via `X-Atulya-Token` header or `Authorization: Bearer <token>` header.

## Agent

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agent/status` | List registered tools and agent status |
| POST | `/api/agent/process` | Send user input to agent loop |
| GET | `/api/agent/tools` | List available tools |
| GET | `/api/agent/schemas` | Get JSON tool schemas |

### POST /api/agent/process

```json
{"input": "set a reminder for 5 minutes", "history": null}
→ {"status": "success", "reply": "Reminder set for 5 minutes"}
```

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Login with credentials |
| POST | `/api/auth/register` | Register new user |
| GET | `/api/auth/session` | Get current session |

## Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message to LLM |
| GET | `/api/chat/history` | Get chat history |

## Cortex (Model Management)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cortex/status` | Cortex system status |
| POST | `/api/cortex/train` | Start training |
| GET | `/api/cortex/checkpoints` | List checkpoints |
| GET | `/api/cortex/logs` | Training logs |

## Voice

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/voice/voices` | List available voices |
| POST | `/api/voice/tts` | Text-to-speech |
| POST | `/api/voice/chat` | Voice chat endpoint |

## Model (OpenAI-compatible)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/models` | List models (OpenAI API) |

## Upload

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | Upload file (max 50MB) |
| GET | `/api/files` | List uploaded files |
| GET | `/api/files/{username}/{file_id}` | Download file |
| DELETE | `/api/files/{file_id}` | Delete file |

## Devices

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | List devices |
| POST | `/api/devices` | Register device |
| POST | `/api/devices/{id}/command` | Send command |
| GET | `/api/devices/stats` | Device stats |
| DELETE | `/api/devices/{id}` | Remove device |

## Notifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/notifications/subscribe` | Subscribe to push |
| POST | `/api/notifications/unsubscribe` | Unsubscribe |
| POST | `/api/notifications/test` | Test notification |

## WebSocket

| Protocol | Path | Description |
|----------|------|-------------|
| WebSocket | `/api/ws` | Real-time events |

## Automation / Cron

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cron/jobs` | List cron jobs |
| POST | `/api/cron/jobs` | Create cron job |
| DELETE | `/api/cron/jobs/{id}` | Delete job |
| PATCH | `/api/cron/jobs/{id}` | Update job |
| POST | `/api/cron/jobs/{id}/run` | Run job immediately |

## System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system/status` | System status |
| GET | `/api/system/health` | Health check |

## Training

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/train/start` | Start training run |
| GET | `/api/train/status` | Training status |
| GET | `/api/train/datasets` | List datasets |
