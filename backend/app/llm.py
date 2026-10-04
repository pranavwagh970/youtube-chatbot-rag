from app.config import Settings
from app.rag_pipeline import RetrievedChunk
from app.time_utils import format_range


class GeminiAnswerer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured.")

            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def answer(self, question: str, retrieved_chunks: list[RetrievedChunk]) -> str:
        context = self._build_context(retrieved_chunks)
        prompt = f"""
You are answering questions about a YouTube video transcript.

Rules:
- Use only the provided transcript context.
- If the answer is not in the context, say you cannot tell from this video.
- Keep the answer concise and helpful.
- Cite the relevant timestamp range when possible.

Transcript context:
{context}

Question:
{question}
"""

        response = self.client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
        )
        return (response.text or "").strip()

    @staticmethod
    def _build_context(retrieved_chunks: list[RetrievedChunk]) -> str:
        blocks: list[str] = []
        for item in retrieved_chunks:
            chunk = item.chunk
            timestamp = format_range(chunk.start, chunk.end)
            blocks.append(f"Source {chunk.chunk_id} ({timestamp}):\n{chunk.text}")
        return "\n\n".join(blocks)
