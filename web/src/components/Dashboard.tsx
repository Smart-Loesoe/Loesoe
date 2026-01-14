import React, { useEffect, useState } from "react";
import { postChatLearning } from "../lib/api"; // zelflerende chat

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type ModuleStatus = {
  key: string;
  status: string;
  note?: string | null;
};

type DashboardPayload = {
  user: {
    id: number;
    name: string;
  };
  slimheidsmeter: number;
  modules: ModuleStatus[];
  last_session: any;
  updated_at: string;
};

type ChatAnalysis = {
  score: number;
  preferences: Record<string, any>;
  patterns: string[];
  emotion?: string | null;
  routine_detected: boolean;
};

type ChatMessage = {
  id: number;
  from: "user" | "loesoe";
  text: string;
};

export default function Dashboard() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tokenPreview, setTokenPreview] = useState<string | null>(null);

  // 🔹 State voor zelflerende chat (Fase 20)
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [lastAnalysis, setLastAnalysis] = useState<ChatAnalysis | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [flashLearning, setFlashLearning] = useState(false);

  const getToken = (): string | null => {
    try {
      const url = new URL(window.location.href);
      const urlToken = url.searchParams.get("token");
      if (urlToken) return urlToken;
    } catch {
      // ignore
    }
    return localStorage.getItem("token");
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);

      let token = getToken();

      // ✅ Als er geen token is: automatisch inloggen als demo-user
      if (!token) {
        try {
          const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              email: "richard@example.com",
              password: "SuperSterk!123",
            }),
          });

          if (!res.ok) {
            const txt = await res.text().catch(() => "");
            setError(
              `Automatisch inloggen mislukt (status ${res.status}).\n\n${txt || ""}`
            );
            setLoading(false);
            return;
          }

          const loginData = await res.json();
          if (!loginData.access_token) {
            setError("Automatische login: geen access_token in response.");
            setLoading(false);
            return;
          }

          token = loginData.access_token;
          localStorage.setItem("token", token);
          // optioneel token in URL zetten
          const url = new URL(window.location.href);
          url.searchParams.set("token", token);
          window.history.replaceState({}, "", url.toString());
        } catch (e: any) {
          setError(
            `Netwerkfout bij automatisch inloggen: ${e?.message ?? String(e)}`
          );
          setLoading(false);
          return;
        }
      }

      if (!token) {
        setError(
          "Niet ingelogd (401). Geen token gevonden én auto-login faalde.\n\n" +
            "Probeer handmatig via /login."
        );
        setLoading(false);
        return;
      }

      setTokenPreview(token.slice(0, 12) + "...");

      // ✅ Nu dashboard-data ophalen
      try {
        const res = await fetch(`${API_BASE}/dashboard`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
          },
        });

        if (res.status === 401) {
          const txt = await res.text().catch(() => "");
          setError(
            "Niet ingelogd (401) bij ophalen dashboard.\n\n" +
              (txt || "Geen extra info.")
          );
          setLoading(false);
          return;
        }

        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          setError(`Fout bij laden dashboard: ${res.status} – ${txt}`);
          setLoading(false);
          return;
        }

        const json = (await res.json()) as DashboardPayload;
        setData(json);
        setError(null);
      } catch (e: any) {
        setError(`Netwerkfout bij dashboard: ${e?.message ?? String(e)}`);
      } finally {
        setLoading(false);
      }
    };

    void init();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.toString());
    window.location.href = "/login";
  };

  // 🧠 Zelflerende chat – via postChatLearning (route /chat)
  const handleSendChat = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || chatLoading) return;

    setChatError(null);
    setChatLoading(true);

    const userMessage: ChatMessage = {
      id: Date.now(),
      from: "user",
      text: trimmed,
    };
    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");

    try {
      const json: any = await postChatLearning(trimmed, {
        source: "dashboard.chat",
        phase: "20B",
      });

      const answerText =
        (typeof json.response === "string" && json.response) ||
        (typeof json.reply === "string" && json.reply) ||
        "(Geen antwoord ontvangen van het model)";

      const loesoeMessage: ChatMessage = {
        id: Date.now() + 1,
        from: "loesoe",
        text: answerText,
      };
      setChatMessages((prev) => [...prev, loesoeMessage]);

      // 🔍 analysis + learning_score mappen naar ChatAnalysis
      if (json.analysis) {
        const a: any = json.analysis || {};
        const score =
          typeof json.learning_score === "number"
            ? Math.max(0, Math.min(10, json.learning_score))
            : typeof a.score === "number"
            ? a.score
            : 0;

        const mapped: ChatAnalysis = {
          score,
          preferences:
            a && typeof a.preferences === "object" ? a.preferences : {},
          patterns: Array.isArray(a.patterns) ? a.patterns : [],
          emotion:
            typeof a.emotion === "string"
              ? a.emotion
              : typeof a.mood === "string"
              ? a.mood
              : null,
          routine_detected: Boolean(a.routine_detected),
        };

        setLastAnalysis(mapped);
        setFlashLearning(true);
        setTimeout(() => setFlashLearning(false), 2000);
      } else {
        setLastAnalysis(null);
      }
    } catch (e: any) {
      setChatError(
        `Netwerkfout bij zelflerende chat: ${e?.message ?? String(e)}`
      );
    } finally {
      setChatLoading(false);
    }
  };

  const handleChatKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSendChat();
    }
  };

  if (loading) {
    return (
      <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
        <h1>Loesoe Dashboard</h1>
        <p>Bezig met laden…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
        <h1>Loesoe Dashboard</h1>
        {tokenPreview && (
          <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>
            Token (begin): <code>{tokenPreview}</code>
          </p>
        )}
        <div
          style={{
            marginTop: "0.75rem",
            padding: "0.75rem 1rem",
            borderRadius: "0.75rem",
            border: "1px solid #b91c1c",
            background: "#fef2f2",
            color: "#7f1d1d",
            maxWidth: "600px",
            whiteSpace: "pre-wrap",
          }}
        >
          {error}
        </div>
        <button
          onClick={handleLogout}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            cursor: "pointer",
          }}
        >
          Opnieuw inloggen
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
        <h1>Loesoe Dashboard</h1>
        <p>Geen data ontvangen.</p>
      </div>
    );
  }

  const statusColor = (status: string) => {
    switch (status) {
      case "ok":
        return "#16a34a";
      case "warn":
        return "#f97316";
      case "off":
      default:
        return "#ef4444";
    }
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
      <h1>Loesoe Dashboard</h1>

      {tokenPreview && (
        <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>
          Actieve token (begin): <code>{tokenPreview}</code>
        </p>
      )}

      <button
        onClick={handleLogout}
        style={{
          padding: "0.5rem 1rem",
          marginBottom: "1rem",
          cursor: "pointer",
        }}
      >
        Uitloggen
      </button>

      {/* Hoofd-info / Slimheidsmeter */}
      <section
        style={{
          marginTop: "1rem",
          padding: "1rem 1.25rem",
          borderRadius: "0.75rem",
          border: "1px solid #e5e7eb",
          background: "#f9fafb",
          maxWidth: "480px",
        }}
      >
        <h2 style={{ margin: 0, marginBottom: "0.35rem", fontSize: "1.05rem" }}>
          Welkom terug, <strong>{data.user.name}</strong> 👋
        </h2>
        <p style={{ margin: 0, fontSize: "0.9rem", color: "#374151" }}>
          Slimheidsmeter:{" "}
          <strong>{data.slimheidsmeter.toFixed(1)}%</strong>
        </p>
        <p
          style={{
            marginTop: "0.25rem",
            fontSize: "0.8rem",
            color: "#6b7280",
          }}
        >
          Laatste update: {new Date(data.updated_at).toLocaleString()}
        </p>
      </section>

      {/* Modules overzicht */}
      <section style={{ marginTop: "1.5rem", maxWidth: "600px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Modules</h2>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            marginTop: "0.5rem",
          }}
        >
          <thead>
            <tr>
              <th
                style={{
                  textAlign: "left",
                  borderBottom: "1px solid #e5e7eb",
                  padding: "0.5rem",
                  fontSize: "0.85rem",
                  color: "#6b7280",
                }}
              >
                Module
              </th>
              <th
                style={{
                  textAlign: "left",
                  borderBottom: "1px solid #e5e7eb",
                  padding: "0.5rem",
                  fontSize: "0.85rem",
                  color: "#6b7280",
                }}
              >
                Status
              </th>
              <th
                style={{
                  textAlign: "left",
                  borderBottom: "1px solid #e5e7eb",
                  padding: "0.5rem",
                  fontSize: "0.85rem",
                  color: "#6b7280",
                }}
              >
                Opmerking
              </th>
            </tr>
          </thead>
          <tbody>
            {data.modules.map((m) => (
              <tr key={m.key}>
                <td
                  style={{
                    padding: "0.4rem 0.5rem",
                    borderBottom: "1px solid #f3f4f6",
                    fontSize: "0.9rem",
                  }}
                >
                  {m.key}
                </td>
                <td
                  style={{
                    padding: "0.4rem 0.5rem",
                    borderBottom: "1px solid #f3f4f6",
                  }}
                >
                  <span
                    style={{
                      display: "inline-block",
                      padding: "0.1rem 0.6rem",
                      borderRadius: "999px",
                      fontSize: "0.75rem",
                      color: "#ffffff",
                      backgroundColor: statusColor(m.status),
                    }}
                  >
                    {m.status}
                  </span>
                </td>
                <td
                  style={{
                    padding: "0.4rem 0.5rem",
                    borderBottom: "1px solid #f3f4f6",
                    fontSize: "0.85rem",
                    color: "#4b5563",
                  }}
                >
                  {m.note ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 🔥 Zelflerende chat (Fase 20) */}
      <section
        style={{
          marginTop: "1.5rem",
          maxWidth: "600px",
          borderRadius: "0.75rem",
          border: "1px solid #e5e7eb",
          background: "#f3f4f6",
          padding: "1rem 1.25rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem",
            marginBottom: "0.5rem",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "1.0rem" }}>
              Chat · Zelflerend (Fase 20)
            </h2>
            <p
              style={{
                margin: 0,
                marginTop: "0.15rem",
                fontSize: "0.8rem",
                color: "#4b5563",
              }}
            >
              Elke boodschap wordt geanalyseerd. Loesoe leert mee op de
              achtergrond.
            </p>
          </div>
          {flashLearning && (
            <div
              style={{
                fontSize: "0.7rem",
                padding: "0.15rem 0.6rem",
                borderRadius: "999px",
                background: "#10b9811a",
                border: "1px solid #10b981",
                color: "#065f46",
                whiteSpace: "nowrap",
              }}
            >
              🧠 Loesoe heeft hiervan geleerd
            </div>
          )}
        </div>

        {/* Chat-venster */}
        <div
          style={{
            minHeight: "160px",
            maxHeight: "260px",
            overflowY: "auto",
            borderRadius: "0.75rem",
            border: "1px solid #d1d5db",
            background: "#111827",
            padding: "0.5rem 0.75rem",
            color: "#e5e7eb",
            fontSize: "0.85rem",
          }}
        >
          {chatMessages.length === 0 && (
            <p
              style={{
                margin: 0,
                fontSize: "0.75rem",
                color: "#9ca3af",
                fontStyle: "italic",
              }}
            >
              Typ een bericht hieronder, bijvoorbeeld:{" "}
              <code>"ik werk woensdag 4 uur aan loesoe"</code>.
            </p>
          )}

          {chatMessages.map((m) => (
            <div
              key={m.id}
              style={{
                display: "flex",
                justifyContent: m.from === "user" ? "flex-end" : "flex-start",
                marginTop: "0.25rem",
              }}
            >
              <div
                style={{
                  maxWidth: "80%",
                  padding: "0.4rem 0.6rem",
                  borderRadius: "0.75rem",
                  background: m.from === "user" ? "#4f46e5" : "#1f2937",
                  color: "#f9fafb",
                  fontSize: "0.8rem",
                }}
              >
                <div
                  style={{
                    fontSize: "0.65rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    opacity: 0.7,
                    marginBottom: "0.1rem",
                  }}
                >
                  {m.from === "user" ? "Jij" : "Loesoe"}
                </div>
                <div>{m.text}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Input + knop */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginTop: "0.5rem",
          }}
        >
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleChatKeyDown}
            placeholder="Typ hier je bericht…"
            style={{
              flex: 1,
              padding: "0.4rem 0.6rem",
              borderRadius: "0.5rem",
              border: "1px solid #d1d5db",
              fontSize: "0.85rem",
            }}
          />
          <button
            onClick={handleSendChat}
            disabled={chatLoading || !chatInput.trim()}
            style={{
              padding: "0.4rem 0.9rem",
              borderRadius: "0.5rem",
              border: "none",
              cursor: chatLoading || !chatInput.trim() ? "default" : "pointer",
              backgroundColor: "#4f46e5",
              color: "#f9fafb",
              fontSize: "0.85rem",
              opacity: chatLoading || !chatInput.trim() ? 0.6 : 1,
            }}
          >
            {chatLoading ? "Bezig..." : "Stuur"}
          </button>
        </div>

        {chatError && (
          <div
            style={{
              marginTop: "0.4rem",
              padding: "0.4rem 0.6rem",
              borderRadius: "0.5rem",
              border: "1px solid #b91c1c",
              background: "#fef2f2",
              color: "#7f1d1d",
              fontSize: "0.75rem",
              whiteSpace: "pre-wrap",
            }}
          >
            {chatError}
          </div>
        )}

        {/* Laatste analyse */}
        {lastAnalysis && (
          <div
            style={{
              marginTop: "0.6rem",
              padding: "0.6rem 0.75rem",
              borderRadius: "0.6rem",
              border: "1px solid #d1d5db",
              background: "#f9fafb",
              fontSize: "0.75rem",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.25rem",
              }}
            >
              <span style={{ fontWeight: 600 }}>Laatste analyse</span>
              <span
                style={{
                  padding: "0.15rem 0.5rem",
                  borderRadius: "999px",
                  fontSize: "0.7rem",
                  background: "#10b9811a",
                  border: "1px solid #10b981",
                  color: "#065f46",
                }}
              >
                score: {lastAnalysis.score.toFixed(1)} / 10
              </span>
            </div>

            <div style={{ marginTop: "0.15rem" }}>
              <span style={{ fontWeight: 600 }}>Voorkeuren: </span>
              {Object.keys(lastAnalysis.preferences).length === 0 ? (
                <span style={{ color: "#6b7280" }}>-</span>
              ) : (
                <code
                  style={{
                    fontSize: "0.7rem",
                    background: "#111827",
                    color: "#e5e7eb",
                    padding: "0.1rem 0.35rem",
                    borderRadius: "0.35rem",
                  }}
                >
                  {JSON.stringify(lastAnalysis.preferences)}
                </code>
              )}
            </div>

            <div style={{ marginTop: "0.15rem" }}>
              <span style={{ fontWeight: 600 }}>Patronen: </span>
              {lastAnalysis.patterns.length === 0 ? (
                <span style={{ color: "#6b7280" }}>-</span>
              ) : (
                <span>{lastAnalysis.patterns.join(", ")}</span>
              )}
            </div>

            <div style={{ marginTop: "0.15rem" }}>
              <span style={{ fontWeight: 600 }}>Emotie: </span>
              {lastAnalysis.emotion ?? (
                <span style={{ color: "#6b7280" }}>-</span>
              )}
            </div>

            <div style={{ marginTop: "0.15rem" }}>
              <span style={{ fontWeight: 600 }}>Routine gedetecteerd: </span>
              {lastAnalysis.routine_detected ? "ja" : "nee"}
            </div>
          </div>
        )}
      </section>

      {/* Last session raw JSON */}
      <section style={{ marginTop: "1.5rem", maxWidth: "600px" }}>
        <h2 style={{ fontSize: "1.05rem" }}>Last session (raw)</h2>
        <pre
          style={{
            background: "#111827",
            color: "#e5e7eb",
            padding: "0.75rem 1rem",
            borderRadius: "0.75rem",
            fontSize: "0.8rem",
            overflowX: "auto",
          }}
        >
          {JSON.stringify(data.last_session, null, 2)}
        </pre>
      </section>
    </div>
  );
}
