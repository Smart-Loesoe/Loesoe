import { useEffect, useMemo, useState } from "react";

type Pattern = {
  id: number;
  subject: string;
  pattern_type: string;
  key: string;
  value: any;
  confidence: number; // 0..1 (verwacht). We normaliseren ook 0..100 voor zekerheid.
  evidence: any;
  last_seen: string | null;
  created_at: string | null;
  updated_at: string | null;
};

type PatternsResponse = {
  ok: boolean;
  filters?: any;
  total?: number;
  items?: Pattern[];
};

function tryParseJson<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function getTokenFromStorage(): string | null {
  // 1) meest gebruikelijke keys
  const keys = ["token", "access_token", "loesoe_token", "auth_token", "jwt"];
  for (const k of keys) {
    const v = localStorage.getItem(k);
    if (v && v.length > 10) return v;
  }

  // 2) soms zit het in een auth object
  const authObj = tryParseJson<any>(localStorage.getItem("auth"));
  if (authObj?.token && typeof authObj.token === "string") return authObj.token;
  if (authObj?.access_token && typeof authObj.access_token === "string")
    return authObj.access_token;

  // 3) soms in session object
  const sessionObj = tryParseJson<any>(localStorage.getItem("session"));
  if (sessionObj?.token && typeof sessionObj.token === "string")
    return sessionObj.token;

  return null;
}

function toPct(conf: number): number {
  // accepteert 0..1 of 0..100
  if (Number.isNaN(conf) || conf === null || conf === undefined) return 0;
  if (conf <= 1) return Math.round(conf * 100);
  return Math.round(conf);
}

function fmtLocal(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso; // fallback: raw tonen
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export default function LearningPatternsCard() {
  const [items, setItems] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  // UI/UX polish
  const [patternType, setPatternType] = useState<string>("ALL");
  const [minConfidence, setMinConfidence] = useState<number>(60); // 0..100
  const [limit, setLimit] = useState<number>(50); // client-side limiet (we fetchen meer)

  const apiBase = useMemo(() => {
    // @ts-ignore
    const envBase = (import.meta?.env?.VITE_API_BASE as string | undefined) || "";
    return (envBase || "http://localhost:8000").replace(/\/$/, "");
  }, []);

  async function load() {
    setLoading(true);
    setError(null);

    const token = getTokenFromStorage();
    if (!token) {
      setLoading(false);
      setError("Geen token gevonden. Log opnieuw in (token ontbreekt in localStorage).");
      return;
    }

    // Fetch iets ruimer zodat filters/sorteren client-side kunnen werken.
    const url = `${apiBase}/learning/patterns?limit=200&order=confidence&direction=desc`;

    try {
      const res = await fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        if (res.status === 401 || res.status === 403) {
          throw new Error(
            `Auth fout (${res.status}). Log opnieuw in.${body ? ` (${body})` : ""}`
          );
        }
        throw new Error(`HTTP ${res.status}${body ? ` — ${body}` : ""}`);
      }

      const data = (await res.json()) as PatternsResponse;
      const nextItems = data.items || [];
      setItems(nextItems);
      setTotal(typeof data.total === "number" ? data.total : nextItems.length);
      setLoading(false);
    } catch (e: any) {
      setError(String(e?.message || e));
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  const patternTypes = useMemo(() => {
    const set = new Set<string>();
    for (const p of items) {
      if (p?.pattern_type) set.add(p.pattern_type);
    }
    return ["ALL", ...Array.from(set).sort((a, b) => a.localeCompare(b))];
  }, [items]);

  const filtered = useMemo(() => {
    const minPct = minConfidence;

    return items
      .filter((p) => {
        const pct = toPct(p.confidence || 0);
        const typeOk = patternType === "ALL" || p.pattern_type === patternType;
        const confOk = pct >= minPct;
        return typeOk && confOk;
      })
      .sort((a, b) => {
        // Recent eerst: last_seen -> updated_at -> created_at
        const ta = new Date(a.last_seen || a.updated_at || a.created_at || 0).getTime();
        const tb = new Date(b.last_seen || b.updated_at || b.created_at || 0).getTime();
        return tb - ta;
      });
  }, [items, patternType, minConfidence]);

  const shown = useMemo(() => filtered.slice(0, Math.max(1, limit)), [filtered, limit]);

  if (loading) {
    return (
      <div className="rounded-xl border p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-lg font-semibold">🧠 Wat Loesoe heeft geleerd</div>
          <button className="px-3 py-1.5 rounded-lg border text-sm opacity-60" disabled>
            Laden…
          </button>
        </div>
        <div className="text-sm opacity-70 mt-2">Patterns ophalen…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="text-lg font-semibold">🧠 Wat Loesoe heeft geleerd</div>
          <button
            onClick={load}
            className="px-3 py-1.5 rounded-lg border text-sm hover:bg-black/5"
          >
            Ververs
          </button>
        </div>
        <div className="text-sm mt-2 text-red-600">Error: {error}</div>
        <div className="text-xs opacity-70 mt-2">
          Tip: als dit 401/403 is → opnieuw inloggen zodat token opnieuw gezet wordt.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-semibold">🧠 Wat Loesoe heeft geleerd</div>
          <div className="text-sm opacity-70 mt-1">
            Read-only • transparant • geen gedrag-wijziging
            {typeof total === "number" ? ` • totaal (DB): ${total}` : ""}
          </div>
          <div className="text-xs opacity-70 mt-1">
            Resultaten: {shown.length} / {filtered.length} (na filters)
          </div>
        </div>

        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg border text-sm hover:bg-black/5"
        >
          Ververs
        </button>
      </div>

      {/* UI/UX polish controls */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <label className="text-sm">
          <div className="opacity-70 mb-1">Pattern type</div>
          <select
            value={patternType}
            onChange={(e) => setPatternType(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-white"
          >
            {patternTypes.map((t) => (
              <option key={t} value={t}>
                {t === "ALL" ? "Alle types" : t}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <div className="opacity-70 mb-1">Min. confidence: {minConfidence}%</div>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="w-full"
          />
        </label>

        <label className="text-sm">
          <div className="opacity-70 mb-1">Max tonen: {limit}</div>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-full rounded-lg border px-3 py-2 text-sm bg-white"
          >
            {[10, 25, 50, 100, 200].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {shown.length === 0 ? (
        <div className="text-sm mt-4 opacity-70">
          Nog geen patterns (of alles is weggefilterd).
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {shown.map((p) => {
            const pct = toPct(p.confidence || 0);
            const keyLabel = p.key ? ` · ${p.key}` : "";
            const lastSeen = p.last_seen || p.updated_at || p.created_at;

            return (
              <div key={p.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">
                    {p.pattern_type}
                    <span className="opacity-80">{keyLabel}</span>
                  </div>
                  <div className="text-sm opacity-70">{pct}%</div>
                </div>

                <div className="mt-2 h-2 w-full rounded bg-black/10">
                  <div
                    className="h-2 rounded bg-black/40"
                    style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                  />
                </div>

                <div className="mt-2 text-sm">
                  <div className="opacity-70">Value</div>
                  <pre className="mt-1 text-xs rounded bg-black/5 p-2 overflow-auto">
                    {JSON.stringify(p.value, null, 2)}
                  </pre>
                </div>

                <div className="mt-2 text-xs opacity-70">
                  Evidence: {JSON.stringify(p.evidence)}
                </div>

                <div className="mt-1 text-xs opacity-70">
                  Last seen (local): {fmtLocal(lastSeen)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
