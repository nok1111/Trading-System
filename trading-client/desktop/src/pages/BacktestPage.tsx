import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { cn, fmtDate } from "../lib/utils";
import { Tooltip, InfoPanel } from "../components/common/Tooltip";

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
    fee?: number;
    reason: string;
    bars_held: number;
  }[];
  buy_hold_return_pct: number;
  total_fees: number;
  total_slippage_cost: number;
  net_return_pct: number;
  alpha_pct: number;
  error?: string;
}

interface OptimizationResult {
  symbol: string;
  strategy: string;
  interval: string;
  total_combinations: number;
  best_params: Record<string, number>;
  best_sharpe: number;
  best_return_pct: number;
  best_win_rate: number;
  best_max_drawdown: number;
  best_alpha: number;
  all_results: {
    params: Record<string, number>;
    total_return_pct: number;
    sharpe: number;
    max_drawdown_pct: number;
    win_rate: number;
    total_trades: number;
    alpha: number;
  }[];
  error?: string;
}

interface AutoAssignResult {
  assignments: {
    symbol: string;
    best_strategy: string;
    best_sharpe: number;
    best_return_pct: number;
    best_alpha_pct: number;
    best_win_rate: number;
    best_max_drawdown: number;
    all_results: {
      strategy: string;
      sharpe: number;
      total_return_pct: number;
      alpha_pct: number;
      win_rate: number;
      max_drawdown_pct: number;
      total_trades: number;
      total_fees: number;
    }[];
    interval: string;
    limit: number;
  }[];
  total_symbols: number;
  evaluated_at: string;
  strategy_distribution: Record<string, number>;
  error?: string;
}

// Symbols available across all supported brokers (Binance, Bybit, OKX, Kraken, Coinbase, KuCoin, Bitget)
const symbols = [
  // ─── Major (top market cap, available everywhere) ───
  "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "TRXUSDT", "LTCUSDT", "AVAXUSDT",
  // ─── Large cap (DeFi / L1 / L2) ───
  "LINKUSDT", "DOTUSDT", "MATICUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT", "APTUSDT", "FILUSDT", "INJUSDT",
  // ─── Mid cap (emerging L1s and infrastructure) ───
  "SUIUSDT", "SEIUSDT", "TIAUSDT", "RNDRUSDT", "FETUSDT", "WLDUSDT", "ORDIUSDT", "TONUSDT", "JUPUSDT", "PYTHUSDT",
  // ─── Memes (high volatility, good for mean reversion) ───
  "PEPEUSDT", "SHIBUSDT", "WIFUSDT", "FLOKIUSDT", "BONKUSDT",
];
const intervals = ["5m", "15m", "1h", "4h", "1d"];
const strategies = [
  { id: "trend_momentum", label: "Trend Momentum", desc: "EMA crossover + RSI + volumen — mercados con tendencia" },
  { id: "mean_reversion", label: "Mean Reversion", desc: "RSI oversold + Bollinger Bands — mercados laterales" },
  { id: "breakout", label: "Breakout", desc: "Donchian Channels + volumen — movimientos explosivos" },
  { id: "grid", label: "Grid Trading", desc: "Rango ATR dinamico — income pasivo en sideways" },
  { id: "macd_momentum", label: "MACD Momentum", desc: "Cruce MACD + histograma — detecta momentum temprano" },
  { id: "bollinger_squeeze", label: "Bollinger Squeeze", desc: "Compresion de volatilidad + expansion — post-consolidacion" },
  { id: "supertrend", label: "Supertrend", desc: "ATR trend following — tendencias sostenidas, menos whipsaws" },
  { id: "rsi_divergence", label: "RSI Divergence", desc: "Divergencia precio/RSI — detecta reverses antes que otros" },
];

export function BacktestPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [strategy, setStrategy] = useState("trend_momentum");
  const [interval, setInterval] = useState("1h");
  const [limit, setLimit] = useState("500");
  const [initialCash, setInitialCash] = useState("10000");
  const [running, setRunning] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [autoAssigning, setAutoAssigning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [optResult, setOptResult] = useState<OptimizationResult | null>(null);
  const [autoResult, setAutoResult] = useState<AutoAssignResult | null>(null);
  const [mtfResult, setMtfResult] = useState<any>(null);
  const [wfResult, setWfResult] = useState<any>(null);
  const [mtfLoading, setMtfLoading] = useState(false);
  const [wfLoading, setWfLoading] = useState(false);
  const [error, setError] = useState("");
  const [showHistorical, setShowHistorical] = useState(false);

  const handleRun = async () => {
    setError("");
    setResult(null);
    setOptResult(null);
    setRunning(true);
    try {
      const r = await api<BacktestResult>("/api/intelligence/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          strategy,
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

  const handleOptimize = async () => {
    setError("");
    setResult(null);
    setOptResult(null);
    setOptimizing(true);
    try {
      const r = await api<OptimizationResult>("/api/intelligence/backtest/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          strategy,
          interval,
          limit: parseInt(limit),
          initial_cash: parseFloat(initialCash),
          max_combinations: 50,
        }),
      });
      if (r.error) {
        setError(r.error);
      } else {
        setOptResult(r);
      }
    } catch (e: any) {
      setError(e.message || "Error al optimizar");
    }
    setOptimizing(false);
  };

  const handleAutoAssign = async () => {
    setError("");
    setResult(null);
    setOptResult(null);
    setAutoResult(null);
    setAutoAssigning(true);
    try {
      // Run on a representative subset (top 10 symbols) to keep it fast
      const subset = symbols.slice(0, 10);
      const r = await api<AutoAssignResult>("/api/intelligence/backtest/auto-assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbols: subset,
          interval,
          limit: parseInt(limit),
          initial_cash: parseFloat(initialCash),
        }),
      });
      if (r.error) {
        setError(r.error);
      } else {
        setAutoResult(r);
      }
    } catch (e: any) {
      setError(e.message || "Error al auto-asignar");
    }
    setAutoAssigning(false);
  };

  const handleMTF = async () => {
    setMtfLoading(true);
    setMtfResult(null);
    try {
      const r = await api<any>("/api/intelligence/mtf/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, primary_interval: interval, strategy_name: strategy }),
      });
      if (r.error) { setError(r.error); } else { setMtfResult(r); }
    } catch (e: any) { setError(e.message || "Error MTF"); }
    setMtfLoading(false);
  };

  const handleWalkForward = async () => {
    setWfLoading(true);
    setWfResult(null);
    try {
      const r = await api<any>("/api/intelligence/backtest/walk-forward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol, strategy, interval,
          limit: Math.max(parseInt(limit), 1000),
          initial_cash: parseFloat(initialCash),
          num_windows: 5, train_ratio: 0.7,
        }),
      });
      if (r.error) { setError(r.error); } else { setWfResult(r); }
    } catch (e: any) { setError(e.message || "Error Walk-Forward"); }
    setWfLoading(false);
  };

  return (
    <div className="space-y-6">
      {/* Config panel */}
      <div className="panel p-5">
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-4">Configuración del Backtest</h2>
        <InfoPanel title="Como usar el Backtest" className="mb-4">
          <p><strong>Ejecutar Backtest:</strong> Simula una estrategia con datos historicos reales de Binance. Muestra la curva de equity, trades, y metricas (Sharpe, win rate, drawdown).</p>
          <p><strong>Optimizar Parametros:</strong> Prueba 50 combinaciones de parametros automaticamente y muestra la mejor.</p>
          <p><strong>Auto-Asignar:</strong> Corre las 8 estrategias en 10 simbolos y asigna la mejor a cada uno segun Sharpe ratio.</p>
          <p><strong>MTF Confirm:</strong> Confirma la señal con el timeframe mayor (2h) y menor (30m). Reduce falsas senales.</p>
          <p><strong>Walk-Forward:</strong> Valida que la estrategia no este sobreajustada (overfit). Divide en 5 ventanas y prueba out-of-sample.</p>
        </InfoPanel>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">Estrategia</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            >
              {strategies.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
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

        {/* Strategy description */}
        <div className="mt-3 text-[11px] text-[var(--color-text-muted)]">
          {strategies.find((s) => s.id === strategy)?.desc}
        </div>

        <div className="mt-4 flex items-center gap-4">
          <Tooltip text="Simula la estrategia elegida con datos historicos reales. Muestra curva de equity, trades, Sharpe, win rate y drawdown.">
            <button
              onClick={handleRun}
              disabled={running || optimizing}
              className={cn(
                "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
                running || optimizing
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                  : "bg-[var(--color-primary)] text-white hover:opacity-90"
              )}
            >
              {running ? "Ejecutando..." : "Ejecutar Backtest"}
            </button>
          </Tooltip>
          <Tooltip text="Prueba 50 combinaciones de parametros automaticamente y muestra la mejor segun Sharpe ratio.">
            <button
              onClick={handleOptimize}
              disabled={running || optimizing || autoAssigning}
              className={cn(
                "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
                running || optimizing || autoAssigning
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                  : "bg-[var(--color-surface-3)] text-[var(--color-text)] hover:opacity-90"
              )}
            >
              {optimizing ? "Optimizando..." : "Optimizar Parametros"}
            </button>
          </Tooltip>
          <Tooltip text="Corre las 8 estrategias en 10 simbolos (80 backtests) y asigna la mejor a cada uno segun Sharpe.">
            <button
              onClick={handleAutoAssign}
              disabled={running || optimizing || autoAssigning}
              className={cn(
                "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
                running || optimizing || autoAssigning
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                  : "bg-[var(--color-primary)]/20 text-[var(--color-primary)] hover:opacity-90 border border-[var(--color-primary)]/30"
              )}
            >
              {autoAssigning ? "Analizando..." : "Auto-Asignar Estrategias"}
            </button>
          </Tooltip>
          <Tooltip text="Confirma la señal con timeframe mayor (2h tendencia) y menor (30m RSI). Reduce falsas senales.">
            <button
              onClick={handleMTF}
              disabled={mtfLoading}
              className={cn(
                "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
                mtfLoading
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                  : "bg-[var(--color-warning)]/20 text-[var(--color-warning)] hover:opacity-90 border border-[var(--color-warning)]/30"
              )}
            >
              {mtfLoading ? "Confirmando..." : "MTF Confirm"}
            </button>
          </Tooltip>
          <Tooltip text="Valida que la estrategia no este sobreajustada (overfit). Divide en 5 ventanas y prueba out-of-sample. Robustness score 0-100.">
            <button
              onClick={handleWalkForward}
              disabled={wfLoading}
              className={cn(
                "h-11 px-6 rounded-[10px] text-[14px] font-extrabold transition-all",
                wfLoading
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                  : "bg-[var(--color-success)]/20 text-[var(--color-success)] hover:opacity-90 border border-[var(--color-success)]/30"
              )}
            >
              {wfLoading ? "Validando..." : "Walk-Forward"}
            </button>
          </Tooltip>
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
            <MetricCard
              label="Buy & Hold"
              value={`${result.buy_hold_return_pct > 0 ? "+" : ""}${result.buy_hold_return_pct.toFixed(2)}%`}
              color={result.buy_hold_return_pct >= 0 ? "success" : "danger"}
            />
            <MetricCard
              label="Alpha vs B&H"
              value={`${result.alpha_pct > 0 ? "+" : ""}${result.alpha_pct.toFixed(2)}%`}
              color={result.alpha_pct >= 0 ? "success" : "danger"}
            />
            <MetricCard
              label="Total Fees"
              value={`$${result.total_fees.toFixed(2)}`}
              color="danger"
            />
          </div>

          {/* Alpha interpretation */}
          {result.alpha_pct < 0 && (
            <div className="mt-3 rounded-[8px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 p-3 text-[11px] text-[var(--color-text-muted)]">
              <span className="font-bold text-[var(--color-warning)]">Alpha negativo:</span> Tu estrategia rinde {result.alpha_pct.toFixed(2)}% vs buy-and-hold.
              Seria mas rentable simplemente comprar y mantener el activo.
            </div>
          )}
          {result.alpha_pct >= 0 && result.total_trades > 0 && (
            <div className="mt-3 rounded-[8px] bg-[var(--color-success)]/10 border border-[var(--color-success)]/30 p-3 text-[11px] text-[var(--color-text-muted)]">
              <span className="font-bold text-[var(--color-success)]">Alpha positivo:</span> Tu estrategia supera a buy-and-hold por {result.alpha_pct.toFixed(2)}%.
            </div>
          )}

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
                    <th className="text-right pb-2">Fee</th>
                    <th className="text-right pb-2">Razón</th>
                    <th className="text-right pb-2">Barras</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-b border-[var(--color-border)]/30">
                      <td className="py-1.5 text-[var(--color-text-muted)]">{t.entry_time ? fmtDate(t.entry_time) : "—"}</td>
                      <td className="py-1.5 text-[var(--color-text-muted)]">{t.exit_time ? fmtDate(t.exit_time) : "—"}</td>
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
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{t.fee ? `$${t.fee.toFixed(2)}` : "—"}</td>
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

      {/* Optimization results */}
      {optResult && !optResult.error && (
        <>
          <div className="panel p-5">
            <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-2">Optimizacion de Parametros</h2>
            <div className="text-[12px] text-[var(--color-text-muted)] mb-4">
              {optResult.total_combinations} combinaciones probadas para {optResult.strategy} en {optResult.symbol}
            </div>

            {/* Best params */}
            <div className="rounded-[8px] bg-[var(--color-success)]/10 border border-[var(--color-success)]/30 p-4 mb-4">
              <div className="text-[12px] font-bold text-[var(--color-success)] mb-2">Mejores parametros (por Sharpe)</div>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
                {Object.entries(optResult.best_params).map(([k, v]) => (
                  <div key={k}>
                    <div className="text-[10px] text-[var(--color-text-muted)] uppercase">{k}</div>
                    <div className="text-[14px] font-bold text-[var(--color-text)]">{typeof v === "number" ? v.toFixed(2) : v}</div>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                <MetricCard label="Sharpe" value={optResult.best_sharpe.toFixed(2)} color={optResult.best_sharpe >= 1 ? "success" : undefined} />
                <MetricCard label="Retorno" value={`${optResult.best_return_pct > 0 ? "+" : ""}${optResult.best_return_pct.toFixed(2)}%`} color={optResult.best_return_pct >= 0 ? "success" : "danger"} />
                <MetricCard label="Win Rate" value={`${optResult.best_win_rate.toFixed(1)}%`} color={optResult.best_win_rate >= 50 ? "success" : undefined} />
                <MetricCard label="Max DD" value={`${optResult.best_max_drawdown.toFixed(2)}%`} color="danger" />
                <MetricCard label="Alpha" value={`${optResult.best_alpha > 0 ? "+" : ""}${optResult.best_alpha.toFixed(2)}%`} color={optResult.best_alpha >= 0 ? "success" : "danger"} />
              </div>
            </div>

            {/* Top results table */}
            <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3">Top combinaciones</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="text-left pb-2">#</th>
                    <th className="text-left pb-2">Parametros</th>
                    <th className="text-right pb-2">Retorno %</th>
                    <th className="text-right pb-2">Sharpe</th>
                    <th className="text-right pb-2">Max DD %</th>
                    <th className="text-right pb-2">Win %</th>
                    <th className="text-right pb-2">Alpha %</th>
                    <th className="text-right pb-2">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {optResult.all_results.map((r, i) => (
                    <tr key={i} className={cn("border-b border-[var(--color-border)]/30", i === 0 && "bg-[var(--color-success)]/5")}>
                      <td className="py-1.5 text-[var(--color-text-muted)]">{i + 1}</td>
                      <td className="py-1.5 text-[10px] text-[var(--color-text-muted)]">
                        {Object.entries(r.params).map(([k, v]) => `${k}=${typeof v === "number" ? v.toFixed(1) : v}`).join(", ")}
                      </td>
                      <td className={cn("text-right py-1.5 font-bold", r.total_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {r.total_return_pct > 0 ? "+" : ""}{r.total_return_pct.toFixed(2)}%
                      </td>
                      <td className={cn("text-right py-1.5 font-bold", r.sharpe >= 1 ? "text-[var(--color-success)]" : r.sharpe < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text)]")}>
                        {r.sharpe.toFixed(2)}
                      </td>
                      <td className="text-right py-1.5 text-[var(--color-danger)]">{r.max_drawdown_pct.toFixed(2)}%</td>
                      <td className="text-right py-1.5">{r.win_rate.toFixed(1)}%</td>
                      <td className={cn("text-right py-1.5 font-bold", r.alpha >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {r.alpha > 0 ? "+" : ""}{r.alpha.toFixed(2)}%
                      </td>
                      <td className="text-right py-1.5 text-[var(--color-text-muted)]">{r.total_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* MTF Confirmation results */}
      {mtfResult && !mtfResult.error && (
        <div className="panel p-5">
          <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-3">Multi-Timeframe Confirmation</h2>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3 text-center">
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Higher TF</div>
              <div className={cn(
                "text-[14px] font-extrabold",
                mtfResult.higher_tf_trend === "bullish" && "text-[var(--color-success)]",
                mtfResult.higher_tf_trend === "bearish" && "text-[var(--color-danger)]",
                mtfResult.higher_tf_trend === "neutral" && "text-[var(--color-text-muted)]",
              )}>
                {mtfResult.higher_interval} {mtfResult.higher_tf_trend.toUpperCase()}
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-1">ADX {mtfResult.higher_tf_adx}</div>
            </div>
            <div className="rounded-[8px] bg-[var(--color-surface-2)] p-3 text-center">
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Lower TF RSI</div>
              <div className={cn(
                "text-[14px] font-extrabold",
                mtfResult.lower_tf_rsi > 70 && "text-[var(--color-danger)]",
                mtfResult.lower_tf_rsi < 30 && "text-[var(--color-success)]",
                "text-[var(--color-text)]",
              )}>
                {mtfResult.lower_interval} {mtfResult.lower_tf_rsi.toFixed(1)}
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
                {mtfResult.lower_tf_rsi > 70 ? "Overbought" : mtfResult.lower_tf_rsi < 30 ? "Oversold" : "Normal"}
              </div>
            </div>
            <div className={cn(
              "rounded-[8px] p-3 text-center border",
              mtfResult.confirmed
                ? "bg-[var(--color-success)]/10 border-[var(--color-success)]/30"
                : "bg-[var(--color-danger)]/10 border-[var(--color-danger)]/30"
            )}>
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Confirmado</div>
              <div className={cn(
                "text-[14px] font-extrabold",
                mtfResult.confirmed ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {mtfResult.confirmed ? "SI" : "NO"}
              </div>
              <div className={cn(
                "text-[10px] mt-1 font-bold",
                mtfResult.confidence_boost >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                Boost {mtfResult.confidence_boost >= 0 ? "+" : ""}{mtfResult.confidence_boost}
              </div>
            </div>
          </div>
          <div className="space-y-1">
            {mtfResult.reasons?.map((r: string, i: number) => (
              <div key={i} className="text-[11px] text-[var(--color-text-muted)] flex items-center gap-1">
                <span className="text-[var(--color-primary)]">•</span> {r}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Walk-Forward results */}
      {wfResult && !wfResult.error && (
        <div className="panel p-5">
          <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-2">Walk-Forward Validation</h2>
          <div className="text-[12px] text-[var(--color-text-muted)] mb-4">
            {wfResult.num_windows} ventanas · {wfResult.total_bars} velas · Train ratio {wfResult.train_ratio}
          </div>

          {/* Robustness score gauge */}
          <div className="flex items-center gap-4 mb-4">
            <div className={cn(
              "rounded-[12px] px-4 py-3 border",
              wfResult.robustness_score > 70 && "bg-[var(--color-success)]/10 border-[var(--color-success)]/30",
              wfResult.robustness_score > 50 && wfResult.robustness_score <= 70 && "bg-[var(--color-warning)]/10 border-[var(--color-warning)]/30",
              wfResult.robustness_score <= 50 && "bg-[var(--color-danger)]/10 border-[var(--color-danger)]/30",
            )}>
              <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Robustness</div>
              <div className={cn(
                "text-[24px] font-extrabold",
                wfResult.robustness_score > 70 && "text-[var(--color-success)]",
                wfResult.robustness_score > 50 && wfResult.robustness_score <= 70 && "text-[var(--color-warning)]",
                wfResult.robustness_score <= 50 && "text-[var(--color-danger)]",
              )}>
                {wfResult.robustness_score}<span className="text-[14px] text-[var(--color-text-muted)]">/100</span>
              </div>
            </div>
            <div className="flex-1">
              {wfResult.is_overfit ? (
                <div className="text-[12px] font-bold text-[var(--color-danger)] flex items-center gap-1">
                  OVERFIT — No usar en vivo
                </div>
              ) : wfResult.robustness_score > 70 ? (
                <div className="text-[12px] font-bold text-[var(--color-success)]">
                  ROBUSTO — Apto para vivo
                </div>
              ) : (
                <div className="text-[12px] font-bold text-[var(--color-warning)]">
                  MODERADO — Usar con caution
                </div>
              )}
              <div className="text-[11px] text-[var(--color-text-muted)] mt-1">{wfResult.recommendation}</div>
            </div>
          </div>

          {/* OOS metrics */}
          <div className="grid grid-cols-4 gap-2 mb-4">
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">OOS Sharpe</div>
              <div className={cn("text-[14px] font-bold", wfResult.avg_oos_sharpe >= 1 ? "text-[var(--color-success)]" : wfResult.avg_oos_sharpe < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text)]")}>
                {wfResult.avg_oos_sharpe.toFixed(2)}
              </div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">OOS Return</div>
              <div className={cn("text-[14px] font-bold", wfResult.avg_oos_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                {wfResult.avg_oos_return_pct > 0 ? "+" : ""}{wfResult.avg_oos_return_pct.toFixed(2)}%
              </div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">Degradation</div>
              <div className={cn("text-[14px] font-bold", wfResult.avg_degradation_pct > 50 ? "text-[var(--color-danger)]" : wfResult.avg_degradation_pct > 25 ? "text-[var(--color-warning)]" : "text-[var(--color-success)]")}>
                {wfResult.avg_degradation_pct.toFixed(0)}%
              </div>
            </div>
            <div className="rounded-[6px] bg-[var(--color-surface-2)] p-2 text-center">
              <div className="text-[9px] text-[var(--color-text-muted)] uppercase">OOS Trades</div>
              <div className="text-[14px] font-bold text-[var(--color-text)]">{wfResult.total_oos_trades}</div>
            </div>
          </div>

          {/* Per-window table */}
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                  <th className="text-left pb-2">Window</th>
                  <th className="text-left pb-2">Train Bars</th>
                  <th className="text-left pb-2">Test Bars</th>
                  <th className="text-right pb-2">Train Sharpe</th>
                  <th className="text-right pb-2">Test Sharpe</th>
                  <th className="text-right pb-2">Test Return</th>
                  <th className="text-right pb-2">Degradation</th>
                </tr>
              </thead>
              <tbody>
                {wfResult.windows?.map((w: any) => (
                  <tr key={w.window} className="border-b border-[var(--color-border)]/30">
                    <td className="py-2 font-bold text-[var(--color-text)]">W{w.window}</td>
                    <td className="py-2 text-[var(--color-text-muted)]">{w.train_bars}</td>
                    <td className="py-2 text-[var(--color-text-muted)]">{w.test_bars}</td>
                    <td className={cn("text-right py-2 font-bold", w.train_sharpe >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      {w.train_sharpe.toFixed(2)}
                    </td>
                    <td className={cn("text-right py-2 font-bold", w.test_sharpe >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      {w.test_sharpe.toFixed(2)}
                    </td>
                    <td className={cn("text-right py-2", w.test_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      {w.test_return_pct > 0 ? "+" : ""}{w.test_return_pct.toFixed(2)}%
                    </td>
                    <td className={cn("text-right py-2 font-bold", w.degradation_pct > 50 ? "text-[var(--color-danger)]" : w.degradation_pct > 25 ? "text-[var(--color-warning)]" : "text-[var(--color-success)]")}>
                      {w.degradation_pct.toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 text-[12px] text-[var(--color-text)] font-semibold">
            {wfResult.summary}
          </div>
        </div>
      )}

      {/* Auto-assignment results */}
      {autoResult && !autoResult.error && (
        <>
          <div className="panel p-5">
            <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-2">Auto-Asignacion de Estrategias</h2>
            <div className="text-[12px] text-[var(--color-text-muted)] mb-4">
              {autoResult.total_symbols} simbolos evaluados con 4 estrategias cada uno ({autoResult.total_symbols * 4} backtests)
            </div>

            {/* Strategy distribution */}
            <div className="flex gap-2 mb-4 flex-wrap">
              {Object.entries(autoResult.strategy_distribution).map(([strat, count]) => (
                <div key={strat} className="rounded-[8px] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px]">
                  <span className="font-bold text-[var(--color-text)]">{strat}</span>
                  <span className="text-[var(--color-text-muted)] ml-2">({count} simbolos)</span>
                </div>
              ))}
            </div>

            {/* Assignments table */}
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="text-left pb-2">Symbol</th>
                    <th className="text-left pb-2">Mejor Estrategia</th>
                    <th className="text-right pb-2">Sharpe</th>
                    <th className="text-right pb-2">Retorno %</th>
                    <th className="text-right pb-2">Alpha %</th>
                    <th className="text-right pb-2">Win Rate</th>
                    <th className="text-right pb-2">Max DD %</th>
                  </tr>
                </thead>
                <tbody>
                  {autoResult.assignments.map((a) => (
                    <tr key={a.symbol} className="border-b border-[var(--color-border)]/30">
                      <td className="py-2 font-bold text-[var(--color-text)]">{a.symbol}</td>
                      <td className="py-2">
                        <span className={cn(
                          "px-2 py-0.5 rounded-[4px] text-[10px] font-bold",
                          a.best_strategy === "trend_momentum" && "bg-[var(--color-primary)]/20 text-[var(--color-primary)]",
                          a.best_strategy === "mean_reversion" && "bg-[var(--color-warning)]/20 text-[var(--color-warning)]",
                          a.best_strategy === "breakout" && "bg-[var(--color-success)]/20 text-[var(--color-success)]",
                          a.best_strategy === "grid" && "bg-purple-500/20 text-purple-400",
                        )}>
                          {a.best_strategy}
                        </span>
                      </td>
                      <td className={cn("text-right py-2 font-bold", a.best_sharpe >= 1 ? "text-[var(--color-success)]" : a.best_sharpe < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text)]")}>
                        {a.best_sharpe.toFixed(2)}
                      </td>
                      <td className={cn("text-right py-2 font-bold", a.best_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {a.best_return_pct > 0 ? "+" : ""}{a.best_return_pct.toFixed(2)}%
                      </td>
                      <td className={cn("text-right py-2 font-bold", a.best_alpha_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                        {a.best_alpha_pct > 0 ? "+" : ""}{a.best_alpha_pct.toFixed(2)}%
                      </td>
                      <td className="text-right py-2 text-[var(--color-text-muted)]">{a.best_win_rate.toFixed(1)}%</td>
                      <td className="text-right py-2 text-[var(--color-danger)]">{a.best_max_drawdown.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detail: all strategies per symbol */}
          <div className="panel p-5">
            <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-3">Detalle por simbolo</h3>
            <div className="space-y-3">
              {autoResult.assignments.map((a) => (
                <div key={a.symbol}>
                  <div className="text-[12px] font-bold text-[var(--color-text)] mb-1">{a.symbol}</div>
                  <div className="grid grid-cols-4 gap-2">
                    {a.all_results.map((r) => (
                      <div
                        key={r.strategy}
                        className={cn(
                          "rounded-[6px] p-2 text-[10px]",
                          r.strategy === a.best_strategy
                            ? "bg-[var(--color-success)]/10 border border-[var(--color-success)]/30"
                            : "bg-[var(--color-surface-2)]"
                        )}
                      >
                        <div className="font-bold text-[var(--color-text)]">{r.strategy}</div>
                        <div className="text-[var(--color-text-muted)] mt-1">
                          Sharpe: {r.sharpe.toFixed(2)} | Ret: {r.total_return_pct > 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
                        </div>
                        <div className="text-[var(--color-text-muted)]">
                          Alpha: {r.alpha_pct > 0 ? "+" : ""}{r.alpha_pct.toFixed(1)}% | Trades: {r.total_trades}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Historical Data Cache panel */}
      <div className="panel p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[14px] font-extrabold text-[var(--color-text)]">Datos Históricos (Cache)</h2>
          <button
            onClick={() => setShowHistorical(!showHistorical)}
            className="text-[11px] font-bold text-[var(--color-primary)] hover:underline"
          >
            {showHistorical ? "Ocultar" : "Mostrar"}
          </button>
        </div>
        <p className="text-[11px] text-[var(--color-text-muted)] mb-3">
          Descarga datos históricos de Binance y los cachea en la BD. Permite backtests con años de historia (sin límite de 1000 velas).
        </p>
        {showHistorical && <HistoricalDataPanel symbol={symbol} interval={interval} />}
      </div>
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

// ---------------------------------------------------------------------------
// Historical Data Panel — download & cache klines for extended backtests
// ---------------------------------------------------------------------------

function HistoricalDataPanel({ symbol, interval }: { symbol: string; interval: string }) {
  const [cacheStatus, setCacheStatus] = useState<any>(null);
  const [fetching, setFetching] = useState(false);
  const [fetchResult, setFetchResult] = useState<any>(null);
  const [days, setDays] = useState("365");

  const loadStatus = async () => {
    try {
      const r = await api<any>("/api/trading/historical-data/status");
      setCacheStatus(r);
    } catch {}
  };

  useEffect(() => { loadStatus(); }, []);

  const handleFetch = async () => {
    setFetching(true);
    setFetchResult(null);
    try {
      const r = await api<any>("/api/trading/historical-data/fetch", {
        method: "POST",
        body: JSON.stringify({ symbol, timeframe: interval, days: parseInt(days) }),
      });
      setFetchResult(r);
      await loadStatus();
    } catch (e: any) {
      setFetchResult({ status: "error", error: e.message });
    }
    setFetching(false);
  };

  const handleClear = async () => {
    try {
      await api<any>(`/api/trading/historical-data/${symbol}`, { method: "DELETE" });
      await loadStatus();
    } catch {}
  };

  const symbolCache = cacheStatus?.cached?.find((c: any) => c.symbol === symbol && c.timeframe === interval);

  return (
    <div className="space-y-3">
      {/* Current cache status */}
      <div className="rounded-[10px] bg-[var(--color-surface-2)] p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[12px] font-bold text-[var(--color-text)]">Cache actual: {symbol} {interval}</span>
          {symbolCache && (
            <span className="text-[10px] text-[var(--color-success)] font-bold">
              {symbolCache.count} velas
            </span>
          )}
        </div>
        {symbolCache ? (
          <div className="text-[10px] text-[var(--color-text-muted)]">
            Desde {fmtDate(symbolCache.earliest)} hasta {fmtDate(symbolCache.latest)}
          </div>
        ) : (
          <div className="text-[10px] text-[var(--color-text-muted)]">Sin datos cacheados</div>
        )}
      </div>

      {/* Fetch controls */}
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Días</label>
          <select
            value={days}
            onChange={(e) => setDays(e.target.value)}
            className="w-full h-8 px-2 rounded-[6px] bg-[var(--color-surface-2)] text-[12px] text-[var(--color-text)] border-none outline-none"
          >
            <option value="30">30 días</option>
            <option value="90">90 días</option>
            <option value="365">1 año</option>
            <option value="730">2 años</option>
            <option value="1095">3 años</option>
          </select>
        </div>
        <button
          onClick={handleFetch}
          disabled={fetching}
          className="h-8 px-4 rounded-[6px] bg-[var(--color-primary)] text-white text-[12px] font-bold disabled:opacity-50"
        >
          {fetching ? "Descargando..." : "Descargar"}
        </button>
        {symbolCache && (
          <button
            onClick={handleClear}
            className="h-8 px-3 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-[12px] font-bold"
          >
            Limpiar
          </button>
        )}
      </div>

      {/* Fetch result */}
      {fetchResult && (
        <div className={cn(
          "rounded-[8px] p-3 text-[12px]",
          fetchResult.status === "ok"
            ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
            : "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
        )}>
          {fetchResult.status === "ok"
            ? `Descargadas ${fetchResult.downloaded} velas (${fetchResult.cached} en cache, ${fetchResult.gaps} gaps)`
            : `Error: ${fetchResult.error}`}
        </div>
      )}

      {/* All cached symbols */}
      {cacheStatus?.cached?.length > 0 && (
        <div>
          <p className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-2">Todo lo cacheado ({cacheStatus.total_entries} velas)</p>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {cacheStatus.cached.map((c: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-[10px] py-1 px-2 rounded bg-[var(--color-surface-2)]">
                <span className="font-bold text-[var(--color-text)]">{c.symbol} {c.timeframe}</span>
                <span className="text-[var(--color-text-muted)]">{c.count} velas</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
