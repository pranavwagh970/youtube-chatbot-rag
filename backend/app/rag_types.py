from dataclasses import dataclass


@dataclass(frozen=True)
class RAGChunk:
    chunk_id: int
    text: str
    start: float
    end: float
