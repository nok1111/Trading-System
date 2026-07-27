import { cn } from "../../lib/utils";

interface GaugeProps {
  value: number;
  max?: number;
  label?: string;
  sublabel?: string;
  size?: number;
  color?: string;
  className?: string;
}

export function Gauge({
  value,
  max = 100,
  label,
  sublabel,
  size = 120,
  color = "var(--color-primary)",
  className,
}: GaugeProps) {
  const pct = Math.min(Math.max(value / max, 0), 1);
  const radius = (size - 12) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - pct);

  return (
    <div
      className={cn("flex flex-col items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-2)"
          strokeWidth={8}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        {label && (
          <span className="text-[20px] font-extrabold text-[var(--color-text)]">
            {label}
          </span>
        )}
        {sublabel && (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            {sublabel}
          </span>
        )}
      </div>
    </div>
  );
}
