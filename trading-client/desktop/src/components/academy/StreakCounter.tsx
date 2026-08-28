import { Flame } from "lucide-react";

interface StreakCounterProps {
  streak: number;
  lastStudyDays?: boolean[]; // last 7 days, index 0 = oldest, index 6 = today
}

export function StreakCounter({ streak, lastStudyDays = [] }: StreakCounterProps) {
  const days = Array.from({ length: 7 }, (_, i) => lastStudyDays[i] || false);
  const dayLabels = ["L", "M", "X", "J", "V", "S", "D"];

  return (
    <div className="space-y-3">
      {/* Flame + streak number */}
      <div className="flex items-center gap-3">
        <div
          className="relative flex items-center justify-center w-12 h-12 rounded-xl"
          style={{
            background:
              streak > 0
                ? "color-mix(in srgb, var(--color-warning) 14%, transparent)"
                : "var(--color-surface-2)",
          }}
        >
          <Flame
            size={24}
            className={streak > 0 ? "text-[var(--color-warning)]" : "text-[var(--color-text-muted)]"}
            style={{
              animation:
                streak > 0
                  ? "streak-pulse 1.5s ease-in-out infinite"
                  : "none",
            }}
          />
          <style>{`
            @keyframes streak-pulse {
              0%, 100% { transform: scale(1); opacity: 1; }
              50% { transform: scale(1.15); opacity: 0.85; }
            }
          `}</style>
        </div>
        <div>
          <div className="text-[22px] font-extrabold text-[var(--color-text)] leading-none">
            {streak}
          </div>
          <div className="text-[11px] text-[var(--color-text-muted)] font-medium">
            {streak === 1 ? "día seguido" : "días seguidos"}
          </div>
        </div>
      </div>

      {/* 7-day dots */}
      <div className="flex items-center justify-between gap-1">
        {days.map((studied, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center transition-all"
              style={{
                background: studied
                  ? "var(--color-warning)"
                  : "var(--color-surface-2)",
                border: studied
                  ? "none"
                  : "1px solid var(--color-border)",
              }}
            >
              {studied && (
                <Flame size={12} className="text-white" />
              )}
            </div>
            <span
              className="text-[9px] font-bold"
              style={{
                color: studied
                  ? "var(--color-warning)"
                  : "var(--color-text-muted)",
              }}
            >
              {dayLabels[i]}
            </span>
          </div>
        ))}
      </div>

      {/* Motivational message */}
      <div
        className="text-[11px] font-medium text-center py-1.5 px-2 rounded-lg"
        style={{
          background: streak > 0
            ? "color-mix(in srgb, var(--color-warning) 8%, transparent)"
            : "var(--color-surface-2)",
          color: streak > 0
            ? "var(--color-warning)"
            : "var(--color-text-muted)",
        }}
      >
        {streak > 0
          ? "¡Mantén tu racha!"
          : "¡Estudia hoy para iniciar tu racha!"}
      </div>
    </div>
  );
}
