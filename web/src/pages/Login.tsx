// web/src/pages/Login.tsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../lib/api";

const LoginPage: React.FC = () => {
  const navigate = useNavigate();

  const [email, setEmail] = useState("richard@example.com");
  const [password, setPassword] = useState("Test1234!");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      // gebruikt login() uit api.ts → POST /login (JSON) → zet token in localStorage
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      console.error("[login] error", err);
      setError('Login mislukt. Controleer je e-mail en wachtwoord.');
    } finally {
      setLoading(false);
    }
  };

  const handleClearToken = () => {
    try {
      localStorage.removeItem("loesoe_token");
    } catch {
      // ignore
    }
    setError(null);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="w-full max-w-md bg-slate-800 rounded-2xl p-8 shadow-xl">
        <h1 className="text-2xl font-bold text-white mb-2">Loesoe – Inloggen</h1>
        <p className="text-slate-300 mb-6 text-sm">
          Log in om je persoonlijke Loesoe-dashboard te openen.
        </p>

        {error && (
          <div className="mb-4 rounded-md bg-red-500/10 border border-red-500/40 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-200 mb-1">E-mail</label>
            <input
              type="email"
              className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-200 mb-1">
              Wachtwoord
            </label>
            <input
              type="password"
              className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-4 inline-flex items-center justify-center rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-emerald-400 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Inloggen..." : "Inloggen"}
          </button>
        </form>

        <button
          type="button"
          onClick={handleClearToken}
          className="w-full mt-4 inline-flex items-center justify-center rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700/60 transition-colors"
        >
          Token wissen
        </button>

        <p className="mt-4 text-xs text-slate-500 text-center">
          API: http://localhost:8000
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
