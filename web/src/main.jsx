// web/src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";

import LoginPage from "./pages/Login";
import DashboardPage from "./pages/Dashboard";
import { getToken, setToken } from "./lib/api";

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

// Simple 404 pagina
function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="text-center text-slate-100">
        <h1 className="text-3xl font-bold mb-2">404 – Pagina niet gevonden</h1>
        <p className="text-slate-400 mb-4">
          Deze route bestaat (nog) niet in Loesoe.
        </p>
        <a
          href="/dashboard"
          className="inline-flex items-center rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-emerald-400 transition-colors"
        >
          Naar dashboard
        </a>
      </div>
    </div>
  );
}

// Guard voor /dashboard
function DashboardGuard() {
  const query = useQuery();
  const urlToken = query.get("token");

  // Token via URL ?token=... → opslaan
  if (urlToken) {
    try {
      setToken(urlToken);
    } catch {
      // ignore
    }
  }

  const token = getToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <DashboardPage />;
}

function AppRouter() {
  console.log("[Loesoe] main.jsx geladen (router + login + guard)");

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardGuard />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root niet gevonden");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>
);
