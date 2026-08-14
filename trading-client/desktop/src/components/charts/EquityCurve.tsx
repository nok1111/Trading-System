import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { cn } from "../../lib/utils";

export interface EquityPoint {
  timestamp: string;
  equity: number;
}

interface EquityTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: EquityPoint }>;
}

function EquityTooltip({ active, payload }: EquityTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  const date = new Date(point.timestamp);
  return (
    <div className="panel-flat px-3 py-2 text-[12px] shadow-lg">
      <div className="num font-bold text-[var(--color-text)]">${point.equity.toFixed(2)}</div>
      <div className="text-[var(--color-text-muted)] text-[10px] mt-0.5">
        {date.toLocaleDateString()} {date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
      </div>
    </div>
  );
}

export function EquityCurve({
  data,
  height = 200,
  color = "var(--color-primary)",
  className,
}: {
  data: EquityPoint[];
  height?: number;
  color?: string;
  className?: string;
}) {
  const chartData = useMemo(
    () =>
      data
        .slice()
        .reverse()
        .map((d) => ({
          ...d,
          idx: d.timestamp,
        })),
    [data]
  );

  const gradientId = useMemo(() => `equityGrad-${Math.random().toString(36).slice(2, 9)}`, []);

  if (chartData.length < 2) {
    return (
      <div
        className={cn(
          "flex items-center justify-center text-[var(--color-text-muted)] text-[12px]",
          className
        )}
        style={{ height }}
      >
        Sin datos suficientes
      </div>
    );
  }

  const resolvedColor = useMemo(() => {
    if (color.startsWith("var(")) {
      const varName = color.slice(4, -1);
      return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || color;
    }
    return color;
  }, [color]);

  return (
    <div className={cn(className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={resolvedColor} stopOpacity={0.3} />
              <stop offset="100%" stopColor={resolvedColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
          <XAxis
            dataKey="idx"
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: string) => {
              const d = new Date(v);
              return d.toLocaleDateString([], { month: "short", day: "numeric" });
            }}
            minTickGap={40}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            tickLine={false}
            axisLine={false}
            width={50}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            domain={["auto", "auto"]}
          />
          <Tooltip content={<EquityTooltip />} />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={resolvedColor}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
