import { useEffect, useState, useMemo, useCallback } from "react";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { api, cacheInvalidate } from "../lib/api";
import { CryptoIcon } from "../components/CryptoIcon";
import { cn } from "../lib/utils";
import { toast } from "../components/ui/Toast";
import * as binanceProxy from "../lib/binanceProxy";
import type { IntelligenceReport } from "../lib/intelligenceTypes";
import { MarketPreviewModal } from "../components/reports/MarketPreviewModal";

const ASSETS = ["ALL", "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"];

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

interface ReportItem extends IntelligenceReport {
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

export function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [asset, setAsset] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState<"all" | "daily" | "weekly" | "monthly" | "position_analysis">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [sltpModalRecId, setSltpModalRecId] = useState<number | null>(null);
  const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const endpoint = asset === "ALL" ? "/api/intelligence/reports/all" : `/api/intelligence/reports/${asset}`;
      const r = await api<ReportItem[]>(endpoint);
      setReports(r || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [asset]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const handleAccept = async (e: React.MouseEvent, recId: number) => {
    e.stopPropagation();
    const id = `rec-${recId}`;
    setActionLoading(id);
    try {
      const res = await api<any>(`/api/intelligence/reports/${recId}/accept`, { method: "POST" });
      await load();
      // Invalidate positions cache so BrokerPage shows updated SL/TP
      cacheInvalidate("/api/positions");
      cacheInvalidate("/api/intelligence/paper-positions");
      if (res?.status === "applied") {
        toast(`SL/TP actualizado para posición #${res.position_id}${res.broker_updated ? " (broker actualizado)" : ""}`, true);
      } else {
        toast("Paper trade creado. Míralo en Posiciones → Paper", true);
      }
    } catch (err) {
      console.error("Accept failed:", err);
      toast("Error al aceptar recomendación", false);
    }
    setActionLoading(null);
  };

  const handleApplyOco = async (recId: number) => {
    setActionLoading(`rec-${recId}`);
    setSltpModalRecId(null);
    try {
      // Step 1: Get SL/TP and position data from backend
      const res = await api<any>(`/api/intelligence/reports/${recId}/apply-oco`, { method: "POST" });
      if (res?.status !== "ready") {
        toast(res?.error || res?.reason || "Error al obtener datos del OCO", false);
        setActionLoading(null);
        return;
      }

      const { position_id, symbol, quantity, stop_loss, take_profit, is_futures, side } = res;
      const brokerSymbol = symbol.toUpperCase().replace(/[-_/]/g, "");
      const closeSide = side === "short" ? "BUY" : "SELL";

      // Step 2: Fetch exchange info for LOT_SIZE and PRICE filters
      let stepSize = "0.00000001";
      let tickSize = "0.00000001";
      let minQty = "0";
      let minNotional = "0";
      const exInfoUrl = is_futures
        ? `https://fapi.binance.com/fapi/v1/exchangeInfo?symbol=${brokerSymbol}`
        : `https://api.binance.com/api/v3/exchangeInfo?symbol=${brokerSymbol}`;
      try {
        let exInfo: any = null;
        try {
          exInfo = is_futures
            ? await binanceProxy.getFuturesExchangeInfo(brokerSymbol)
            : await binanceProxy.getExchangeInfo(brokerSymbol);
        } catch {
          // Fallback: direct from Binance (public endpoint)
          const directResp = await fetch(exInfoUrl);
          if (directResp.ok) exInfo = await directResp.json();
        }
        const filters = exInfo?.symbols?.[0]?.filters || [];
        for (const f of filters) {
          if (f.filterType === "LOT_SIZE") {
            stepSize = f.stepSize || stepSize;
            minQty = f.minQty || minQty;
          } else if (f.filterType === "PRICE_FILTER") {
            tickSize = f.tickSize || tickSize;
          } else if (f.filterType === "MIN_NOTIONAL" || f.filterType === "NOTIONAL") {
            minNotional = f.minNotional || f.notional || minNotional;
          }
        }
      } catch {}

      // Helper: round to step size
      const roundToStep = (value: number, step: string): string => {
        const stepNum = parseFloat(step);
        if (stepNum <= 0 || isNaN(stepNum)) return String(value);
        const stepStr = step.replace(/0+$/, "").replace(/\.$/, "");
        const decimals = (stepStr.split(".")[1] || "").length;
        const quotient = Math.floor(value / stepNum);
        const rounded = quotient * stepNum;
        let result = rounded.toFixed(Math.max(decimals, 0));
        result = result.replace(/0+$/, "").replace(/\.$/, "");
        if (result === "" || result === "-0" || parseFloat(result) === 0) return "0";
        return result;
      };

      let formattedQty = roundToStep(quantity, stepSize);
      const formattedTp = roundToStep(take_profit, tickSize);
      const formattedSl = roundToStep(stop_loss, tickSize);

      // If rounding to step makes qty 0 but original qty > 0, use original qty
      if (parseFloat(formattedQty) === 0 && quantity > 0) {
        formattedQty = String(quantity);
      }

      // Validate quantity
      const qtyNum = parseFloat(formattedQty);
      const minQtyNum = parseFloat(minQty);
      if (qtyNum <= 0) {
        toast(`Cantidad inválida (${formattedQty}) para ${symbol}.`, false);
        setActionLoading(null);
        return;
      }
      if (minQtyNum > 0 && qtyNum < minQtyNum) {
        const marketLabel = is_futures ? "Futuros" : "Spot";
        const suggestion = is_futures
          ? "Verifica la cantidad de tu posición en futuros."
          : `Binance Spot requiere mínimo ${minQty} ${symbol.replace("USDT", "")}. Tienes ${formattedQty}. Considera comprar más o mover la posición a Futuros (mínimo 0.001).`;
        toast(`Cantidad insuficiente para ${marketLabel}: ${formattedQty} < mínimo ${minQty}. ${suggestion}`, false);
        setActionLoading(null);
        return;
      }
      const minNotionalNum = parseFloat(minNotional);
      if (minNotionalNum > 0 && qtyNum * take_profit < minNotionalNum) {
        toast(`Valor de la orden (${(qtyNum * take_profit).toFixed(2)} USDT) menor al mínimo de Binance (${minNotional} USDT).`, false);
        setActionLoading(null);
        return;
      }

      let orderIds: string[] = [];

      if (is_futures) {
        // Futures: cancel existing orders, then place STOP_MARKET + TAKE_PROFIT_MARKET
        try {
          const openOrders = await binanceProxy.getFuturesOpenOrders(brokerSymbol);
          for (const o of openOrders) {
            const otype = o.type || "";
            if (["STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"].includes(otype)) {
              try { await binanceProxy.cancelFuturesOrder(brokerSymbol, String(o.orderId)); } catch {}
            }
          }
        } catch {}

        // Place TAKE_PROFIT_MARKET
        const tpResp = await binanceProxy.placeFuturesOrder({
          symbol: brokerSymbol,
          side: closeSide,
          type: "TAKE_PROFIT_MARKET",
          stopPrice: formattedTp,
          quantity: formattedQty,
          reduceOnly: true,
          workingType: "MARK_PRICE",
        });
        orderIds.push(String(tpResp.orderId));

        // Place STOP_MARKET
        const slResp = await binanceProxy.placeFuturesOrder({
          symbol: brokerSymbol,
          side: closeSide,
          type: "STOP_MARKET",
          stopPrice: formattedSl,
          quantity: formattedQty,
          reduceOnly: true,
          workingType: "MARK_PRICE",
        });
        orderIds.push(String(slResp.orderId));
      } else {
        // Spot: cancel existing orders, then place OCO
        try {
          const openOrders = await binanceProxy.getOpenOrders(brokerSymbol);
          for (const o of openOrders) {
            const otype = o.type || "";
            if (["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT", "STOP_MARKET", "TAKE_PROFIT_MARKET"].includes(otype)) {
              try { await binanceProxy.cancelOrder(brokerSymbol, String(o.orderId)); } catch {}
            }
          }
        } catch {}

        const ocoResp = await binanceProxy.placeOCO({
          symbol: brokerSymbol,
          side: closeSide,
          quantity: formattedQty,
          price: formattedTp,
          stopPrice: formattedSl,
          stopLimitPrice: formattedSl,
          stopLimitTimeInForce: "GTC",
        });
        orderIds.push(String(ocoResp.orderListId));
      }

      // Step 5: Confirm in DB via backend
      const confirmRes = await api<any>(`/api/intelligence/positions/${position_id}/update-oco`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ oco_order_id: orderIds.join(","), stop_loss, take_profit }),
      });

      // Step 6: Mark recommendation as executed
      try {
        await api(`/api/intelligence/reports/${recId}/accept`, { method: "POST" });
      } catch {}

      await load();
      cacheInvalidate("/api/positions");

      const label = is_futures ? "Futuros SL/TP" : "OCO Spot";
      if (confirmRes?.status === "placed" || confirmRes?.status === "ok") {
        toast(`${label} colocado en Binance para ${symbol} (IDs: ${orderIds.join(", ")})`, true);
      } else {
        toast(`${label} colocado pero error al actualizar DB: ${confirmRes?.error || "desconocido"}`, false);
      }
    } catch (err: any) {
      const msg = err?.message || err?.error || JSON.stringify(err);
      toast(`Error al colocar OCO: ${msg}`, false);
      console.error("ReportsPage OCO error:", err);
    }
    setActionLoading(null);
  };

  const handleMonitorOnly = async (recId: number) => {
    setActionLoading(`rec-${recId}`);
    setSltpModalRecId(null);
    try {
      const res = await api<any>(`/api/intelligence/reports/${recId}/monitor-only`, { method: "POST" });
      await load();
      cacheInvalidate("/api/positions");
      if (res?.status === "monitoring") {
        toast(`Monitoreo activado para posición #${res.position_id}`, true);
      } else {
        toast(res?.reason || "Error al activar monitoreo", false);
      }
    } catch (err) {
      toast("Error al activar monitoreo", false);
    }
    setActionLoading(null);
  };

  const handleDecline = async (e: React.MouseEvent, recId: number) => {
    e.stopPropagation();
    const id = `rec-${recId}`;
    setActionLoading(id);
    try {
      await api(`/api/intelligence/reports/${recId}/decline`, { method: "POST" });
      await load();
    } catch (err) {
      console.error("Decline failed:", err);
    }
    setActionLoading(null);
  };

  const filtered = useMemo(() => {
    if (typeFilter === "position_analysis") return reports.filter((r) => r.action_type === "position_analysis");
    if (typeFilter === "all") return reports;
    return reports.filter((r) => r.type === typeFilter && r.action_type !== "position_analysis");
  }, [reports, typeFilter]);

  const typeBtn = (active: boolean) =>
    cn("px-2.5 h-7 rounded-[6px] text-[11px] font-bold transition-colors", active ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]");

  const actionBadge = (action?: string) => {
    if (!action) return null;
    if (action === "BUY") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/20 text-green-400 border border-green-500/40">▲ COMPRA</span>;
    if (action === "SELL") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500/20 text-red-400 border border-red-500/40">▼ VENTA</span>;
    return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gray-500/20 text-gray-400 border border-gray-500/40">— HOLD</span>;
  };

  const statusBadge = (status?: string) => {
    if (!status || status === "pending") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-yellow-500/20 text-yellow-400 border border-yellow-500/40">⏳ PENDIENTE</span>;
    if (status === "executed") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/20 text-green-400 border border-green-500/40">✓ EJECUTADA</span>;
    if (status === "dismissed") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-gray-500/20 text-gray-400 border border-gray-500/40">✕ DESCARTADA</span>;
    if (status === "expired") return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/40">⏱ EXPIRADA</span>;
    return null;
  };

  const modeBadge = (mode?: string | null, broker?: string | null) => {
    if (!mode) return null;
    if (mode === "paper") return <span className="px-2 py-0.5 rounded-[4px] text-[9px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/40">📊 PAPER</span>;
    if (mode === "live") return <span className="px-2 py-0.5 rounded-[4px] text-[9px] font-bold bg-green-500/20 text-green-400 border border-green-500/40">🔴 {broker?.toUpperCase() || "LIVE"}</span>;
    return null;
  };

  const cardStyle = (mode?: string | null, actionType?: string) => {
    if (actionType === "position_analysis") return "bg-cyan-500/5 border-cyan-500/30 border-l-[4px] border-l-cyan-500";
    if (mode === "paper") return "bg-blue-500/5 border-blue-500/30 border-l-[4px] border-l-blue-500";
    if (mode === "live") return "bg-green-500/5 border-green-500/30 border-l-[4px] border-l-green-500";
    return "bg-[var(--color-surface)] border-[var(--color-border)]";
  };

  return (
    <div className="p-5 max-w-[800px] mx-auto space-y-4">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Reportes & Recomendaciones</h2>

      {/* Asset selector */}
      <div className="flex gap-1.5 flex-wrap">
        {ASSETS.map((a) => (
          <button
            key={a}
            onClick={() => setAsset(a)}
            className={cn(
              "px-2.5 h-8 rounded-[8px] text-[12px] font-bold transition-colors flex items-center gap-1.5",
              asset === a ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            )}
          >
            <CryptoIcon symbol={a + "USDT"} size={16} />
            {a}
          </button>
        ))}
      </div>

      {/* Type filter */}
      <div className="flex gap-1">
        <button className={typeBtn(typeFilter === "all")} onClick={() => setTypeFilter("all")}>Todos</button>
        <button className={typeBtn(typeFilter === "daily")} onClick={() => setTypeFilter("daily")}>Diarios</button>
        <button className={typeBtn(typeFilter === "weekly")} onClick={() => setTypeFilter("weekly")}>Semanales</button>
        <button className={typeBtn(typeFilter === "monthly")} onClick={() => setTypeFilter("monthly")}>Mensuales</button>
        <button className={typeBtn(typeFilter === "position_analysis")} onClick={() => setTypeFilter("position_analysis")}>Análisis de Posiciones</button>
      </div>

      <div className="text-[11px] text-[var(--color-text-muted)]">
        {filtered.length} reportes{asset !== "ALL" ? ` para ${asset}` : ""}
      </div>

      {loading ? (
        <LoadingSkeleton lines={4} />
      ) : filtered.length === 0 ? (
        <div className="text-center py-8 text-[12px] text-[var(--color-text-muted)]">
          No hay reportes disponibles{asset !== "ALL" ? ` para ${asset}` : ""}.
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((r) => {
            const isExpanded = expandedId === r.id;
            return (
              <div
                key={r.id}
                className={cn(
                  "rounded-[10px] border p-3 cursor-pointer transition-colors",
                  cardStyle(r.trading_mode, r.action_type),
                  r.action_type === "position_analysis" ? "hover:border-cyan-500/50" : r.trading_mode === "paper" ? "hover:border-blue-500/50" : r.trading_mode === "live" ? "hover:border-green-500/50" : "hover:border-[var(--color-border-strong)]"
                )}
                onClick={() => setExpandedId(isExpanded ? null : r.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CryptoIcon symbol={r.asset + "USDT"} size={20} />
                    <span className="text-[13px] font-bold text-[var(--color-text)]">
                      {r.action_type === "position_analysis" ? "Análisis de Posición" : r.type === "daily" ? "Daily" : r.type === "weekly" ? "Weekly" : "Monthly"} — {r.asset}
                    </span>
                    {r.action_type === "position_analysis" ? <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">⚙ ANÁLISIS</span> : actionBadge(r.action_type)}
                    {r.confidence != null && (
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {Math.round(r.confidence * 100)}% confianza
                      </span>
                    )}
                    {modeBadge(r.trading_mode, r.broker_name)}
                  </div>
                  <div className="flex items-center gap-2">
                    {statusBadge(r.status)}
                    <span className="text-[10px] text-[var(--color-text-muted)]">{r.date}</span>
                  </div>
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{r.summary}</p>
                {isExpanded && r.sections && (
                  <div className="mt-3 space-y-2 border-t border-[var(--color-border)] pt-3">
                    {r.action_type === "position_analysis" && r.metadata && (
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <div className="bg-red-500/10 rounded-[6px] p-2 border border-red-500/20">
                          <div className="text-[9px] font-bold text-red-400 uppercase">Stop Loss</div>
                          <div className="text-[12px] text-[var(--color-text)]">
                            <span className="text-[var(--color-text-muted)] line-through">{r.metadata.current_sl ?? "N/A"}</span>
                            {" → "}
                            <span className="text-red-400 font-bold">{r.metadata.suggested_sl ?? "N/A"}</span>
                          </div>
                        </div>
                        <div className="bg-green-500/10 rounded-[6px] p-2 border border-green-500/20">
                          <div className="text-[9px] font-bold text-green-400 uppercase">Take Profit</div>
                          <div className="text-[12px] text-[var(--color-text)]">
                            <span className="text-[var(--color-text-muted)] line-through">{r.metadata.current_tp ?? "N/A"}</span>
                            {" → "}
                            <span className="text-green-400 font-bold">{r.metadata.suggested_tp ?? "N/A"}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {r.sections.marketOverview && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Market Overview</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.marketOverview}</p>
                      </div>
                    )}
                    {r.sections.keyEvents && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Ajuste SL" : "Recomendación"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.keyEvents}</p>
                      </div>
                    )}
                    {r.sections.performance && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Ajuste TP" : "Gestión de riesgo"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.performance}</p>
                      </div>
                    )}
                    {r.sections.outlook && (
                      <div>
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Razón y Horizonte" : "Razón"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.outlook}</p>
                      </div>
                    )}
                    {r.sections.detailedAnalysis && (
                      <div>
                        <span className="text-[10px] font-bold text-cyan-400 uppercase">Análisis Detallado</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5 whitespace-pre-wrap">{r.sections.detailedAnalysis}</p>
                      </div>
                    )}

                    {/* Accept / Decline buttons for pending recommendations */}
                    {r.id?.startsWith("rec-") && r.status === "pending" && r.action_type !== "position_analysis" && (
                      <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
                          disabled={actionLoading === r.id}
                          onClick={(e) => { e.stopPropagation(); setPreviewReport(r); }}
                        >
                          📊 Ver en Market
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleAccept(e, parseInt(r.id.replace("rec-", "")))}
                        >
                          {actionLoading === r.id ? "Procesando..." : "✓ Aceptar"}
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleDecline(e, parseInt(r.id.replace("rec-", "")))}
                        >
                          ✕ Declinar
                        </button>
                      </div>
                    )}

                    {/* Apply / Decline buttons for position_analysis recommendations */}
                    {r.id?.startsWith("rec-") && r.status === "pending" && r.action_type === "position_analysis" && (
                      <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
                          disabled={actionLoading === r.id}
                          onClick={(e) => { e.stopPropagation(); setPreviewReport(r); }}
                        >
                          📊 Ver en Market
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-cyan-500 text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => { e.stopPropagation(); setSltpModalRecId(parseInt(r.id.replace("rec-", ""))); }}
                        >
                          {actionLoading === r.id ? "Aplicando..." : "⚙ Aplicar SL/TP"}
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleDecline(e, parseInt(r.id.replace("rec-", "")))}
                        >
                          ✕ Ignorar
                        </button>
                      </div>
                    )}

                    {/* Status message for executed/dismissed */}
                    {r.id?.startsWith("rec-") && r.status === "executed" && r.action_type === "position_analysis" && (
                      <div className="text-[10px] text-cyan-400 font-bold pt-1">
                        ✓ Ajustes de SL/TP aplicados a la posición
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "executed" && r.action_type !== "position_analysis" && (
                      <div className="text-[10px] text-[var(--color-success)] font-bold pt-1 flex items-center gap-1">
                        ✓ Recomendación aceptada y ejecutada como paper trade
                        <span className="text-[var(--color-text-muted)]">→</span>
                        <span className="text-[var(--color-info)]">Posiciones → Paper</span>
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "dismissed" && (
                      <div className="text-[10px] text-[var(--color-text-muted)] pt-1">
                        ✕ Recomendación declinada
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "expired" && (
                      <div className="text-[10px] text-orange-400 pt-1">
                        ⏱ Recomendación expirada (sin acción en 24h)
                      </div>
                    )}
                  </div>
                )}
                {!isExpanded && (
                  <div className="text-[10px] text-[var(--color-text-muted)] mt-1">Click para expandir ▼</div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {/* SL/TP Options Modal for position_analysis reports */}
      {sltpModalRecId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setSltpModalRecId(null)}
        >
          <div
            className="w-[380px] panel p-5 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-[14px] font-bold text-[var(--color-text)]">Aplicar SL/TP</h3>
              <button
                onClick={() => setSltpModalRecId(null)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-[16px]"
              >
                ✕
              </button>
            </div>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              Elige cómo ejecutar los niveles de Stop Loss y Take Profit:
            </p>
            <div className="space-y-2">
              <button
                disabled={actionLoading === `rec-${sltpModalRecId}`}
                onClick={() => handleApplyOco(sltpModalRecId)}
                className="w-full h-10 rounded-[8px] text-[12px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {actionLoading === `rec-${sltpModalRecId}` ? "Procesando..." : "Colocar OCO en Binance"}
              </button>
              <p className="text-[10px] text-[var(--color-text-muted)] text-center -mt-1">
                Orden real: se ejecuta automáticamente cuando se alcanza SL o TP
              </p>
              <button
                disabled={actionLoading === `rec-${sltpModalRecId}`}
                onClick={() => handleMonitorOnly(sltpModalRecId)}
                className="w-full h-10 rounded-[8px] text-[12px] font-bold bg-[var(--color-info)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {actionLoading === `rec-${sltpModalRecId}` ? "Procesando..." : "Solo Monitorear"}
              </button>
              <p className="text-[10px] text-[var(--color-text-muted)] text-center -mt-1">
                Guarda SL/TP y te notifica cuando se alcancen los niveles
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Market Preview Modal */}
      {previewReport && (
        <MarketPreviewModal
          report={previewReport}
          onClose={() => setPreviewReport(null)}
          onAction={() => load()}
        />
      )}
    </div>
  );
}
