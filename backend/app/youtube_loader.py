import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, urlparse

from youtube_transcript_api import YouTubeTranscriptApi


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


def extract_video_id(value: str) -> str:
    candidate = value.strip()
    if VIDEO_ID_RE.match(candidate):
        return candidate

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "youtu.be" in host and path_parts:
        video_id = path_parts[0]
    elif "youtube.com" in host or "youtube-nocookie.com" in host:
        query_video_id = parse_qs(parsed.query).get("v", [""])[0]
        if query_video_id:
            video_id = query_video_id
        elif path_parts and path_parts[0] in {"embed", "shorts", "live"} and len(path_parts) > 1:
            video_id = path_parts[1]
        else:
            video_id = ""
    else:
        video_id = ""

    if not VIDEO_ID_RE.match(video_id):
        raise ValueError("Enter a valid YouTube video URL or 11-character video ID.")
    return video_id


def _field(item: object, name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def fetch_transcript(video_id: str, language: str = "en") -> list[TranscriptSegment]:
    api = YouTubeTranscriptApi()

    try:
        raw_transcript = api.fetch(video_id, languages=[language])
    except AttributeError:
        raw_transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])

    segments: list[TranscriptSegment] = []
    for item in raw_transcript:
        text = str(_field(item, "text", "")).strip()
        if not text:
            continue

        segments.append(
            TranscriptSegment(
                text=text,
                start=float(_field(item, "start", 0.0)),
                duration=float(_field(item, "duration", 0.0)),
            )
        )

    if not segments:
        raise ValueError("No transcript text was found for this video.")
    return segments


def fetch_video_title(video_id: str) -> str:
    import requests

    url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={quote_plus(url)}&format=json"

    try:
        response = requests.get(oembed_url, timeout=8)
        response.raise_for_status()
        title = str(response.json().get("title", "")).strip()
    except Exception:
        title = ""

    return title or video_id
