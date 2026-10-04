from pydantic import BaseModel, Field


class LoadVideoRequest(BaseModel):
    youtube_url: str = Field(..., min_length=1)
    language: str = Field(default="en", min_length=2, max_length=12)
    force_refresh: bool = False


class VideoLoadResponse(BaseModel):
    video_id: str
    title: str
    chunks: int
    cached: bool
    message: str


class StoredVideo(BaseModel):
    video_id: str
    title: str
    chunks: int


class StoredVideosResponse(BaseModel):
    videos: list[StoredVideo]


class ChatRequest(BaseModel):
    video_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=8)


class SourceChunk(BaseModel):
    chunk_id: int
    text: str
    start: float
    end: float
    timestamp: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class HealthResponse(BaseModel):
    status: str
