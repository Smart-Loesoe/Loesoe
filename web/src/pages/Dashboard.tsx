import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchDashboard,
  DashboardResponse,
  ChatAnalysis,
  postChatLearning,
  getToken,
  clearToken,
} from "../lib/api";

import LearningPatternsCard from "../components/LearningPatternsCard";


// NOTE (23.3-polish): centraliseer API base voor SSE endpoints.
// fetchDashboard()/postChatLearning blijven via ../lib/api lopen (leidend),
// maar EventSource gebruikte hardcoded localhost. Dat maken we consistent met VITE_API_BASE.
function getApiBase(): string {
  // @ts-ignore
  const envBase = (import.meta?.env?.VITE_API_BASE as string | undefined) || "";
  const base = (envBase || "http://localhost:8000").replace(/\/$/, "");
  return base;
}

type ChatMessage = {
  id: number;
  from: "user" | "loesoe";
  text: string;
};

function getLevelLabel(value: number): string {
  if (value >= 90) return "ULTRA";
  if (value >= 70) return "PRO";
  if (value >= 40) return "GROWING";
  return "BEGINNER";
}

export default function Dashboard() {
  const navigate = useNavigate();

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenPreview, setTokenPreview] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState<boolean>(false);

  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [lastAnalysis, setLastAnalysis] = useState<ChatAnalysis | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [flashLearning, setFlashLearning] = useState(false);

  const [isStreaming, setIsStreaming] = useState(false);
  const streamRef = useRef<EventSource | null>(null);
  const lastMessageIdRef = useRef<number | null>(null);

  const [streamAlive, setStreamAlive] = useState(false);
  const [lastStreamUpdate, setLastStreamUpdate] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      setLoading(true);

      try {
        const result = await fetchDashboard();
        if (cancelled) return;

        setData(result);
        const t = getToken();
        if (t) {
        setTokenPreview(t.slice(0, 12) + "...");
        setHasToken(true);
      } else {
        setHasToken(false);
      }
      } catch (err) {
        if (!cancelled) {
          setError("Dashboard kan niet laden.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void init();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  useEffect(() => {
    let cancelled = false;
    const es = new EventSource(`${getApiBase()}/stream/events`);

    es.onopen = () => {
      if (!cancelled) setStreamAlive(true);
    };

    es.onmessage = async (event) => {
      try {
        const payload = JSON.parse(event.data ?? "{}");
        if (payload?.ts) {
          setLastStreamUpdate(payload.ts);
        }
      } catch {}

      try {
        const result = await fetchDashboard();
        if (!cancelled) setData(result);
      } catch {}
    };

    es.onerror = () => {
      if (!cancelled) setStreamAlive(false);
      es.close();
    };

    return () => {
      cancelled = true;
      es.close();
    };
  }, []);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.close();
        streamRef.current = null;
      }
    };
  }, []);

  const handleLogout = () => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    clearToken();
    setHasToken(false);
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.toString());
    navigate("/login");
  };

  const handleSendChat = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || chatLoading || isStreaming) return;

    setChatError(null);
    setChatLoading(true);

    const token = getToken();
    if (!token) {
      setChatError("Geen token. Log opnieuw in.");
      setChatLoading(false);
      return;
    }

    const now = Date.now();

    const userMsg: ChatMessage = {
      id: now,
      from: "user",
      text: trimmed,
    };

    const assistantMsg: ChatMessage = {
      id: now + 1,
      from: "loesoe",
      text: "",
    };

    lastMessageIdRef.current = assistantMsg.id;

    setChatMessages((prev) => [...prev, userMsg, assistantMsg]);
    setChatInput("");
    setIsStreaming(true);

    const es = new EventSource(
      `${getApiBase()}/stream/chat?q=${encodeURIComponent(trimmed)}`
    );
    streamRef.current = es;

    es.onmessage = (event) => {
      if (!event.data) return;

      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "chat_chunk" && payload.content) {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.id === lastMessageIdRef.current
                ? { ...m, text: m.text + payload.content }
                : m
            )
          );
        }
        if (payload.type === "chat_done") {
          setIsStreaming(false);
          es.close();
          streamRef.current = null;
        }
      } catch {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.id === lastMessageIdRef.current
              ? { ...m, text: m.text + event.data }
              : m
          )
        );
      }
    };

    es.onerror = () => {
      setIsStreaming(false);
      setChatError("Streamfout.");
      es.close();
      streamRef.current = null;
    };

    try {
      const json = await postChatLearning(trimmed, { origin: "dashboard" });

      if (json.analysis) {
        setLastAnalysis(json.analysis);
        setFlashLearning(true);
        setTimeout(() => setFlashLearning(false), 2000);
      }
    } catch (e) {
      setChatError("Learning endpoint fout.");
    } finally {
      setChatLoading(false);
    }
  };

  const handleStopStreaming = () => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    setIsStreaming(false);
  };

  const handleChatKeyDown = (e: any) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSendChat();
    }
  };

  if (loading) {
    return <div style={{ padding: "2rem" }}>Dashboard laden...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: "2rem" }}>
        <p>{error}</p>
        <button onClick={handleLogout}>Uitloggen</button>
      </div>
    );
  }

  if (!data) {
    return <div style={{ padding: "2rem" }}>Geen data.</div>;
  }

  const slimheid = data.slimheidsmeter ?? 0;
  const levelLabel = getLevelLabel(slimheid);
  const selfLearning = data.self_learning;
  const lastMood =
    selfLearning?.last_mood?.trim()?.length > 0 ? selfLearning.last_mood : "onbekend";
  const prefsCount = selfLearning?.preferences_count ?? 0;

  const barWidth = Math.max(0, Math.min(100, slimheid));

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
      <h1>Loesoe Dashboard</h1>

      {!hasToken && (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem",
            borderRadius: "0.75rem",
            border: "1px solid #fbbf24",
            background: "#fffbeb",
            maxWidth: "600px",
          }}
        >
          <div style={{ fontWeight: 600 }}>🔐 Niet ingelogd</div>
          <div style={{ fontSize: "0.85rem", marginTop: "0.35rem", color: "#78350f" }}>
            Je dashboard-endpoints vereisen een <b>Bearer token</b>. Log opnieuw in zodat alle cards live data kunnen tonen.
          </div>
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
            <button
              onClick={() => navigate("/login")}
              style={{
                padding: "0.45rem 0.9rem",
                borderRadius: "0.5rem",
                border: "1px solid #d4d4d4",
                background: "#fff",
                cursor: "pointer",
              }}
            >
              Naar login
            </button>

            <button
              onClick={() => {
                clearToken();
                setTokenPreview(null);
                setHasToken(false);
              }}
              style={{
                padding: "0.45rem 0.9rem",
                borderRadius: "0.5rem",
                border: "1px solid #d4d4d4",
                background: "#fff",
                cursor: "pointer",
              }}
            >
              Token opruimen
            </button>
          </div>
        </div>
      )}


      {tokenPreview && (
        <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>
          Actieve token: <code>{tokenPreview}</code>
        </p>
      )}

      <p style={{ fontSize: "0.75rem" }}>
        Streaming:{" "}
        <strong style={{ color: streamAlive ? "#16a34a" : "#ef4444" }}>
          {streamAlive ? "actief" : "geen verbinding"}
        </strong>
        {lastStreamUpdate && <> (laatste: {new Date(lastStreamUpdate).toLocaleTimeString()})</>}
      </p>

      <button
        onClick={handleLogout}
        style={{ padding: "0.5rem 1rem", marginBottom: "1rem" }}
      >
        Uitloggen
      </button>

      {/* Slimheidsmeter */}
      <section
        style={{
          border: "1px solid #111",
          background: "#0a0a0a",
          padding: "1rem",
          borderRadius: "0.75rem",
          color: "#eee",
          maxWidth: "500px",
        }}
      >
        <p style={{ margin: 0, fontSize: "0.75rem", opacity: 0.7 }}>
          Welkom terug
        </p>
        <h2 style={{ marginTop: "0.2rem" }}>{data.user.name} 👋</h2>

        <div style={{ display: "flex", alignItems: "baseline", gap: "0.4rem" }}>
          <span style={{ fontSize: "2rem", fontWeight: 700 }}>
            {slimheid.toFixed(1)}%
          </span>
          <span
            style={{
              fontSize: "0.75rem",
              padding: "0.15rem 0.5rem",
              borderRadius: "999px",
              border: "1px solid #333",
              background: "#222",
            }}
          >
            Level {levelLabel}
          </span>
        </div>

        <div
          style={{
            marginTop: "0.5rem",
            height: "6px",
            width: "100%",
            background: "#222",
            borderRadius: "999px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${barWidth}%`,
              height: "100%",
              background: "#22c55e",
            }}
          />
        </div>

        <p style={{ fontSize: "0.8rem", marginTop: "0.5rem", opacity: 0.7 }}>
          Laatste mood: {lastMood} · Voorkeuren: {prefsCount}
        </p>
      </section>

      {/* Modules */}
      <section style={{ marginTop: "1.5rem", maxWidth: "600px" }}>
        <h2>Modules</h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {data.modules.map((m) => (
              <tr key={m.key}>
                <td style={{ padding: "0.4rem" }}>{m.key}</td>
                <td style={{ padding: "0.4rem" }}>
                  <span
                    style={{
                      padding: "0.15rem 0.5rem",
                      borderRadius: "999px",
                      color: "#fff",
                      background:
                        m.status === "ok"
                          ? "#16a34a"
                          : m.status === "warn"
                          ? "#f97316"
                          : "#ef4444",
                    }}
                  >
                    {m.status}
                  </span>
                </td>
                <td style={{ padding: "0.4rem" }}>{m.note ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Learning patterns (Fase 23.3) */}
      <section style={{ marginTop: "1.5rem", maxWidth: "600px" }}>
        <LearningPatternsCard />
      </section>

      {/* CHAT + STREAMING */}
      <section
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          maxWidth: "600px",
          border: "1px solid #ccc",
          borderRadius: "0.75rem",
          background: "#f5f5f5",
        }}
      >
        <div style={{ marginBottom: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Chat · Zelflerend + Streaming (Fase 21)</h2>
          <p style={{ fontSize: "0.8rem", color: "#444", margin: 0 }}>
            Loesoe streamt realtime én leert van elke boodschap.
          </p>
        </div>

        {flashLearning && (
          <div
            style={{
              fontSize: "0.7rem",
              padding: "0.2rem 0.6rem",
              borderRadius: "999px",
              background: "#10b9811a",
              border: "1px solid #10b981",
              color: "#065f46",
              marginBottom: "0.5rem",
              display: "inline-block",
            }}
          >
            🧠 Loesoe heeft hiervan geleerd
          </div>
        )}

        <div
          style={{
            minHeight: "150px",
            maxHeight: "260px",
            overflowY: "auto",
            background: "#111",
            color: "#eee",
            padding: "0.75rem",
            borderRadius: "0.75rem",
          }}
        >
          {chatMessages.length === 0 ? (
            <p style={{ opacity: 0.6, fontSize: "0.8rem" }}>
              Typ een bericht hieronder.
            </p>
          ) : (
            chatMessages.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  justifyContent: m.from === "user" ? "flex-end" : "flex-start",
                  marginTop: "0.3rem",
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "0.5rem 0.7rem",
                    background: m.from === "user" ? "#4f46e5" : "#222",
                    borderRadius: "0.7rem",
                    fontSize: "0.8rem",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.65rem",
                      opacity: 0.7,
                      textTransform: "uppercase",
                    }}
                  >
                    {m.from === "user" ? "Jij" : "Loesoe"}
                  </div>
                  {m.text}
                </div>
              </div>
            ))
          )}
        </div>

        <div
          style={{
            display: "flex",
            gap: "0.5rem",
            marginTop: "0.6rem",
          }}
        >
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleChatKeyDown}
            placeholder="Typ hier je bericht…"
            disabled={isStreaming}
            style={{
              flex: 1,
              padding: "0.5rem",
              border: "1px solid #ccc",
              borderRadius: "0.5rem",
            }}
          />

          {isStreaming ? (
            <button
              onClick={handleStopStreaming}
              style={{
                background: "#b91c1c",
                color: "#fff",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "0.5rem",
              }}
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleSendChat}
              disabled={chatLoading || !chatInput.trim()}
              style={{
                background: "#4f46e5",
                color: "#fff",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "0.5rem",
                opacity: chatLoading || !chatInput.trim() ? 0.6 : 1,
              }}
            >
              {chatLoading ? "Bezig..." : "Stuur"}
            </button>
          )}
        </div>

        {chatError && (
          <div
            style={{
              marginTop: "0.5rem",
              background: "#fee",
              padding: "0.5rem",
              borderRadius: "0.5rem",
              color: "#900",
            }}
          >
            {chatError}
          </div>
        )}

        {lastAnalysis && (
          <div
            style={{
              marginTop: "1rem",
              background: "#fff",
              padding: "0.75rem",
              borderRadius: "0.75rem",
              border: "1px solid #ddd",
              fontSize: "0.8rem",
            }}
          >
            <strong>Laatste analyse</strong>
            <p style={{ marginTop: "0.3rem" }}>
              Score: {lastAnalysis.score.toFixed(1)} / 10
            </p>
            <p>Voorkeuren: {JSON.stringify(lastAnalysis.preferences)}</p>
            <p>Patronen: {lastAnalysis.patterns.join(", ") || "-"}</p>
            <p>Emotie: {lastAnalysis.emotion ?? "-"}</p>
            <p>
              Routine gedetecteerd: {lastAnalysis.routine_detected ? "ja" : "nee"}
            </p>
          </div>
        )}
      </section>

      {/* Raw JSON */}
      <section style={{ marginTop: "1.5rem" }}>
        <h2>Last session (raw)</h2>
        <pre
          style={{
            background: "#111",
            color: "#eee",
            padding: "1rem",
            borderRadius: "0.75rem",
            maxWidth: "600px",
            overflowX: "auto",
            fontSize: "0.8rem",
          }}
        >
          {JSON.stringify(data.last_session, null, 2)}
        </pre>
      </section>
    </div>
  );
}
