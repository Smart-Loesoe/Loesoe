import React from "react";

type SlimheidsmeterCardProps = {
  value: number; // 0–100
  selfLearning?: {
    last_mood?: string | null;
    preferences_count?: number;
  };
};

function getLevelLabel(value: number): string {
  if (value >= 90) return "ULTRA";
  if (value >= 70) return "PRO";
  if (value >= 40) return "GROWING";
  return "BEGINNER";
}

export const SlimheidsmeterCard: React.FC<SlimheidsmeterCardProps> = ({
  value,
  selfLearning,
}) => {
  const level = getLevelLabel(value);
  const clamped = Math.min(100, Math.max(0, value));

  const moodText =
    selfLearning?.last_mood && selfLearning.last_mood.trim().length > 0
      ? selfLearning.last_mood
      : "onbekend";

  const prefs = selfLearning?.preferences_count ?? 0;

  return (
    <div className="w-full rounded-2xl border border-slate-800 bg-slate-950/60 p-4 md:p-5 shadow-lg flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-slate-400">
            Slimheidsmeter
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-50">
              {clamped.toFixed(1)}%
            </span>
            <span className="px-2 py-0.5 text-xs rounded-full border border-emerald-500/40 text-emerald-300">
              Level {level}
            </span>
          </div>
        </div>

        {/* Simpele progress ring-achtige cirkel */}
        <div className="relative inline-flex items-center justify-center">
          <svg className="w-16 h-16 -rotate-90">
            <circle
              cx="32"
              cy="32"
              r="26"
              stroke="currentColor"
              strokeWidth="6"
              className="text-slate-800"
              fill="transparent"
            />
            <circle
              cx="32"
              cy="32"
              r="26"
              stroke="currentColor"
              strokeWidth="6"
              className="text-emerald-400"
              strokeDasharray={2 * Math.PI * 26}
              strokeDashoffset={
                (1 - clamped / 100) * (2 * Math.PI * 26)
              }
              fill="transparent"
              strokeLinecap="round"
            />
          </svg>
          <span className="absolute text-xs font-semibold text-slate-200">
            {Math.round(clamped)}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
        <span>🧠 Zelflerend actief</span>
        <span>⚙️ Modules stabiel</span>
        <span>📈 Gebruik meegewogen</span>
      </div>

      <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-400">
        <span className="px-2 py-1 rounded-full bg-slate-900/70">
          Laatste mood: <span className="font-medium text-slate-200">{moodText}</span>
        </span>
        <span className="px-2 py-1 rounded-full bg-slate-900/70">
          Voorkeuren:{" "}
          <span className="font-medium text-slate-200">{prefs}</span>
        </span>
      </div>
    </div>
  );
};
