import { useState } from "react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";

interface BacktestResult {
  symbol: string;
  strategy: string;
  interval: string;
  initial_cash: number;
  final_equity: number;
  total_return_pct: number;
  annualized_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  avg_trade_pnl: number;
  equity_curve: { time: string; equity: number; price: number }[];
  trades: {
    entry_time: string;
    exit_time: string;
    side: string;
    quantity: number;
    entry_price: number;
    exit_price: number;
    pnl: number;
    pnl_pct: number;
    reason: string;
    bars_held: number;
  }[];
  error?: string;
}

const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LTCUSDT", "TRXUSDT"];
const intervals = ["5m", "15m", "1h", "4h", "1d"];

export function BacktestPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("1h");
  const [limit, setLimit] = useState("500");
  const [initialCash, setInitialCash] = useState("10000");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");

  const handleRun = async () => {
    setError("");
    setResult(null);
    setRunning(true);
    try {
      const r = await api<BacktestResult>("/api/intelligence/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          strategy: "trend_momentum",
          interval,
          limit: parseInt(limit),
          initial_cash: parseFloat(initialCash),
        }),
      });
      if (r.error) {
        setError(r.error);
      } else {
        setResult(r);
      }
    } catch (e: any) {
      setError(e.message || "Error al ejecutar backtest");
    }
    setRunning(false);
  };

  return (
    <div className="space-y-6">
      {/* Config panel */}
      <div className="panel p-5">
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Configuración del Backtest</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Símbolo</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            >
              {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Intervalo</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            >
              {intervals.map((i) => <option key={i} value={i}>{i}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Velas</label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Capital inicial (USDT)</label>
            <input
              type="number"
              value={initialCash}
              onChange={(e) => setInitialCash(e.target.value)}
              className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-4">
          <button
            onClick={handleRun}
            disabled={running}
            className={cn(
              "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
              running
                ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                : "bg-[var(--color-primary)] text-white hover:opacity-90"
            )}
          >
            {running ? "Ejecutando..." : "Ejecutar Backtest"}
          </button>
          <span className="text-[12px] text-[var(--color-text-muted)]">
            Estrategia: TrendMomentum (EMA9/21 + RSI + Volume + ATR trailing stop)
          </span>
        </div>

        {error && (
          <div className="mt-4 rounded-[8px] bg-[var(--color-danger)]/10 p-3 text-[12px] font-semibold text-[var(--color-danger)]">
            {error}
          </div>
        )}
      </div>

      {/* Results */}
      {result && !result.error && (
        <>
          {/* Metrics grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <MetricCard
              label="Retorno Total"
              value={`${result.total_return_pct > 0 ? "+" : ""}${result.total_return_pct.toFixed(2)}%`}
              color={result.total_return_pct >= 0 ? "success" : "danger"}
            />
            <MetricCard
              label="Equity Final"
              value={`$${result.final_equity.toLocaleString("en-US", { maximumFractionDigits: 2 })}`}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={result.sharpe_ratio.toFixed(2)}
              color={result.sharpe_ratio >= 1 ? "success" : result.sharpe_ratio < 0 ? "danger" : undefined}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${result.max_drawdown_pct.toFixed(2)}%`}
              color="danger"
            />
            <MetricCard
              label="Win Rate"
              value={`${(result.win_rate * 100).toFixed(1)}%`}
              color={result.win_rate >= 0.5 ? "success" : undefined}
            />
            <MetricCard
              label="Profit Factor"
              value={result.profit_factor.toFixed(2)}
              color={result.profit_factor >= 1.5 ? "success" : undefined}
            />
            <MetricCard label="Total Trades" value={String(result.total_trades)} />
            <MetricCard
              label="PnL Promedio"
              value={`$${result.avg_trade_pnl.toFixed(2)}`}
              color={result.avg_trade_pnl >= 0 ? "success" : "danger"}
            />
            <MetricCard
              label="Retorno Anualizado"
              value={`${result.annualized_return_pct > 0 ? "+" : ""}${result.annualized_return_pct.toFixed(2)}%`}
              color={result.annualized_return_pct >= 0 ? "success" : "danger"}
            />
          </div>

          {/* Equity curve chart */}
          <div className="panel p-4">
            <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3">Curva de Equity</h3>
            <EquityCurveChart data={result.equity_curve} />
          </div>

          {/* Trades table */}
          <div className="panel p-4">
            <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3">
              Trades ({result.trades.filter((t) => t.side === "SELL").length} cerrados)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="text-left pb-2">Entrada</th>
                    <th className="text-left pb-2">Salida</th>
                    <th className="text-right pb-2">Side</th>
                    <th className="text-right pb-2">Entry</th>
                    <th className="text-right pb-2">Exit</th>
                    <th className="text-right pb-2">PnL</th>
                    <th className="text-right pb-2">PnL %</th>
                    <th className="text-right pb-2">Razón</th>
                    <th className="text-right pb-2">Barras</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-b border-[var(--color-border)]/30">
                      <td className="py-1.5 text-[var(--color-text-muted)]">{t.entry_time ? new Date(t.entry_time).toLocaleString() : "—"}</td>
                      <td className="py-1.5 text-[var(--color-text-muted)]">{t.exit_time ? new Date(t.exit_time).toLocaleString() : "—"}</td>
                      <td className="text-right py-1.5">
                        <span className={t.side === "BUY" ? "text-[var(--color-success)] font-bold" : "text-[var(--color-danger)] font-bold"}>
                          {t.side}
                        </span>
                      </td>
                      <td className="text-right py-1.5 text-[var(--color-text)]">${t.entry_price.toFixed(4)}</td>
                      <td className="text-right py-1.5 text-[var(--color-text)]">{t.exit_price ? `$${t.exit_price.toFixed(4)}` : "—"}</td>
                      <td className={cn("text-right py-1.5 font-bold", t.pnl > 0 ? "text-[var(--color-success)]" : t.pnl < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]")}>
                        {t.pnl !== 0 ? `$${t.pnl.toFixed(2)}` : "—"}
                      </td>
                      <td className={cn("text-right py-1.5 font-bold", t.pnl_pct > 0 ? "text-[var(--color-success)]" : t.pnl_pct < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]")}>
                        {t.pnl_pct !== 0 ? `${t.pnl_pct.toFixed(2)}%` : "—"}
                      </td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{t.reason}</td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{t.bars_held}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: "success" | "danger" }) {
  return (
    <div className="panel p-3">
      <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">{label}</div>
      <div className={cn(
        "text-[18px] font-extrabold",
        color === "success" ? "text-[var(--color-success)]" : color === "danger" ? "text-[var(--color-danger)]" : "text-[var(--color-text)]"
      )}>
        {value}
      </div>
    </div>
  );
}

function EquityCurveChart({ data }: { data: { time: string; equity: number; price: number }[] }) {
  if (!data || data.length === 0) {
    return <div className="text-[12px] text-[var(--color-text-muted)] py-8 text-center">Sin datos</div>;
  }

  const equities = data.map((d) => d.equity);
  const minEq = Math.min(...equities);
  const maxEq = Math.max(...equities);
  const range = maxEq - minEq || 1;
  const width = 800;
  const height = 200;
  const padding = 20;

  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((d.equity - minEq) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(" ");

  const initialEquity = data[0]?.equity ?? 0;
  const isProfit = data[data.length - 1]?.equity >= initialEquity;
  const lineColor = isProfit ? "var(--color-success)" : "var(--color-danger)";

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height: 200 }}>
      <polyline
        points={points}
        fill="none"
        stroke={lineColor}
        strokeWidth="2"
      />
      <polyline
        points={`${padding},${height - padding} ${points} ${width - padding},${height - padding}`}
        fill={isProfit ? "var(--color-success)" : "var(--color-danger)"}
        opacity="0.1"
      />
      <text x={padding} y={padding + 5} fill="var(--color-text-muted)" fontSize="11">
        ${maxEq.toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </text>
      <text x={padding} y={height - padding + 15} fill="var(--color-text-muted)" fontSize="11">
        ${minEq.toLocaleString("en-US", { maximumFractionDigits: 0 })}
      </text>
    </svg>
  );
}
