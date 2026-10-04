import React from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Database,
  Link2,
  Loader2,
  MessageSquareText,
  PlayCircle,
  Send,
} from "lucide-react";

import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [youtubeUrl, setYoutubeUrl] = React.useState("");
  const [question, setQuestion] = React.useState("");
  const [video, setVideo] = React.useState(null);
  const [storedVideos, setStoredVideos] = React.useState([]);
  const [messages, setMessages] = React.useState([]);
  const [isLoadingVideo, setIsLoadingVideo] = React.useState(false);
  const [isLoadingStored, setIsLoadingStored] = React.useState(true);
  const [isAsking, setIsAsking] = React.useState(false);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    refreshStoredVideos();
  }, []);

  async function request(path, options) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.detail || "Request failed");
    }
    return body;
  }

  async function refreshStoredVideos() {
    setIsLoadingStored(true);
    try {
      const result = await request("/api/videos");
      setStoredVideos(result.videos || []);
    } catch {
      setStoredVideos([]);
    } finally {
      setIsLoadingStored(false);
    }
  }

  function selectStoredVideo(storedVideo) {
    setVideo({
      video_id: storedVideo.video_id,
      title: storedVideo.title,
      chunks: storedVideo.chunks,
      cached: true,
      message: "Stored video selected.",
    });
    setMessages([]);
    setError("");
  }

  async function loadVideo(event) {
    event.preventDefault();
    const value = youtubeUrl.trim();
    if (!value || isLoadingVideo) return;

    setError("");
    setIsLoadingVideo(true);
    setMessages([]);

    try {
      const result = await request("/api/videos/load", {
        method: "POST",
        body: JSON.stringify({ youtube_url: value }),
      });
      setVideo(result);
      await refreshStoredVideos();
    } catch (err) {
      setVideo(null);
      setError(err.message);
    } finally {
      setIsLoadingVideo(false);
    }
  }

  async function askQuestion(event) {
    event.preventDefault();
    const value = question.trim();
    if (!value || !video || isAsking) return;

    const userMessage = { role: "user", text: value };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setError("");
    setIsAsking(true);

    try {
      const result = await request("/api/chat", {
        method: "POST",
        body: JSON.stringify({
          video_id: video.video_id,
          question: value,
          top_k: 4,
        }),
      });

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: result.answer,
          sources: result.sources,
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAsking(false);
    }
  }

  const canAsk = Boolean(video) && !isAsking;

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div className="brand-mark">
            <PlayCircle size={28} aria-hidden="true" />
          </div>
          <div>
            <h1>Video RAG</h1>
            <p>{video ? `Ready: ${video.title || video.video_id}` : "Load a video to begin"}</p>
          </div>
        </header>

        <form className="load-panel" onSubmit={loadVideo}>
          <label htmlFor="youtube-url">YouTube URL</label>
          <div className="input-row">
            <div className="field">
              <Link2 size={18} aria-hidden="true" />
              <input
                id="youtube-url"
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </div>
            <button type="submit" disabled={isLoadingVideo}>
              {isLoadingVideo ? <Loader2 className="spin" size={18} /> : <PlayCircle size={18} />}
              <span>{isLoadingVideo ? "Loading" : "Load"}</span>
            </button>
          </div>
        </form>

        <section className="stored-panel" aria-label="Stored videos">
          <div className="panel-title">
            <Database size={18} aria-hidden="true" />
            <span>Stored videos</span>
          </div>
          {isLoadingStored ? (
            <div className="stored-empty">Checking saved indexes</div>
          ) : storedVideos.length > 0 ? (
            <div className="stored-list">
              {storedVideos.map((storedVideo) => (
                <button
                  className={
                    video?.video_id === storedVideo.video_id
                      ? "stored-video active"
                      : "stored-video"
                  }
                  key={storedVideo.video_id}
                  onClick={() => selectStoredVideo(storedVideo)}
                  type="button"
                >
                  <span>{storedVideo.title || storedVideo.video_id}</span>
                  <small>
                    {storedVideo.video_id} · {storedVideo.chunks} chunks
                  </small>
                </button>
              ))}
            </div>
          ) : (
            <div className="stored-empty">No indexed videos yet</div>
          )}
        </section>

        {video && (
          <div className="status-strip" role="status">
            <CheckCircle2 size={18} aria-hidden="true" />
            <span>{video.cached ? "Loaded from cache" : "Indexed transcript"}</span>
            <strong>{video.chunks} chunks</strong>
          </div>
        )}

        {error && (
          <div className="error-strip" role="alert">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <section className="chat-surface" aria-label="Chat">
          <div className="messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                <MessageSquareText size={34} aria-hidden="true" />
                <h2>Ask about the loaded video</h2>
              </div>
            ) : (
              messages.map((message, index) => (
                <MessageBubble key={`${message.role}-${index}`} message={message} />
              ))
            )}
            {isAsking && (
              <div className="assistant-thinking">
                <Loader2 className="spin" size={18} aria-hidden="true" />
                <span>Thinking</span>
              </div>
            )}
          </div>

          <form className="ask-row" onSubmit={askQuestion}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={video ? "Ask a question about this video" : "Load a video first"}
              disabled={!video}
            />
            <button type="submit" disabled={!canAsk}>
              <Send size={18} aria-hidden="true" />
              <span>Ask</span>
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function MessageBubble({ message }) {
  return (
    <article className={`message ${message.role}`}>
      <p>{message.text}</p>
      {message.sources?.length > 0 && (
        <div className="sources">
          {message.sources.map((source) => (
            <details key={source.chunk_id}>
              <summary>
                <Clock3 size={15} aria-hidden="true" />
                <span>{source.timestamp}</span>
              </summary>
              <p>{source.text}</p>
            </details>
          ))}
        </div>
      )}
    </article>
  );
}

createRoot(document.getElementById("root")).render(<App />);
