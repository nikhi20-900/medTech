# MEDET

**MEDET** is an AI-powered rural healthcare assistant for underserved communities. It is not a generic chatbot. The product is built to feel like a compassionate healthcare companion: it asks follow-up questions, explains next steps in simple language, flags likely emergencies, and always points people toward professional care.

This repository contains both the **Next.js frontend** and the **FastAPI backend**.

> **Medical disclaimer:** MEDET does not diagnose, prescribe medication, or replace a clinician. In an emergency, call local emergency services immediately.

## Features

- Symptom triage with category, severity, duration, and missing-info detection
- Deterministic emergency detection (chest pain, breathing trouble, unconsciousness, severe bleeding, and similar high-risk language)
- Clinical safety filter that strips unsafe diagnoses, dosages, and self-treatment advice from model output
- Multi-turn conversation state so the assistant does not re-ask facts already collected
- Structured healthcare cards (emergency, hydration, nutrition, follow-up, and related actions)
- Multilingual UI and backend copy: English, Hindi, Bengali, Nepali, Tamil, Kannada, and Marathi
- Voice-oriented screens for lower-literacy and hands-free use
- Nearby clinics, family health profiles, and medicine reminders (with local fallbacks when remote APIs are unavailable)

## Repository layout

```
medTech/
├── medet-codex-medet-frontend-intelligence/   # Next.js 16 + React 19 app
├── medet-codex-medet-backend-intelligence/    # FastAPI triage + safety service
└── medet_backend_analysis.md                  # Backend architecture notes
```

| App | Path | Stack |
| --- | --- | --- |
| Frontend | `medet-codex-medet-frontend-intelligence` | Next.js 16, React 19, Tailwind CSS 4, Framer Motion, shadcn/ui |
| Backend | `medet-codex-medet-backend-intelligence` | FastAPI, Pydantic, Ollama (`qwen3:4b`) |

## How it works

1. The user describes symptoms in the chat or voice UI.
2. The backend classifies the message (category, severity, duration, gaps).
3. Conversation state is updated so follow-up questions stay relevant.
4. A local LLM (Ollama) generates a response using a policy-aware prompt.
5. Safety guards, emergency flags, and healthcare cards are attached before the JSON is returned to the client.

```
Next.js UI  →  POST /medet/chat (or /medet/chat/stream)
FastAPI     →  triage → state → Ollama → safety filter → MedetResponse
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.12+
- [Ollama](https://ollama.com) running locally, with the `qwen3:4b` model pulled

```bash
ollama serve
ollama pull qwen3:4b
```

## Run the backend

```bash
cd medet-codex-medet-backend-intelligence
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic ollama pytest httpx
uvicorn backend.app.main:app --reload --port 8000
```

Useful endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/medet/chat` | Structured (non-streaming) reply |
| `POST` | `/medet/chat/stream` | SSE stream: `token` events, then `metadata` |

Example request:

```bash
curl -X POST http://localhost:8000/medet/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I have had a fever for 3 days","language":"en","input_type":"text"}'
```

Run tests:

```bash
cd medet-codex-medet-backend-intelligence
source .venv/bin/activate
pytest
```

## Run the frontend

```bash
cd medet-codex-medet-frontend-intelligence
npm install
```

Create `.env.local` if you want the UI to talk to the FastAPI server:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MEDET_API_PREFIX=/medet
```

Without `NEXT_PUBLIC_API_URL`, the app uses `/api` and local fallbacks for auth, profiles, reminders, and nearby clinics.

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

| Route | Screen |
| --- | --- |
| `/` | Landing |
| `/chat` | Symptom chat |
| `/voice` | Voice mode |
| `/emergency` | Emergency panel |
| `/nearby` | Nearby clinics |
| `/reminders` | Medicine reminders |
| `/profile` | Family health profiles |
| `/language` | Language selection |
| `/login` | Sign in |

## Supported languages

`en`, `hi`, `bn`, `ne`, `ta`, `kn`, and `mr` (Marathi in the UI; the backend currently maps Marathi to Hindi for model calls).

## Safety model

Clinical safety is enforced in code, not only in prompts:

- **Input:** keyword and regex emergency detection, with basic negation handling
- **State:** facts already collected are kept so the assistant does not loop on the same questions
- **Output:** a medical safety guard removes overconfident diagnoses, dosages, and dangerous self-treatment language

MEDET is a triage and guidance layer. It should never be treated as a diagnosis engine.

## License

No license file is included yet. All rights remain with the repository owner unless a license is added.
