import { useEffect, useState, useCallback } from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip, ReferenceLine } from "recharts";
import { X, Check, TrendingUp, TrendingDown, Clock, BarChart3 } from "lucide-react";
import { cn } from "../../lib/utils";
import { api, cacheInvalidate } from "../../lib/api";
import { CryptoIcon } from "../CryptoIcon";
import { toast } from "../ui/Toast";

interface ReportItem {
  id: string;
  date: string;
  type: string;
  asset: string;
  summary: string;
  sections: {
    marketOverview: string;
    keyEvents: string;
    performance: string;
    outlook: string;
    detailedAnalysis?: string;
  };
  action_type?: string;
  confidence?: number;
  status?: string;
  trading_mode?: string | null;
  broker_name?: string | null;
  metadata?: Record<string, any>;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  reason?: string | null;
}

interface MarketPreviewModalProps {
  report: ReportItem;
  onClose: () => void;
  onAction: () => void;
}

interface Ticker24h {
  lastPrice: string;
  priceChangePercent: string;
  highPrice: string;
  lowPrice: string;
  volume: string;
  quoteVolume: string;
}

interface KlinePoint {
  time: number;
  price: number;
  label: string;
}

export function MarketPreviewModal({ report, onClose, onAction }: MarketPreviewModalProps) {
  const [ticker, setTicker] = useState<Ticker24h | null>(null);
  const [klines, setKlines] = useState<KlinePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const isPositionAnalysis = report.action_type === "position_analysis";
  const meta = report.metadata || {};
  const symbol = isPositionAnalysis
    ? (meta.symbol as string) || `${report.asset}USDT`
    : `${report.asset}USDT`;

  const loadMarketData = useCallback(async () => {
    setLoading(true);
    try {
      const [t, k] = await Promise.all([
        fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${symbol}`).then((r) => r.json()),
        fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=1h&limit=24`).then((r) => r.json()),
      ]);
      setTicker(t);
      const parsed: KlinePoint[] = (k as any[]).map((candle: any) => {
        const ts = candle[0] as number;
        const d = new Date(ts);
        const hh = d.getHours().toString().padStart(2, "0");
        const mm = d.getMinutes().toString().padStart(2, "0");
        return {
          time: ts,
          price: parseFloat(candle[4]),
          label: `${hh}:${mm}`,
        };
      });
      setKlines(parsed);
    } catch {
      // ignore
    }
    setLoading(false);
  }, [symbol]);

  useEffect(() => {
    loadMarketData();
  }, [loadMarketData]);

  const currentPrice = ticker ? parseFloat(ticker.lastPrice) : null;
  const change24h = ticker ? parseFloat(ticker.priceChangePercent) : null;

  // Calculate SL/TP
  const slPrice = isPositionAnalysis
    ? meta.suggested_sl
    : currentPrice != null && report.stop_loss_pct != null
      ? currentPrice * (1 - report.stop_loss_pct / 100)
      : null;
  const tpPrice = isPositionAnalysis
    ? meta.suggested_tp
    : currentPrice != null && report.take_profit_pct != null
      ? currentPrice * (1 + report.take_profit_pct / 100)
      : null;

  const slPct = isPositionAnalysis && currentPrice != null && slPrice != null
    ? ((currentPrice - slPrice) / currentPrice * 100)
    : report.stop_loss_pct;
  const tpPct = isPositionAnalysis && currentPrice != null && tpPrice != null
    ? ((tpPrice - currentPrice) / currentPrice * 100)
    : report.take_profit_pct;

  const timeHorizon = meta.time_horizon || "";
  const reason = report.reason || report.sections?.outlook || "";
  const detailedAnalysis = meta.detailed_analysis || "";
  const confidence = report.confidence != null ? Math.round(report.confidence * 100) : null;

  const isPositive = change24h != null && change24h >= 0;

  const handleAccept = async () => {
    const recId = parseInt(report.id.replace("rec-", ""));
    setActionLoading(true);
    try {
      const res = await api<any>(`/api/intelligence/reports/${recId}/accept`, { method: "POST" });
      cacheInvalidate("/api/positions");
      cacheInvalidate("/api/intelligence/paper-positions");
      if (res?.status === "applied") {
        toast(`SL/TP actualizado para posición #${res.position_id}${res.broker_updated ? " (broker actualizado)" : ""}`, true);
      } else if (res?.status === "executed") {
        toast("Paper trade creado. Míralo en Posiciones → Paper", true);
      } else {
        toast(res?.reason || "Error al aceptar recomendación", false);
      }
      onAction();
      onClose();
    } catch (err) {
      console.error("Accept failed:", err);
      toast("Error al aceptar recomendación", false);
    }
    setActionLoading(false);
  };

  const handleDecline = async () => {
    const recId = parseInt(report.id.replace("rec-", ""));
    setActionLoading(true);
    try {
      await api(`/api/intelligence/reports/${recId}/decline`, { method: "POST" });
      onAction();
      onClose();
    } catch (err) {
      console.error("Decline failed:", err);
      toast("Error al declinar recomendación", false);
    }
    setActionLoading(false);
  };

  const fmtPrice = (v: number | null | undefined): string => {
    if (v == null) return "N/A";
    if (v >= 1000) return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return `$${v.toFixed(6)}`;
  };

  const chartTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;
    const point = payload[0].payload as KlinePoint;
    return (
      <div className="rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border-strong)] px-2.5 py-1.5 shadow-lg">
        <div className="text-[10px] font-bold text-[var(--color-text-muted)]">{point.label}</div>
        <div className="text-[12px] font-bold text-[var(--color-text)] mt-0.5">{fmtPrice(point.price)}</div>
      </div>
    );
  };

  const yDomain = (() => {
    if (!klines.length) return ["dataMin", "dataMax"] as [string, string];
    const prices = klines.map((k) => k.price);
    let lo = Math.min(...prices);
    let hi = Math.max(...prices);
    if (slPrice != null) lo = Math.min(lo, slPrice);
    if (tpPrice != null) hi = Math.max(hi, tpPrice);
    if (currentPrice != null) { lo = Math.min(lo, currentPrice); hi = Math.max(hi, currentPrice); }
    const pad = (hi - lo) * 0.08 || hi * 0.01;
    return [lo - pad, hi + pad] as [number, number];
  })();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-[480px] max-w-[90vw] max-h-[90vh] overflow-y-auto panel p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <CryptoIcon symbol={symbol} size={28} />
            <div>
              <div className="text-[15px] font-extrabold text-[var(--color-text)]">{symbol}</div>
              <div className="flex items-center gap-2 mt-0.5">
                {currentPrice != null && (
                  <span className="text-[14px] font-bold text-[var(--color-text)]">{fmtPrice(currentPrice)}</span>
                )}
                {change24h != null && (
                  <span
                    className={cn(
                      "text-[11px] font-bold flex items-center gap-0.5",
                      isPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                    )}
                  >
                    {isPositive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                    {isPositive ? "+" : ""}{change24h.toFixed(2)}%
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Sparkline */}
        <div className="h-[160px] w-full rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2">
          {loading ? (
            <div className="h-full flex items-center justify-center text-[11px] text-[var(--color-text-muted)]">
              Cargando gráfico...
            </div>
          ) : klines.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={klines} margin={{ top: 8, right: 8, bottom: 2, left: 8 }}>
                <defs>
                  <linearGradient id="sparkGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={isPositive ? "var(--color-success)" : "var(--color-danger)"} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={isPositive ? "var(--color-success)" : "var(--color-danger)"} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="label" hide />
                <YAxis domain={yDomain} hide />
                <Tooltip content={chartTooltip} cursor={{ stroke: "var(--color-border-strong)", strokeWidth: 1 }} />
                {slPrice != null && (
                  <ReferenceLine y={slPrice} stroke="#ef4444" strokeDasharray="4 3" strokeWidth={1} label={{ value: "SL", fill: "#ef4444", fontSize: 9, fontWeight: 700, position: "right" }} />
                )}
                {currentPrice != null && (
                  <ReferenceLine y={currentPrice} stroke="var(--color-text-muted)" strokeDasharray="2 2" strokeWidth={1} label={{ value: "NOW", fill: "var(--color-text-muted)", fontSize: 9, fontWeight: 700, position: "right" }} />
                )}
                {tpPrice != null && (
                  <ReferenceLine y={tpPrice} stroke="#22c55e" strokeDasharray="4 3" strokeWidth={1} label={{ value: "TP", fill: "#22c55e", fontSize: 9, fontWeight: 700, position: "right" }} />
                )}
                <Area
                  type="monotone"
                  dataKey="price"
                  stroke={isPositive ? "var(--color-success)" : "var(--color-danger)"}
                  strokeWidth={1.5}
                  fill="url(#sparkGradient)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-[11px] text-[var(--color-text-muted)]">
              Sin datos de gráfico
            </div>
          )}
        </div>

        {/* Price cards */}
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-[8px] p-2.5 bg-[var(--color-surface-2)] border border-[var(--color-border)]">
            <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">Current</div>
            <div className="text-[13px] font-bold text-[var(--color-text)] mt-1">{fmtPrice(currentPrice)}</div>
          </div>
          <div className="rounded-[8px] p-2.5 bg-red-500/5 border border-red-500/20">
            <div className="text-[9px] font-bold text-red-400 uppercase tracking-wide">Stop Loss</div>
            <div className="text-[13px] font-bold text-red-400 mt-1">{fmtPrice(slPrice)}</div>
            {slPct != null && (
              <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">-{Math.abs(slPct).toFixed(1)}%</div>
            )}
          </div>
          <div className="rounded-[8px] p-2.5 bg-green-500/5 border border-green-500/20">
            <div className="text-[9px] font-bold text-green-400 uppercase tracking-wide">Take Profit</div>
            <div className="text-[13px] font-bold text-green-400 mt-1">{fmtPrice(tpPrice)}</div>
            {tpPct != null && (
              <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">+{Math.abs(tpPct).toFixed(1)}%</div>
            )}
          </div>
        </div>

        {/* Info row */}
        <div className="flex items-center gap-3 flex-wrap">
          {confidence != null && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-[6px] bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/20">
              <BarChart3 size={12} className="text-[var(--color-primary)]" />
              <span className="text-[11px] font-bold text-[var(--color-primary)]">{confidence}% confianza</span>
            </div>
          )}
          {timeHorizon && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)]">
              <Clock size={12} className="text-[var(--color-text-muted)]" />
              <span className="text-[11px] font-bold text-[var(--color-text-muted)]">{timeHorizon}</span>
            </div>
          )}
          {report.trading_mode && (
            <div className={cn(
              "px-2 py-1 rounded-[6px] text-[10px] font-bold border",
              report.trading_mode === "live"
                ? "bg-green-500/10 text-green-400 border-green-500/20"
                : "bg-blue-500/10 text-blue-400 border-blue-500/20"
            )}>
              {report.trading_mode === "live" ? "🔴 LIVE" : "📊 PAPER"}
            </div>
          )}
        </div>

        {/* Reason */}
        {reason && (
          <div>
            <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide mb-1">
              Razón de la IA
            </div>
            <p className="text-[12px] text-[var(--color-text)] leading-relaxed">{reason}</p>
          </div>
        )}

        {/* Detailed analysis (position_analysis only) */}
        {detailedAnalysis && (
          <div>
            <div className="text-[10px] font-bold text-cyan-400 uppercase tracking-wide mb-1">
              Análisis Detallado
            </div>
            <p className="text-[12px] text-[var(--color-text)] leading-relaxed whitespace-pre-wrap">{detailedAnalysis}</p>
          </div>
        )}

        {/* Action buttons */}
        {report.id?.startsWith("rec-") && report.status === "pending" && (
          <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
            <button
              className="flex-1 h-9 rounded-[8px] text-[12px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
              disabled={actionLoading}
              onClick={handleAccept}
            >
              <Check size={14} />
              {actionLoading ? "Procesando..." : isPositionAnalysis ? "Aceptar ajustes" : "Aceptar y ejecutar"}
            </button>
            <button
              className="flex-1 h-9 rounded-[8px] text-[12px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
              disabled={actionLoading}
              onClick={handleDecline}
            >
              <X size={14} className="inline mr-1" />
              Declinar
            </button>
          </div>
        )}

        {/* Status for already acted */}
        {report.status === "executed" && (
          <div className="text-[11px] text-[var(--color-success)] font-bold pt-1 text-center">
            ✓ Recomendación aceptada y ejecutada
          </div>
        )}
        {report.status === "dismissed" && (
          <div className="text-[11px] text-[var(--color-text-muted)] pt-1 text-center">
            ✕ Recomendación declinada
          </div>
        )}
      </div>
    </div>
  );
}
