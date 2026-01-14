import { useEffect, useState } from "react";

export default function TokenSet() {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  // Optie 1: automatisch oppakken via query ?t=...
  useEffect(() => {
    const qp = new URLSearchParams(window.location.search);
    const t = qp.get("t");
    if (t) {
      localStorage.setItem("access_token", t);
      setStatus("Token opgeslagen via URL. Je kunt nu naar /dashboard.");
    }
  }, []);

  // Optie 2: handmatig plakken in tekstvak
  const save = () => {
    if (!token.trim()) {
      setStatus("Geen token ingevuld.");
      return;
    }
    localStorage.setItem("access_token", token.trim());
    setStatus("Token opgeslagen. Ga naar /dashboard.");
  };

  const clear = () => {
    localStorage.removeItem("access_token");
    setStatus("Token verwijderd.");
  };

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", padding: 16 }}>
      <h1>Loesoe – Set Token</h1>
      <p>
        Plak hieronder je <code>access_token</code> van <b>/auth/login</b> (Swagger) of gebruik de URL-vorm{" "}
        <code>/set-token?t=JOUW_TOKEN</code>.
      </p>
      <textarea
        placeholder="Plak hier je JWT access_token"
        style={{ width: "100%", height: 140 }}
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button onClick={save}>Opslaan</button>
        <button onClick={clear}>Token verwijderen</button>
      </div>
      {status && <p style={{ marginTop: 12 }}><b>{status}</b></p>}
      <p style={{ marginTop: 12 }}>
        Klaar? Ga naar <a href="/dashboard">/dashboard</a>.
      </p>
    </div>
  );
}
