import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "../../lib/utils";
import { useTheme } from "../../theme/ThemeContext";

export interface DonutData {
  name: string;
  value: number;
  color?: string;
}

const DEFAULT_PALETTE = [
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-cyan)",
  "var(--color-success)",
  "var(--color-warning)",
  "var(--color-danger)",
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-success)",
  "var(--color-cyan)",
];

function resolveColor(c: string): string {
  if (c.startsWith("var(")) {
    const varName = c.slice(4, -1);
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || c;
  }
  return c;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: DonutData; value: number }>;
}

function DonutTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0].payload;
  return (
    <div className="panel-flat px-3 py-2 text-[12px] shadow-lg">
      <div className="font-bold text-[var(--color-text)]">{item.name}</div>
      <div className="text-[var(--color-text-muted)] mt-0.5">
        ${item.value.toFixed(2)}
      </div>
    </div>
  );
}

export function DonutChart({
  data,
  size = 180,
  innerRadius = 55,
  outerRadius = 80,
  centerLabel,
  centerValue,
  className,
}: {
  data: DonutData[];
  size?: number;
  innerRadius?: number;
  outerRadius?: number;
  centerLabel?: string;
  centerValue?: string;
  className?: string;
}) {
  const { theme } = useTheme();
  const coloredData = data.map((d, i) => ({
    ...d,
    resolvedColor: resolveColor(d.color || DEFAULT_PALETTE[i % DEFAULT_PALETTE.length]),
  }));
  // theme dependency forces re-evaluation on theme switch
  void theme;

  if (data.length === 0 || data.every((d) => d.value <= 0)) {
    return (
      <div
        className={cn("flex items-center justify-center text-[var(--color-text-muted)] text-[12px]", className)}
        style={{ height: size }}
      >
        Sin datos
      </div>
    );
  }

  return (
    <div className={cn("relative", className)} style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={coloredData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={2}
            stroke="none"
          >
            {coloredData.map((entry, i) => (
              <Cell key={i} fill={entry.resolvedColor} />
            ))}
          </Pie>
          <Tooltip content={<DonutTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      {(centerLabel || centerValue) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          {centerValue && (
            <div className="num text-[18px] font-extrabold text-[var(--color-text)] leading-none">
              {centerValue}
            </div>
          )}
          {centerLabel && (
            <div className="text-[11px] font-bold uppercase text-[var(--color-text-muted)] mt-1">
              {centerLabel}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
