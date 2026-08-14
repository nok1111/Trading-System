import { useEffect, useState, useMemo, useCallback } from "react";
import { FileText, Clock, CheckCircle, DollarSign, X } from "lucide-react";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { api, cacheInvalidate } from "../lib/api";
import { useBrokerContext } from "../context/BrokerContext";
import { isBrokerConnected } from "../lib/brokerTypes";
import { CryptoIcon } from "../components/CryptoIcon";
import { cn, fmtDate } from "../lib/utils";
import { toast } from "../components/ui/Toast";
import { SummaryBar } from "../components/ui/SummaryBar";
import * as brokerApi from "../lib/brokerApi";
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
  timestamp?: string;
}

export function ReportsPage() {
  const { connectedAccounts } = useBrokerContext();
  const firstConnectedBroker = connectedAccounts.find((a) => isBrokerConnected(a.status));
  const activeBrokerId = firstConnectedBroker?.brokerId || "paper";

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

  const handleAccept = async (e: React.MouseEvent, recId: number, actionType?: string) => {
    e.stopPropagation();
    const id = `rec-${recId}`;
    setActionLoading(id);
    try {
      // For BUY recommendations, execute a LIVE trade via /buy-live (not paper)
      // For position_analysis, use /accept which just updates SL/TP
      const endpoint = actionType === "position_analysis"
        ? `/api/intelligence/reports/${recId}/accept`
        : `/api/intelligence/reports/${recId}/buy-live`;
      const res = await api<any>(endpoint, { method: "POST" });
      await load();
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

      const { position_id, symbol, quantity, stop_loss, take_profit, side } = res;
      const closeSide = side === "short" ? "buy" : "sell";

      // Fetch market info for precision/min sizes
      let stepSize = 0;
      let minQty = 0;
      let minNotional = 0;
      try {
        const info = await brokerApi.getMarketInfo(activeBrokerId, symbol);
        if (info.step_size) stepSize = info.step_size;
        if (info.min_quantity) minQty = info.min_quantity;
        if (info.min_notional) minNotional = info.min_notional;
      } catch {}

      // Helper: round to step size
      const roundToStep = (value: number, step: number): number => {
        if (step <= 0 || isNaN(step)) return value;
        const quotient = Math.floor(value / step);
        return quotient * step;
      };

      let formattedQty = roundToStep(quantity, stepSize);
      if (formattedQty === 0 && quantity > 0) formattedQty = quantity;

      // Validate quantity
      if (formattedQty <= 0) {
        toast(`Cantidad inválida (${formattedQty}) para ${symbol}.`, false);
        setActionLoading(null);
        return;
      }
      if (minQty > 0 && formattedQty < minQty) {
        toast(`Cantidad insuficiente: ${formattedQty} < mínimo ${minQty} para ${symbol}.`, false);
        setActionLoading(null);
        return;
      }
      if (minNotional > 0 && formattedQty * take_profit < minNotional) {
        toast(`Valor de la orden (${(formattedQty * take_profit).toFixed(2)}) menor al mínimo (${minNotional}) para ${symbol}.`, false);
        setActionLoading(null);
        return;
      }

      // Place TP as a limit sell order
      const tpResp = await brokerApi.placeOrder(activeBrokerId, {
        symbol,
        side: closeSide as "buy" | "sell",
        order_type: "limit",
        quantity: formattedQty,
        price: take_profit,
      });
      // Place SL as a limit sell order
      const slResp = await brokerApi.placeOrder(activeBrokerId, {
        symbol,
        side: closeSide as "buy" | "sell",
        order_type: "limit",
        quantity: formattedQty,
        price: stop_loss,
      });

      const orderIds: string[] = [];
      if (tpResp.orderId) orderIds.push(tpResp.orderId);
      if (slResp.orderId) orderIds.push(slResp.orderId);

      if (tpResp.error || slResp.error) {
        toast(`Error: ${tpResp.error || slResp.error}`, false);
        setActionLoading(null);
        return;
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

      if (confirmRes?.status === "placed" || confirmRes?.status === "ok") {
        toast(`SL/TP colocado en ${activeBrokerId} para ${symbol} (IDs: ${orderIds.join(", ")})`, true);
      } else {
        toast(`SL/TP colocado pero error al actualizar DB: ${confirmRes?.error || "desconocido"}`, false);
      }
    } catch (err: any) {
      const msg = err?.message || err?.error || JSON.stringify(err);
      toast(`Error al colocar SL/TP: ${msg}`, false);
      console.error("ReportsPage SL/TP error:", err);
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
    if (action === "BUY") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-success)]/20 text-[var(--color-success)] border border-[var(--color-success)]/40">▲ COMPRA</span>;
    if (action === "SELL") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-danger)]/20 text-[var(--color-danger)] border border-[var(--color-danger)]/40">▼ VENTA</span>;
    return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-border)]">— HOLD</span>;
  };

  const statusBadge = (status?: string) => {
    if (!status || status === "pending") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-warning)]/20 text-[var(--color-warning)] border border-[var(--color-warning)]/40">PENDIENTE</span>;
    if (status === "executed") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-success)]/20 text-[var(--color-success)] border border-[var(--color-success)]/40">EJECUTADA</span>;
    if (status === "dismissed") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-border)]">DESCARTADA</span>;
    if (status === "expired") return <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-warning)]/20 text-[var(--color-warning)] border border-[var(--color-warning)]/40">EXPIRADA</span>;
    return null;
  };

  const modeBadge = (mode?: string | null, broker?: string | null) => {
    if (!mode) return null;
    if (mode === "paper") return <span className="px-2 py-0.5 rounded-[4px] text-[11px] font-bold bg-[var(--color-primary)]/20 text-[var(--color-primary)] border border-[var(--color-primary)]/40">PAPER</span>;
    if (mode === "live") return <span className="px-2 py-0.5 rounded-[4px] text-[11px] font-bold bg-[var(--color-success)]/20 text-[var(--color-success)] border border-[var(--color-success)]/40">{broker?.toUpperCase() || "LIVE"}</span>;
    return null;
  };

  const cardStyle = (mode?: string | null, actionType?: string) => {
    if (actionType === "position_analysis") return "bg-[var(--color-cyan)]/5 border-[var(--color-cyan)]/30 border-l-[4px] border-l-[var(--color-cyan)]";
    if (mode === "paper") return "bg-[var(--color-primary)]/5 border-[var(--color-primary)]/30 border-l-[4px] border-l-[var(--color-primary)]";
    if (mode === "live") return "bg-[var(--color-success)]/5 border-[var(--color-success)]/30 border-l-[4px] border-l-[var(--color-success)]";
    return "bg-[var(--color-surface)] border-[var(--color-border)]";
  };

  // Summary metrics
  const pendingCount = filtered.filter((r) => !r.status || r.status === "pending").length;
  const executedCount = filtered.filter((r) => r.status === "executed").length;
  const totalPnl = filtered
    .filter((r) => r.metadata?.realized_pnl)
    .reduce((sum, r) => sum + (Number(r.metadata?.realized_pnl) || 0), 0);

  // Group by date
  const grouped = useMemo(() => {
    const groups: Record<string, ReportItem[]> = {};
    filtered.forEach((r) => {
      const rawDate = r.timestamp || r.date || "";
      let dateKey: string;
      try {
        const d = new Date(rawDate);
        if (isNaN(d.getTime())) dateKey = "Sin fecha";
        else {
          const today = new Date();
          const yesterday = new Date(today);
          yesterday.setDate(yesterday.getDate() - 1);
          if (d.toDateString() === today.toDateString()) dateKey = "Hoy";
          else if (d.toDateString() === yesterday.toDateString()) dateKey = "Ayer";
          else dateKey = d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
        }
      } catch {
        dateKey = "Sin fecha";
      }
      if (!groups[dateKey]) groups[dateKey] = [];
      groups[dateKey].push(r);
    });
    return groups;
  }, [filtered]);

  return (
    <div className="p-5 max-w-[900px] mx-auto space-y-4">
      <h2 className="text-[20px] font-extrabold text-[var(--color-text)]">Reportes & Recomendaciones</h2>

      {/* Summary bar */}
      {!loading && filtered.length > 0 && (
        <SummaryBar
          items={[
            { label: "Total", value: filtered.length, icon: <FileText size={14} /> },
            { label: "Pendientes", value: pendingCount, tone: pendingCount > 0 ? "warning" : "default", icon: <Clock size={14} /> },
            { label: "Ejecutadas", value: executedCount, tone: executedCount > 0 ? "success" : "default", icon: <CheckCircle size={14} /> },
            { label: "P&L", value: `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`, tone: totalPnl >= 0 ? "success" : "danger", icon: <DollarSign size={14} /> },
          ]}
        />
      )}

      {/* Asset selector */}
      <div className="flex gap-1.5 flex-wrap">
        {ASSETS.map((a) => (
          <button
            key={a}
            onClick={() => setAsset(a)}
            className={cn(
              "px-2.5 h-8 rounded-[8px] text-[12px] font-bold transition-colors flex items-center gap-1.5 btn-press",
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
        <div className="space-y-4">
          {Object.entries(grouped).map(([date, items]) => (
            <div key={date} className="space-y-2">
              <div className="flex items-center gap-2 py-1">
                <span className="text-[11px] font-bold uppercase text-[var(--color-text-muted)] tracking-wide">{date}</span>
                <div className="flex-1 h-px bg-[var(--color-border)]" />
                <span className="text-[11px] text-[var(--color-text-muted)]">{items.length}</span>
              </div>
              {items.map((r) => {
            const isExpanded = expandedId === r.id;
            return (
              <div
                key={r.id}
                className={cn(
                  "rounded-[10px] border p-3 cursor-pointer transition-colors card-hover",
                  cardStyle(r.trading_mode, r.action_type),
                  r.action_type === "position_analysis" ? "hover:border-[var(--color-cyan)]/50" : r.trading_mode === "paper" ? "hover:border-[var(--color-primary)]/50" : r.trading_mode === "live" ? "hover:border-[var(--color-success)]/50" : "hover:border-[var(--color-border-strong)]"
                )}
                onClick={() => setExpandedId(isExpanded ? null : r.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CryptoIcon symbol={r.asset + "USDT"} size={20} />
                    <span className="text-[13px] font-bold text-[var(--color-text)]">
                      {r.action_type === "position_analysis" ? "Análisis de Posición" : r.type === "daily" ? "Daily" : r.type === "weekly" ? "Weekly" : "Monthly"} — {r.asset}
                    </span>
                    {r.action_type === "position_analysis" ? <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-[var(--color-cyan)]/20 text-[var(--color-cyan)] border border-[var(--color-cyan)]/40">ANÁLISIS</span> : actionBadge(r.action_type)}
                    {r.confidence != null && (
                      <span className="text-[11px] text-[var(--color-text-muted)]">
                        {Math.round(r.confidence * 100)}% confianza
                      </span>
                    )}
                    {modeBadge(r.trading_mode, r.broker_name)}
                  </div>
                  <div className="flex items-center gap-2">
                    {statusBadge(r.status)}
                    <span className="text-[11px] text-[var(--color-text-muted)]">{r.timestamp ? fmtDate(r.timestamp) : r.date}</span>
                  </div>
                </div>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">{r.summary}</p>
                {isExpanded && r.sections && (
                  <div className="mt-3 space-y-2 border-t border-[var(--color-border)] pt-3">
                    {r.action_type === "position_analysis" && r.metadata && (
                      <div className="grid grid-cols-2 gap-2 mb-2">
                        <div className="bg-[var(--color-danger)]/10 rounded-[6px] p-2 border border-[var(--color-danger)]/20">
                          <div className="text-[11px] font-bold text-[var(--color-danger)] uppercase">Stop Loss</div>
                          <div className="text-[12px] text-[var(--color-text)]">
                            <span className="text-[var(--color-text-muted)] line-through">{r.metadata.current_sl ?? "N/A"}</span>
                            {" → "}
                            <span className="text-[var(--color-danger)] font-bold">{r.metadata.suggested_sl ?? "N/A"}</span>
                          </div>
                        </div>
                        <div className="bg-[var(--color-success)]/10 rounded-[6px] p-2 border border-[var(--color-success)]/20">
                          <div className="text-[11px] font-bold text-[var(--color-success)] uppercase">Take Profit</div>
                          <div className="text-[12px] text-[var(--color-text)]">
                            <span className="text-[var(--color-text-muted)] line-through">{r.metadata.current_tp ?? "N/A"}</span>
                            {" → "}
                            <span className="text-[var(--color-success)] font-bold">{r.metadata.suggested_tp ?? "N/A"}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {r.sections.marketOverview && (
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Market Overview</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.marketOverview}</p>
                      </div>
                    )}
                    {r.sections.keyEvents && (
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Ajuste SL" : "Recomendación"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.keyEvents}</p>
                      </div>
                    )}
                    {r.sections.performance && (
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Ajuste TP" : "Gestión de riesgo"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.performance}</p>
                      </div>
                    )}
                    {r.sections.outlook && (
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">{r.action_type === "position_analysis" ? "Razón y Horizonte" : "Razón"}</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5">{r.sections.outlook}</p>
                      </div>
                    )}
                    {r.sections.detailedAnalysis && (
                      <div>
                        <span className="text-[11px] font-bold text-[var(--color-cyan)] uppercase">Análisis Detallado</span>
                        <p className="text-[12px] text-[var(--color-text)] mt-0.5 whitespace-pre-wrap">{r.sections.detailedAnalysis}</p>
                      </div>
                    )}

                    {/* Accept / Decline buttons for pending recommendations */}
                    {r.id?.startsWith("rec-") && r.status === "pending" && r.action_type !== "position_analysis" && (
                      <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
                          disabled={actionLoading === r.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            const sym = (r.metadata?.symbol as string) || `${r.asset}USDT`;
                            window.dispatchEvent(new CustomEvent("navigate", {
                              detail: {
                                page: "trade",
                                asset: sym,
                                broker: activeBrokerId,
                                stop_loss: r.live_data?.stop_loss_price ?? null,
                                take_profit: r.live_data?.take_profit_price ?? null,
                              },
                            }));
                          }}
                        >
                          � Ir a Trade
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-success)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleAccept(e, parseInt(r.id.replace("rec-", "")), r.action_type)}
                        >
                          {actionLoading === r.id ? "Procesando..." : "Comprar LIVE"}
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleDecline(e, parseInt(r.id.replace("rec-", "")))}
                        >
                          Declinar
                        </button>
                      </div>
                    )}

                    {/* Apply / Decline buttons for position_analysis recommendations */}
                    {r.id?.startsWith("rec-") && r.status === "pending" && r.action_type === "position_analysis" && (
                      <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-1.5"
                          disabled={actionLoading === r.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            const sym = (r.metadata?.symbol as string) || `${r.asset}USDT`;
                            window.dispatchEvent(new CustomEvent("navigate", {
                              detail: {
                                page: "trade",
                                asset: sym,
                                broker: activeBrokerId,
                                stop_loss: r.live_data?.stop_loss_price ?? null,
                                take_profit: r.live_data?.take_profit_price ?? null,
                              },
                            }));
                          }}
                        >
                          � Ir a Trade
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-cyan)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => { e.stopPropagation(); setSltpModalRecId(parseInt(r.id.replace("rec-", ""))); }}
                        >
                          {actionLoading === r.id ? "Aplicando..." : "Aplicar SL/TP"}
                        </button>
                        <button
                          className="flex-1 h-8 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors disabled:opacity-50"
                          disabled={actionLoading === r.id}
                          onClick={(e) => handleDecline(e, parseInt(r.id.replace("rec-", "")))}
                        >
                          Ignorar
                        </button>
                      </div>
                    )}

                    {/* Status message for executed/dismissed */}
                    {r.id?.startsWith("rec-") && r.status === "executed" && r.action_type === "position_analysis" && (
                      <div className="text-[11px] text-[var(--color-cyan)] font-bold pt-1">
                        Ajustes de SL/TP aplicados a la posición
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "executed" && r.action_type !== "position_analysis" && (
                      <div className="text-[11px] text-[var(--color-success)] font-bold pt-1 flex items-center gap-1">
                        Compra LIVE ejecutada en tu broker
                        <span className="text-[var(--color-text-muted)]">→</span>
                        <span className="text-[var(--color-info)]">Posiciones</span>
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "dismissed" && (
                      <div className="text-[11px] text-[var(--color-text-muted)] pt-1">
                        Recomendación declinada
                      </div>
                    )}
                    {r.id?.startsWith("rec-") && r.status === "expired" && (
                      <div className="text-[11px] text-[var(--color-warning)] pt-1">
                        Recomendación expirada (sin acción en 24h)
                      </div>
                    )}
                  </div>
                )}
                {!isExpanded && (
                  <div className="text-[11px] text-[var(--color-text-muted)] mt-1">Click para expandir</div>
                )}
              </div>
            );
          })}
            </div>
          ))}
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
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-[16px] flex items-center justify-center w-6 h-6"
              >
                <X size={16} />
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
                {actionLoading === `rec-${sltpModalRecId}` ? "Procesando..." : `Colocar SL/TP en ${firstConnectedBroker?.displayName || activeBrokerId}`}
              </button>
              <p className="text-[11px] text-[var(--color-text-muted)] text-center -mt-1">
                Orden real: se ejecuta automáticamente cuando se alcanza SL o TP
              </p>
              <button
                disabled={actionLoading === `rec-${sltpModalRecId}`}
                onClick={() => handleMonitorOnly(sltpModalRecId)}
                className="w-full h-10 rounded-[8px] text-[12px] font-bold bg-[var(--color-info)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {actionLoading === `rec-${sltpModalRecId}` ? "Procesando..." : "Solo Monitorear"}
              </button>
              <p className="text-[11px] text-[var(--color-text-muted)] text-center -mt-1">
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
