import React, { useEffect, useRef, useState } from "react";

type Msg = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  style?: { tone?: string; verbosity?: string };
};

const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";
const SESSION_ID = "12345678";

export default function ChatApp() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", text }]);
    setInput("");
    setSending(true);

    try {
      const r = await fetch(`${API_BASE}/chat/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, message: text, file_ids: [] }),
      });
      if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
      const data = await r.json();

      setMessages((m) => [
        ...m,
        {
          id: data.assistant_message_id || crypto.randomUUID(),
          role: "assistant",
          text: data.text ?? "",
          style: data.style ?? {},
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "system", text: "⚠️ Backend gaf geen OK. Probeer opnieuw." },
      ]);
      console.error(e);
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      send();
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "24px auto", padding: "0 16px", fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 26, fontWeight: 700 }}>Loesoe Chat — Stap 1 (Skeleton)</h1>

      <div style={{ height: 460, border: "1px solid #e5e7eb", borderRadius: 14, padding: 16, overflowY: "auto" }} ref={listRef}>
        {messages.map((m) => (
          <div key={m.id} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", margin: "8px 0" }}>
            <div
              style={{
                maxWidth: "72%",
                background: m.role === "user" ? "#cfe8ec" : m.role === "assistant" ? "#f3f4f6" : "#fff8e1",
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                padding: "8px 12px",
                whiteSpace: "pre-wrap",
              }}
            >
              {m.text}
              {m.role === "assistant" && (m.style?.tone || m.style?.verbosity) && (
                <div style={{ marginTop: 6, fontSize: 11, color: "#6b7280" }}>
                  {m.style?.tone ?? "—"} / {m.style?.verbosity ?? "—"}
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div style={{ display: "flex", justifyContent: "flex-start", marginTop: 6 }}>
            <div style={{ fontSize: 13, color: "#6b7280", background: "#f3f4f6", borderRadius: 10, padding: "6px 10px" }}>
              Loesoe denkt…
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Typ een bericht…"
          style={{ flex: 1, height: 40, borderRadius: 10, border: "1px solid #e5e7eb", padding: "0 12px" }}
        />
        <button onClick={send} disabled={sending || !input.trim()} style={{ height: 40, minWidth: 72, borderRadius: 10, border: "1px solid #e5e7eb" }}>
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
