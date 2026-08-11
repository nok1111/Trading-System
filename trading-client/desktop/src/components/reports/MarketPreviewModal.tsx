import { useEffect, useState, useCallback } from "react";
import { X, Check, TrendingUp, TrendingDown, Clock, BarChart3 } from "lucide-react";
import { cn } from "../../lib/utils";
import { api, cacheInvalidate } from "../../lib/api";
import { CryptoIcon } from "../CryptoIcon";
import { toast } from "../ui/Toast";
import { useBrokerContext } from "../../context/BrokerContext";
import { isBrokerConnected } from "../../lib/brokerTypes";
import * as brokerApi from "../../lib/brokerApi";
import { PriceChart } from "../charts/PriceChart";

interface LiveData {
  usdt_balance: number | null;
  allocated_capital: number | null;
  available_capital: number | null;
  open_positions_count: number;
  max_positions: number;
  open_positions_symbols: string[];
  has_existing_position: boolean;
  estimated_quantity: number | null;
  estimated_value: number | null;
  stop_loss_price: number | null;
  take_profit_price: number | null;
  current_price: number | null;
  kill_switch_active: boolean;
}

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
  live_data?: LiveData | null;
}

interface MarketPreviewModalProps {
  report: ReportItem;
  onClose: () => void;
  onAction: () => void;
}

export function MarketPreviewModal({ report, onClose, onAction }: MarketPreviewModalProps) {
  const { connectedAccounts } = useBrokerContext();
  const [ticker, setTicker] = useState<any>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [buyLiveLoading, setBuyLiveLoading] = useState(false);

  // Editable trade parameters
  const [slPctInput, setSlPctInput] = useState<string>("");
  const [tpPctInput, setTpPctInput] = useState<string>("");
  const [amountInput, setAmountInput] = useState<string>("");

  const isPositionAnalysis = report.action_type === "position_analysis";
  const meta = report.metadata || {};
  const symbol = isPositionAnalysis
    ? (meta.symbol as string) || `${report.asset}USDT`
    : `${report.asset}USDT`;

  // Resolve broker ID from connected accounts
  const firstConnected = connectedAccounts.find((a) => isBrokerConnected(a.status));
  const brokerId = firstConnected?.brokerId || "binance";

  const loadTicker = useCallback(async () => {
    try {
      const t = await brokerApi.getTicker(brokerId, symbol).catch(() => null);
      if (t) setTicker(t);
    } catch {
      // ignore
    }
  }, [symbol, brokerId]);

  useEffect(() => {
    loadTicker();
  }, [loadTicker]);

  // Initialize editable inputs from report defaults
  useEffect(() => {
    if (report.stop_loss_pct != null) setSlPctInput(String(report.stop_loss_pct));
    else setSlPctInput("3");
    if (report.take_profit_pct != null) setTpPctInput(String(report.take_profit_pct));
    else setTpPctInput("6");
    if (report.live_data?.estimated_value != null) setAmountInput(String(Math.round(report.live_data.estimated_value)));
    else setAmountInput("");
  }, [report]);

  const currentPrice = ticker ? parseFloat(ticker.lastPrice || ticker.last_price || ticker.price || 0) : null;
  const change24h = ticker ? parseFloat(ticker.priceChangePercent || ticker.price_change_pct || 0) : null;

  // Calculate SL/TP from editable inputs
  const slPctNum = parseFloat(slPctInput) || 0;
  const tpPctNum = parseFloat(tpPctInput) || 0;
  const amountNum = parseFloat(amountInput) || 0;

  const slPrice = isPositionAnalysis
    ? meta.suggested_sl
    : currentPrice != null && slPctNum > 0
      ? currentPrice * (1 - slPctNum / 100)
      : null;
  const tpPrice = isPositionAnalysis
    ? meta.suggested_tp
    : currentPrice != null && tpPctNum > 0
      ? currentPrice * (1 + tpPctNum / 100)
      : null;

  const timeHorizon = meta.time_horizon || "";
  const reason = report.reason || report.sections?.outlook || "";
  const detailedAnalysis = meta.detailed_analysis || "";
  const confidence = report.confidence != null ? Math.round(report.confidence * 100) : null;

  const isPositive = change24h != null && change24h >= 0;

  const handleAccept = async () => {
    const recId = parseInt(report.id.replace("rec-", ""));
    setActionLoading(true);
    try {
      const endpoint = isPositionAnalysis
        ? `/api/intelligence/reports/${recId}/accept`
        : `/api/intelligence/reports/${recId}/buy-live`;
      const body: any = {};
      if (!isPositionAnalysis) {
        if (slPctNum > 0) body.sl_pct = slPctNum;
        if (tpPctNum > 0) body.tp_pct = tpPctNum;
        if (amountNum > 0) body.amount = amountNum;
      }
      const res = await api<any>(endpoint, { method: "POST", body: JSON.stringify(body) });
      cacheInvalidate("/api/positions");
      cacheInvalidate("/api/intelligence/paper-positions");
      if (res?.status === "applied") {
        toast(`SL/TP actualizado para posición #${res.position_id}${res.broker_updated ? " (broker actualizado)" : ""}`, true);
      } else if (res?.status === "executed") {
        toast(`Compra LIVE ejecutada: ${res.quantity} ${res.symbol} @ $${res.price}`, true);
      } else if (res?.status === "rejected") {
        toast(res?.reason || "Compra rechazada", false);
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

  const handleBuyLive = async () => {
    const recId = parseInt(report.id.replace("rec-", ""));
    setBuyLiveLoading(true);
    try {
      const body: any = {};
      if (slPctNum > 0) body.sl_pct = slPctNum;
      if (tpPctNum > 0) body.tp_pct = tpPctNum;
      if (amountNum > 0) body.amount = amountNum;
      const res = await api<any>(`/api/intelligence/reports/${recId}/buy-live`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      cacheInvalidate("/api/positions");
      cacheInvalidate("/api/intelligence/paper-positions");
      if (res?.status === "executed") {
        toast(`Compra LIVE ejecutada: ${res.quantity} ${res.symbol} @ $${res.price}`, true);
        onAction();
        onClose();
      } else if (res?.status === "rejected") {
        toast(res?.reason || "Compra rechazada", false);
      } else {
        toast(res?.reason || "Error en compra LIVE", false);
      }
    } catch (err) {
      console.error("Buy LIVE failed:", err);
      toast("Error al ejecutar compra LIVE", false);
    }
    setBuyLiveLoading(false);
  };

  const fmtPrice = (v: number | null | undefined): string => {
    if (v == null) return "N/A";
    if (v >= 1000) return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return `$${v.toFixed(6)}`;
  };

  // Estimated quantity from editable amount
  const estQuantity = currentPrice != null && amountNum > 0 ? amountNum / currentPrice : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-[520px] max-w-[90vw] max-h-[90vh] overflow-y-auto panel p-5 space-y-4"
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

        {/* Professional candlestick chart with indicators */}
        <PriceChart
          symbol={symbol}
          interval="1h"
          height={300}
          brokerId={brokerId}
          stopLoss={slPrice}
          takeProfit={tpPrice}
          entryPrice={isPositionAnalysis ? meta.entry_price : undefined}
        />

        {/* Price cards */}
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-[8px] p-2.5 bg-[var(--color-surface-2)] border border-[var(--color-border)]">
            <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">Current</div>
            <div className="text-[13px] font-bold text-[var(--color-text)] mt-1">{fmtPrice(currentPrice)}</div>
          </div>
          <div className="rounded-[8px] p-2.5 bg-red-500/5 border border-red-500/20">
            <div className="text-[9px] font-bold text-red-400 uppercase tracking-wide">Stop Loss</div>
            <div className="text-[13px] font-bold text-red-400 mt-1">{fmtPrice(slPrice)}</div>
            {slPctNum > 0 && (
              <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">-{slPctNum.toFixed(1)}%</div>
            )}
          </div>
          <div className="rounded-[8px] p-2.5 bg-green-500/5 border border-green-500/20">
            <div className="text-[9px] font-bold text-green-400 uppercase tracking-wide">Take Profit</div>
            <div className="text-[13px] font-bold text-green-400 mt-1">{fmtPrice(tpPrice)}</div>
            {tpPctNum > 0 && (
              <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">+{tpPctNum.toFixed(1)}%</div>
            )}
          </div>
        </div>

        {/* Editable trade parameters (only for non-position_analysis) */}
        {!isPositionAnalysis && report.status === "pending" && (
          <div className="rounded-[10px] p-3 bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-3">
            <div className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">Parámetros de Compra</div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[9px] font-bold text-red-400 uppercase">SL %</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  max="50"
                  value={slPctInput}
                  onChange={(e) => setSlPctInput(e.target.value)}
                  className="w-full h-8 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-red-400 focus:outline-none focus:border-red-500/50"
                />
              </div>
              <div>
                <label className="text-[9px] font-bold text-green-400 uppercase">TP %</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  max="100"
                  value={tpPctInput}
                  onChange={(e) => setTpPctInput(e.target.value)}
                  className="w-full h-8 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-green-400 focus:outline-none focus:border-green-500/50"
                />
              </div>
              <div>
                <label className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase">Cantidad USD</label>
                <input
                  type="number"
                  step="10"
                  min="10"
                  placeholder="Auto"
                  value={amountInput}
                  onChange={(e) => setAmountInput(e.target.value)}
                  className="w-full h-8 px-2 rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]/50"
                />
              </div>
            </div>
            {estQuantity != null && currentPrice != null && (
              <div className="text-[10px] text-[var(--color-text-muted)]">
                ≈ {estQuantity.toLocaleString("en-US", { maximumFractionDigits: 6 })} {report.asset} @ {fmtPrice(currentPrice)}
              </div>
            )}
          </div>
        )}

        {/* Live trading data: balance, risk summary */}
        {report.live_data && !isPositionAnalysis && report.status === "pending" && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-[8px] p-2.5 bg-[var(--color-surface-2)] border border-[var(--color-border)]">
                <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">Saldo USDT</div>
                <div className="text-[13px] font-bold text-[var(--color-text)] mt-1">
                  {report.live_data.usdt_balance != null ? `$${report.live_data.usdt_balance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A"}
                </div>
                <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">
                  Disponible: {report.live_data.available_capital != null ? `$${report.live_data.available_capital.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A"}
                </div>
              </div>
              <div className="rounded-[8px] p-2.5 bg-[var(--color-surface-2)] border border-[var(--color-border)]">
                <div className="text-[9px] font-bold text-[var(--color-text-muted)] uppercase tracking-wide">Posiciones abiertas</div>
                <div className="text-[13px] font-bold text-[var(--color-text)] mt-1">
                  {report.live_data.open_positions_count}
                </div>
                {report.live_data.has_existing_position && (
                  <div className="text-[9px] text-amber-400 font-bold mt-0.5">⚠ Ya tienes posición en {report.asset}</div>
                )}
              </div>
            </div>
          </div>
        )}

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
            {!isPositionAnalysis && (
              <button
                className="flex-1 h-9 rounded-[8px] text-[12px] font-bold bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
                disabled={buyLiveLoading || actionLoading}
                onClick={handleBuyLive}
              >
                {buyLiveLoading ? "Ejecutando..." : "Comprar LIVE"}
              </button>
            )}
            {isPositionAnalysis && (
              <button
                className="flex-1 h-9 rounded-[8px] text-[12px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
                disabled={actionLoading || buyLiveLoading}
                onClick={handleAccept}
              >
                <Check size={14} />
                {actionLoading ? "Procesando..." : "Aceptar ajustes"}
              </button>
            )}
            <button
              className="flex-1 h-9 rounded-[8px] text-[12px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
              disabled={actionLoading || buyLiveLoading}
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
        {report.status === "expired" && (
          <div className="text-[11px] text-[var(--color-text-muted)] pt-1 text-center">
            ⏱ Recomendación expirada (sin acción en 24h)
          </div>
        )}
      </div>
    </div>
  );
}
