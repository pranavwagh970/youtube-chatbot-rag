import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.rag_types import RAGChunk


def _fallback_metadata(video_id: str) -> dict[str, str]:
    return {"video_id": video_id, "title": video_id}


class IndexStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def video_dir(self, video_id: str) -> Path:
        return self.root / video_id

    def exists(self, video_id: str) -> bool:
        directory = self.video_dir(video_id)
        return (directory / "index.faiss").exists() and (directory / "chunks.json").exists()

    def metadata_path(self, video_id: str) -> Path:
        return self.video_dir(video_id) / "metadata.json"

    def read_metadata(self, video_id: str) -> dict[str, str]:
        path = self.metadata_path(video_id)
        if not path.exists():
            return _fallback_metadata(video_id)

        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _fallback_metadata(video_id)

        return {
            "video_id": str(metadata.get("video_id") or video_id),
            "title": str(metadata.get("title") or video_id),
        }

    def list_videos(self) -> list[dict[str, str | int]]:
        videos: list[dict[str, str | int]] = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or not self.exists(directory.name):
                continue

            try:
                payload = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            metadata = self.read_metadata(directory.name)
            videos.append(
                {
                    "video_id": metadata["video_id"],
                    "title": metadata["title"],
                    "chunks": len(payload),
                }
            )
        return videos

    def save(self, video_id: str, index: Any, chunks: list[RAGChunk], title: str) -> None:
        import faiss

        directory = self.video_dir(video_id)
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(directory / "index.faiss"))

        chunk_payload = [asdict(chunk) for chunk in chunks]
        (directory / "chunks.json").write_text(
            json.dumps(chunk_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.save_metadata(video_id=video_id, title=title)

    def save_metadata(self, video_id: str, title: str) -> None:
        directory = self.video_dir(video_id)
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"video_id": video_id, "title": title or video_id}
        self.metadata_path(video_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, video_id: str) -> tuple[Any, list[RAGChunk]]:
        import faiss

        directory = self.video_dir(video_id)
        index = faiss.read_index(str(directory / "index.faiss"))
        chunks = self.load_chunks(video_id)
        return index, chunks

    def load_chunks(self, video_id: str) -> list[RAGChunk]:
        directory = self.video_dir(video_id)
        payload = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
        return [RAGChunk(**item) for item in payload]
