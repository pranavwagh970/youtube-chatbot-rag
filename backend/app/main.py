from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.llm import GeminiAnswerer
from app.rag_pipeline import RAGPipeline
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    LoadVideoRequest,
    SourceChunk,
    StoredVideo,
    StoredVideosResponse,
    VideoLoadResponse,
)
from app.storage import IndexStorage
from app.time_utils import format_range
from app.youtube_loader import extract_video_id, fetch_transcript
from app.youtube_loader import fetch_video_title

settings = get_settings()
storage = IndexStorage(settings.index_dir)
rag = RAGPipeline(settings=settings, storage=storage)
answerer = GeminiAnswerer(settings=settings)

app = FastAPI(
    title="YouTube RAG Chat API",
    version="0.1.0",
)

allowed_origins = {
    settings.frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/videos", response_model=StoredVideosResponse)
def list_videos() -> StoredVideosResponse:
    videos: list[StoredVideo] = []
    for video in storage.list_videos():
        video_id = str(video["video_id"])
        title = str(video["title"])
        if title == video_id:
            title = fetch_video_title(video_id)
            storage.save_metadata(video_id=video_id, title=title)

        videos.append(
            StoredVideo(
                video_id=video_id,
                title=title,
                chunks=int(video["chunks"]),
            )
        )
    return StoredVideosResponse(videos=videos)


@app.post("/api/videos/load", response_model=VideoLoadResponse)
def load_video(payload: LoadVideoRequest) -> VideoLoadResponse:
    try:
        video_id = extract_video_id(payload.youtube_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if rag.has_index(video_id) and not payload.force_refresh:
        video_index = rag.get_index(video_id)
        metadata = storage.read_metadata(video_id)
        return VideoLoadResponse(
            video_id=video_id,
            title=metadata["title"],
            chunks=len(video_index.chunks),
            cached=True,
            message="Video is ready to chat.",
        )

    try:
        title = fetch_video_title(video_id)
        segments = fetch_transcript(video_id, language=payload.language)
        video_index = rag.build_index(video_id, segments, title)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load video: {exc}") from exc

    return VideoLoadResponse(
        video_id=video_id,
        title=title,
        chunks=len(video_index.chunks),
        cached=False,
        message="Video indexed successfully.",
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        retrieved = rag.retrieve(payload.video_id, question, payload.top_k)
        answer = answerer.answer(question, retrieved)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not answer question: {exc}") from exc

    sources = [
        SourceChunk(
            chunk_id=item.chunk.chunk_id,
            text=item.chunk.text,
            start=item.chunk.start,
            end=item.chunk.end,
            timestamp=format_range(item.chunk.start, item.chunk.end),
            score=item.score,
        )
        for item in retrieved
    ]
    return ChatResponse(answer=answer, sources=sources)
