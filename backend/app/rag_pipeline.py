import bisect
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.rag_types import RAGChunk
from app.storage import IndexStorage
from app.time_utils import format_timestamp
from app.youtube_loader import TranscriptSegment


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
}


@dataclass
class VideoIndex:
    index: Any
    chunks: list[RAGChunk]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: RAGChunk
    score: float


class RAGPipeline:
    def __init__(self, settings: Settings, storage: IndexStorage):
        self.settings = settings
        self.storage = storage
        self._embedding_model: Any | None = None
        self._loaded_indexes: dict[str, VideoIndex] = {}

    @property
    def embedding_model(self) -> Any:
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.settings.embedding_model)
        return self._embedding_model

    def has_index(self, video_id: str) -> bool:
        return video_id in self._loaded_indexes or self.storage.exists(video_id)

    def get_index(self, video_id: str) -> VideoIndex:
        if video_id not in self._loaded_indexes:
            if not self.storage.exists(video_id):
                raise FileNotFoundError("Load this video before asking questions.")
            index, chunks = self.storage.load(video_id)
            self._loaded_indexes[video_id] = VideoIndex(index=index, chunks=chunks)
        return self._loaded_indexes[video_id]

    def build_index(
        self,
        video_id: str,
        segments: list[TranscriptSegment],
        title: str,
    ) -> VideoIndex:
        import faiss

        chunks = self._chunk_transcript(segments)
        if not chunks:
            raise ValueError("Transcript could not be split into searchable chunks.")

        vectors = self._embed([chunk.text for chunk in chunks])
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        video_index = VideoIndex(index=index, chunks=chunks)
        self.storage.save(video_id, index, chunks, title)
        self._loaded_indexes[video_id] = video_index
        return video_index

    def retrieve(self, video_id: str, question: str, top_k: int) -> list[RetrievedChunk]:
        if self.settings.retrieval_mode == "keyword":
            return self._retrieve_keyword(video_id, question, top_k)

        video_index = self.get_index(video_id)
        query_vector = self._embed([question])
        scores, indices = video_index.index.search(query_vector, top_k)

        retrieved: list[RetrievedChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            retrieved.append(RetrievedChunk(chunk=video_index.chunks[int(idx)], score=float(score)))
        return retrieved

    def _retrieve_keyword(self, video_id: str, question: str, top_k: int) -> list[RetrievedChunk]:
        chunks = self._get_chunks(video_id)
        query_terms = self._tokenize(question)

        if not query_terms:
            return [RetrievedChunk(chunk=chunk, score=0.0) for chunk in chunks[:top_k]]

        query_counts = Counter(query_terms)
        scored: list[RetrievedChunk] = []

        for chunk in chunks:
            chunk_terms = self._tokenize(chunk.text)
            if not chunk_terms:
                continue

            chunk_counts = Counter(chunk_terms)
            overlap_score = sum(
                min(query_count, chunk_counts.get(term, 0))
                for term, query_count in query_counts.items()
            )
            if overlap_score == 0:
                continue

            # Normalize lightly so giant chunks do not win only by being longer.
            score = overlap_score / math.sqrt(len(chunk_terms))
            scored.append(RetrievedChunk(chunk=chunk, score=score))

        if not scored:
            return [RetrievedChunk(chunk=chunk, score=0.0) for chunk in chunks[:top_k]]

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _get_chunks(self, video_id: str) -> list[RAGChunk]:
        if video_id in self._loaded_indexes:
            return self._loaded_indexes[video_id].chunks
        if not self.storage.exists(video_id):
            raise FileNotFoundError("Load this video before asking questions.")
        chunks = self.storage.load_chunks(video_id)
        self._loaded_indexes[video_id] = VideoIndex(index=None, chunks=chunks)
        return chunks

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [
            token
            for token in (match.group(0).lower() for match in TOKEN_RE.finditer(text))
            if token not in STOP_WORDS and len(token) > 1
        ]

    def _embed(self, texts: list[str]) -> Any:
        import numpy as np

        vectors = self.embedding_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype="float32")

    def _chunk_transcript(self, segments: list[TranscriptSegment]) -> list[RAGChunk]:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        transcript_text, starts, ends, offsets = self._format_transcript(segments)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        split_texts = splitter.split_text(transcript_text)
        chunks: list[RAGChunk] = []
        search_from = 0

        for chunk_id, text in enumerate(split_texts):
            start_pos = transcript_text.find(text, search_from)
            if start_pos == -1:
                start_pos = transcript_text.find(text)
            if start_pos == -1:
                start_pos = search_from

            end_pos = start_pos + len(text)
            search_from = max(start_pos + 1, end_pos - self.settings.chunk_overlap)

            first_segment_idx = max(0, bisect.bisect_right(offsets, start_pos) - 1)
            last_segment_idx = max(0, bisect.bisect_right(offsets, end_pos) - 1)
            last_segment_idx = min(last_segment_idx, len(segments) - 1)

            chunks.append(
                RAGChunk(
                    chunk_id=chunk_id,
                    text=text.strip(),
                    start=starts[first_segment_idx],
                    end=ends[last_segment_idx],
                )
            )

        return chunks

    @staticmethod
    def _format_transcript(
        segments: list[TranscriptSegment],
    ) -> tuple[str, list[float], list[float], list[int]]:
        lines: list[str] = []
        starts: list[float] = []
        ends: list[float] = []
        offsets: list[int] = []
        cursor = 0

        for segment in segments:
            line = f"[{format_timestamp(segment.start)}] {segment.text}"
            offsets.append(cursor)
            starts.append(segment.start)
            ends.append(segment.end)
            lines.append(line)
            cursor += len(line) + 1

        return "\n".join(lines), starts, ends, offsets
