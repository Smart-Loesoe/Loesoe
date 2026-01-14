import React from "react";
import { createRoot } from "react-dom/client";

const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function App() {
  const [msg, setMsg] = React.useState("");
  const [reply, setReply] = React.useState("");
  const [status, setStatus] = React.useState("⏳ check...");

  React.useEffect(() => {
    fetch(`${apiBase}/health`).then(r => r.json())
      .then(() => setStatus("✅ API online"))
      .catch(() => setStatus("❌ API offline"));
  }, []);

  const send = async () => {
    setReply("…");
    const r = await fetch(`${apiBase}/chat/send`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ session_id: "dev-123", message: msg, file_ids: [] })
    });
    const data = await r.json().catch(() => ({}));
    setReply(JSON.stringify(data, null, 2));
  };

  return (
    <div style={{fontFamily:"system-ui, sans-serif", padding:16, maxWidth:800, margin:"0 auto"}}>
      <h1>Loesoe Dashboard — MVP (Fase 14)</h1>
      <div style={{display:"flex", gap:12, alignItems:"center"}}>
        <span>Status:</span><strong>{status}</strong>
        <span>• API:</span><code>{apiBase}</code>
      </div>

      <div style={{display:"grid", gap:8, marginTop:16}}>
        <input
          placeholder="Typ een bericht voor Loesoe…"
          value={msg}
          onChange={(e)=>setMsg(e.target.value)}
          style={{padding:8, fontSize:16}}
        />
        <button onClick={send} style={{padding:10, fontSize:16, width:160}}>Verstuur</button>
        <pre style={{background:"#111", color:"#0f0", padding:12, borderRadius:8, minHeight:140}}>
{reply || "— antwoord verschijnt hier —"}
        </pre>
      </div>

      <div style={{marginTop:16, fontSize:14, opacity:.75}}>
        Statusbalk: ✅ • Prefs: 🔜 live • Upload: 🔜
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
