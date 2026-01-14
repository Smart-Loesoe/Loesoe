// web/src/lib/api.ts

// ================== Types ==================

export interface ChatAnalysis {
  score: number;
  preferences: Record<string, any>;
  patterns: string[];
  emotion?: string | null;
  routine_detected: boolean;
}

// Generieke shape voor zelflerende chat
export interface ChatLearningResponse {
  response?: string;
  reply?: string; // fallback
  analysis?: any;
  learning_score?: number;
  [key: string]: any;
}

// --- Auth & Dashboard types ---

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface DashboardModule {
  key: string;
  status: "ok" | "warn" | "off";
  note: string;
}

export interface DashboardUser {
  id: number;
  name: string;
}

export interface DashboardSelfLearning {
  has_data: boolean;
  avg_score: number;
  user_score: number;
  last_mood: string | null;
  preferences_count: number;
  patterns: any;
}

export interface DashboardLastSession {
  version: number;
  users: Record<string, any>;
}

export interface DashboardResponse {
  user: DashboardUser;
  slimheidsmeter: number;
  modules: DashboardModule[];
  last_session: DashboardLastSession;
  updated_at: string;
  self_learning: DashboardSelfLearning;
}

export interface ChatResponse {
  reply: string;
}

// ================== API base ==================

const API_BASE: string =
  (import.meta as any)?.env?.VITE_API_BASE_URL?.replace(/\/+$/, "") ??
  (import.meta as any)?.env?.VITE_API_BASE?.replace(/\/+$/, "") ??
  "http://localhost:8000";

// ================== JWT helpers ==================

const TOKEN_KEY = "loesoe_token";

// Token zetten
export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // negeren
  }
}

// Token ophalen (URL > localStorage)
export function getToken(): string | null {
  try {
    const url = new URL(window.location.href);
    const urlToken = url.searchParams.get("token");
    if (urlToken) {
      // als er een token in de URL staat, gelijk opslaan voor volgende pagina's
      try {
        localStorage.setItem(TOKEN_KEY, urlToken);
      } catch {
        // negeren
      }
      return urlToken;
    }
  } catch {
    // negeren
  }

  // volgorde: nieuwe key → oude keys
  return (
    localStorage.getItem(TOKEN_KEY) ??
    localStorage.getItem("access_token") ??
    localStorage.getItem("token") ??
    null
  );
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem("access_token");
    localStorage.removeItem("token");
  } catch {
    // negeren
  }
}

// ================== Generic request helper ==================

async function request<T>(
  path: string,
  options: RequestInit = {},
  useAuth: boolean = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (useAuth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // token ongeldig of verlopen
    clearToken();
    throw new Error("unauthorized");
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `HTTP ${res.status}: ${text || res.statusText || "Onbekende fout"}`
    );
  }

  if (res.status === 204) {
    // no content
    return {} as T;
  }

  return (await res.json()) as T;
}

// ================== Auth ==================

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `Login failed: ${text || res.statusText || "Onbekende fout bij inloggen"}`
    );
  }

  const data = (await res.json()) as LoginResponse;
  setToken(data.access_token);
  return data;
}

// ================== Dashboard ==================

export function fetchDashboard(): Promise<DashboardResponse> {
  return request<DashboardResponse>("/dashboard", { method: "GET" }, true);
}

// ================== Chat (basis + zelflerend) ==================

/**
 * Basis-chat (wordt nog gebruikt door oudere componenten zoals ChatWithLearning)
 * Route: POST /chat
 */
export async function postChat(
  message: string,
  meta?: Record<string, any>
): Promise<ChatLearningResponse> {
  return postChatLearning(message, meta);
}

/**
 * Zelflerende chat (Fase 20B/20C/20D)
 * Route: POST /chat  (backend doet analyse + learning)
 */
export async function postChatLearning(
  message: string,
  meta?: Record<string, any>
): Promise<ChatLearningResponse> {
  return request<ChatLearningResponse>(
    "/chat",
    {
      method: "POST",
      body: JSON.stringify({
        message,
        meta: meta ?? {},
      }),
    },
    true
  );
}

/**
 * Eenvoudige helper voor components die alleen `reply` nodig hebben.
 * Gebruikt dezelfde /chat endpoint, maar mapped terug naar ChatResponse.
 */
export async function sendChat(
  message: string,
  meta?: Record<string, any>
): Promise<ChatResponse> {
  const data = await postChatLearning(message, meta);
  const reply = data.response ?? data.reply ?? "";
  return { reply };
}
