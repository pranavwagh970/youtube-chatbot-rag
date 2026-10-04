# YouTube RAG Chat

A minimal full-stack app for chatting with YouTube videos using transcript retrieval, MiniLM embeddings, FAISS vector search, and Gemini answer generation.

## Architecture

```text
React + Vite frontend
        |
FastAPI backend
        |
YouTube transcript -> timestamped chunks -> MiniLM embeddings -> FAISS
        |
Gemini answer with source timestamps
```

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Set `GEMINI_API_KEY` in `backend/.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://localhost:8000` by default. To override it, create `frontend/.env`:

```text
VITE_API_BASE_URL=http://localhost:8000
```

## Deployment Shape

- Frontend: Vercel static site
- Backend: Render or Railway web service
- Secret: `GEMINI_API_KEY` only on backend
- Optional persistence: mount backend storage at `INDEX_DIR`

## API

```text
GET  /health
GET  /api/videos
POST /api/videos/load
POST /api/chat
```

## Stored Videos

The app saves each indexed video under `backend/storage/indexes/<video_id>`. The frontend shows these stored videos so a user can select one and ask questions without loading a URL first.

For a deployed demo, load at least one video once after deployment so it appears in the stored-video picker. If the backend uses ephemeral storage, add a persistent disk/volume for `INDEX_DIR`.

This repo includes one pre-indexed demo video so the deployed app can work even when YouTube blocks transcript requests from cloud hosts:

```text
aircAruvnKk - But what is a neural network? | Deep learning chapter 1
```

