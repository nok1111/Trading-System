import { BADGES, type Badge } from "../../data/tutorials";

interface BadgeDisplayProps {
  badges: typeof BADGES;
  earnedBadgeIds: string[];
  newlyEarned?: string | null;
}

export function BadgeDisplay({
  badges,
  earnedBadgeIds,
  newlyEarned,
}: BadgeDisplayProps) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
      {badges.map((badge: Badge) => {
        const earned = earnedBadgeIds.includes(badge.id);
        const isNewlyEarned = newlyEarned === badge.id;

        return (
          <div
            key={badge.id}
            className="group relative flex flex-col items-center gap-2 p-3 rounded-xl transition-all cursor-default"
            style={{
              background: earned
                ? "color-mix(in srgb, var(--color-primary) 8%, var(--color-surface))"
                : "var(--color-surface-2)",
              border: isNewlyEarned
                ? "2px solid var(--color-primary)"
                : earned
                ? "1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)"
                : "1px solid var(--color-border)",
              animation: isNewlyEarned
                ? "badge-reveal 0.6s ease-out"
                : "none",
            }}
          >
            <style>{`
              @keyframes badge-reveal {
                0% { transform: scale(0.5) rotate(-10deg); opacity: 0; }
                50% { transform: scale(1.15) rotate(5deg); opacity: 1; }
                100% { transform: scale(1) rotate(0deg); opacity: 1; }
              }
            `}</style>

            {/* Badge icon */}
            <div
              className="text-[28px] leading-none transition-all"
              style={{
                filter: earned ? "none" : "grayscale(1) opacity(0.4)",
              }}
            >
              {badge.icon}
            </div>

            {/* Badge name */}
            <div
              className="text-[10px] font-bold text-center leading-tight"
              style={{
                color: earned
                  ? "var(--color-text)"
                  : "var(--color-text-muted)",
              }}
            >
              {badge.name}
            </div>

            {/* Lock overlay for unearned */}
            {!earned && (
              <div className="absolute top-1.5 right-1.5 text-[10px] opacity-50">
                🔒
              </div>
            )}

            {/* New badge indicator */}
            {isNewlyEarned && (
              <div
                className="absolute -top-1.5 -right-1.5 text-[8px] font-bold px-1.5 py-0.5 rounded-full text-white"
                style={{ background: "var(--color-success)" }}
              >
                NEW
              </div>
            )}

            {/* Tooltip on hover */}
            <div
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20"
              style={{
                background: "var(--color-text)",
                color: "var(--color-bg)",
              }}
            >
              <div className="text-[11px] font-bold">{badge.name}</div>
              <div className="text-[10px] opacity-80 mt-0.5">
                {badge.description}
              </div>
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent"
                style={{ borderTopColor: "var(--color-text)" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
