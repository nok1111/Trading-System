import { XP_LEVELS, getLevelForXp, getNextLevel } from "../../data/tutorials";

interface XPBarProps {
  xp: number;
  compact?: boolean;
}

export function XPBar({ xp, compact = false }: XPBarProps) {
  const current = getLevelForXp(xp);
  const next = getNextLevel(current.level);

  const xpInLevel = xp - current.minXp;
  const xpForLevel = next ? next.minXp - current.minXp : 0;
  const progressPct = next
    ? Math.min(100, Math.round((xpInLevel / xpForLevel) * 100))
    : 100;
  const xpToNext = next ? next.minXp - xp : 0;

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[16px]">{current.icon}</span>
          <span className="text-[12px] font-bold text-[var(--color-text)]">
            Nivel {current.level}
          </span>
          <span className="text-[11px] text-[var(--color-text-muted)] ml-auto">
            {xp} XP
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
          <div
            className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Level header */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-xl text-[24px]"
          style={{
            background: "color-mix(in srgb, var(--color-primary) 14%, transparent)",
          }}
        >
          {current.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-extrabold text-[var(--color-text)]">
            {current.title}
          </div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            Nivel {current.level}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[18px] font-extrabold text-[var(--color-primary)]">
            {xp}
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)] uppercase font-bold">
            XP Total
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between text-[11px] mb-1.5">
          <span className="text-[var(--color-text-muted)] font-medium">
            {xpInLevel} / {xpForLevel || xpInLevel} XP
          </span>
          {next ? (
            <span className="text-[var(--color-text-muted)]">
              Next: <span className="text-[var(--color-text)] font-bold">{next.title}</span>
            </span>
          ) : (
            <span className="text-[var(--color-warning)] font-bold">¡Nivel Máximo!</span>
          )}
        </div>
        <div className="h-2.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-accent)] transition-all duration-700 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        {next && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1 text-center">
            {xpToNext} XP para el siguiente nivel
          </div>
        )}
      </div>

      {/* Level milestones */}
      <div className="flex items-center justify-between gap-1 pt-1">
        {XP_LEVELS.map((lvl) => {
          const reached = xp >= lvl.minXp;
          return (
            <div
              key={lvl.level}
              className="flex flex-col items-center gap-0.5 flex-1"
              title={`${lvl.title} (${lvl.minXp} XP)`}
            >
              <div
                className="text-[14px] transition-all"
                style={{
                  opacity: reached ? 1 : 0.3,
                  filter: reached ? "none" : "grayscale(1)",
                }}
              >
                {lvl.icon}
              </div>
              <div
                className="text-[8px] font-bold"
                style={{
                  color: reached
                    ? "var(--color-primary)"
                    : "var(--color-text-muted)",
                }}
              >
                {lvl.level}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
