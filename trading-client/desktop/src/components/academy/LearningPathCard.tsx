import { CheckCircle2, Play, ChevronRight } from "lucide-react";
import type { LearningPath } from "../../data/tutorials";

interface LearningPathCardProps {
  path: LearningPath;
  completedTutorials: string[];
  onClick: () => void;
}

export function LearningPathCard({
  path,
  completedTutorials,
  onClick,
}: LearningPathCardProps) {
  const completedCount = path.tutorialIds.filter((id) =>
    completedTutorials.includes(id),
  ).length;
  const totalCount = path.tutorialIds.length;
  const progressPct = Math.round((completedCount / totalCount) * 100);
  const isCompleted = completedCount === totalCount;
  const isStarted = completedCount > 0;

  return (
    <button
      onClick={onClick}
      className="group relative w-full text-left p-4 rounded-2xl transition-all hover:scale-[1.02] hover:shadow-lg"
      style={{
        background: "var(--color-surface)",
        border: `1px solid ${
          isCompleted
            ? "color-mix(in srgb, var(--color-success) 40%, transparent)"
            : isStarted
            ? "color-mix(in srgb, var(--color-primary) 30%, transparent)"
            : "var(--color-border)"
        }`,
        borderTop: `3px solid ${path.color}`,
      }}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-xl text-[24px] flex-shrink-0"
          style={{
            background: `color-mix(in srgb, ${path.color} 14%, transparent)`,
          }}
        >
          {path.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-extrabold text-[var(--color-text)] leading-tight">
            {path.title}
          </div>
          <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5 leading-relaxed">
            {path.description}
          </div>
        </div>
        {isCompleted ? (
          <CheckCircle2
            size={20}
            className="text-[var(--color-success)] flex-shrink-0"
          />
        ) : isStarted ? (
          <Play
            size={16}
            className="text-[var(--color-primary)] flex-shrink-0"
          />
        ) : (
          <ChevronRight
            size={18}
            className="text-[var(--color-text-muted)] flex-shrink-0 group-hover:text-[var(--color-text)] transition-colors"
          />
        )}
      </div>

      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-bold">
          <span style={{ color: path.color }}>
            {completedCount} / {totalCount} tutoriales
          </span>
          <span className="text-[var(--color-text-muted)]">
            {progressPct}%
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-[var(--color-surface-2)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${progressPct}%`,
              background: path.color,
            }}
          />
        </div>
      </div>

      {/* Status badge */}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {path.tutorialIds.slice(0, 5).map((id, i) => {
            const done = completedTutorials.includes(id);
            return (
              <div
                key={i}
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: done ? path.color : "var(--color-surface-2)",
                }}
              />
            );
          })}
          {path.tutorialIds.length > 5 && (
            <span className="text-[9px] text-[var(--color-text-muted)] ml-0.5">
              +{path.tutorialIds.length - 5}
            </span>
          )}
        </div>
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded-full"
          style={{
            background: isCompleted
              ? "color-mix(in srgb, var(--color-success) 14%, transparent)"
              : isStarted
              ? "color-mix(in srgb, var(--color-primary) 14%, transparent)"
              : "var(--color-surface-2)",
            color: isCompleted
              ? "var(--color-success)"
              : isStarted
              ? "var(--color-primary)"
              : "var(--color-text-muted)",
          }}
        >
          {isCompleted
            ? "Completado"
            : isStarted
            ? "En progreso"
            : "Empezar"}
        </span>
      </div>
    </button>
  );
}
