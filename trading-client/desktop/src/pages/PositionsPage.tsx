import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../lib/api";
import { useLivePrices } from "../hooks/useLivePrices";
import { useDbPositions } from "../hooks/useDbPositions";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { fmt, fmtDate } from "../lib/utils";
import { cn } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { PositionChart } from "../components/PositionChart";
import { VirtualList } from "../components/common/VirtualList";
import { useI18n } from "../i18n/I18nContext";
import { toast } from "../components/ui/Toast";

export function PositionsPage() {
  const { t } = useI18n();
  const [riskEvents, setRiskEvents] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  const priceHistoryRef = useRef<Record<string, number[]>>({});
  const [paperStatus, setPaperStatus] = useState<any>(null);
  const [paperAction, setPaperAction] = useState("");
  const [depositAmount, setDepositAmount] = useState("1000");
  const [paperInterval, setPaperInterval] = useState("30");
  const [activeTab, setActiveTab] = useState<"live" | "paper">("live");
  const [paperPositions, setPaperPositions] = useState<any[]>([]);
  const [slTpModal, setSlTpModal] = useState<{ symbol: string; positionId: number | null; entry: number } | null>(null);
  const [slInput, setSlInput] = useState("");
  const [tpInput, setTpInput] = useState("");
  const [closingIds, setClosingIds] = useState<Set<number>>(new Set());

  // Real-time prices via WebSocket
  const { prices: wsPrices } = useLivePrices([], 5000);

  // Real-time DB positions via WebSocket (no polling needed)
  const { positions: wsDbPositions, closedIds: wsClosedIds } = useDbPositions();

  // Merge WS DB positions with broker-live positions
  // wsDbPositions are from DB (may include broker positions merged by backend)
  // We also fetch full positions list periodically for broker-live positions
  const [brokerPositions, setBrokerPositions] = useState<any[]>([]);

  const loadBrokerPositions = useCallback(async () => {
    try {
      const p = await api<any[]>("/api/positions" + (filter ? `?status=${filter}` : ""));
      setBrokerPositions(p);
    } catch {}
  }, [filter]);

  useEffect(() => {
    loadBrokerPositions();
    const id = setInterval(loadBrokerPositions, 5000);
    return () => clearInterval(id);
  }, [loadBrokerPositions]);

  // Use broker positions as primary (they include both DB and broker-live)
  // but update with WS DB positions for real-time SL/TP/status changes
  const positions = brokerPositions.map((bp) => {
    const wsMatch = wsDbPositions.find((wp) => wp.id === bp.id && bp.id > 0);
    if (wsMatch) {
      // Merge: WS data takes priority for SL/TP/status
      return {
        ...bp,
        stop_loss: wsMatch.stop_loss !== null ? wsMatch.stop_loss : bp.stop_loss,
        take_profit: wsMatch.take_profit !== null ? wsMatch.take_profit : bp.take_profit,
        status: wsMatch.status || bp.status,
        auto_sell_enabled: wsMatch.auto_sell_enabled !== null ? wsMatch.auto_sell_enabled : bp.auto_sell_enabled,
        unrealized_pnl: wsMatch.unrealized_pnl !== null ? wsMatch.unrealized_pnl : bp.unrealized_pnl,
        current_price: wsMatch.current_price !== null ? wsMatch.current_price : bp.current_price,
        realized_pnl: wsMatch.realized_pnl !== null ? wsMatch.realized_pnl : bp.realized_pnl,
        closed_at: wsMatch.closed_at || bp.closed_at,
      };
    }
    return bp;
  });

  // Show toast when positions are closed
  useEffect(() => {
    if (wsClosedIds.length > 0) {
      for (const pid of wsClosedIds) {
        if (!lastNotifiedClosedRef.current.has(pid)) {
          lastNotifiedClosedRef.current.add(pid);
          const pos = positions.find((p) => p.id === pid);
          if (pos) {
            const pnl = Number(pos.realized_pnl || 0);
            toast(`Posición #${pid} ${pos.symbol} cerrada — P&L: ${pnl >= 0 ? "+" : ""}$${fmt(Math.abs(pnl))}`, pnl >= 0);
          }
        }
      }
      // Refresh broker positions to get the updated state
      loadBrokerPositions();
    }
  }, [wsClosedIds]);

  const lastNotifiedClosedRef = useRef<Set<number>>(new Set());

  // Update price history on WS updates
  useEffect(() => {
    for (const [symbol, price] of Object.entries(wsPrices)) {
      const hist = priceHistoryRef.current[symbol] || [];
      hist.push(price);
      if (hist.length > 60) hist.shift();
      priceHistoryRef.current[symbol] = hist;
    }
  }, [wsPrices]);

  const load = useCallback(async () => {
    try {
      const r = await api<any[]>("/api/risk-events");
      setRiskEvents(r);
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const loadPaperStatus = useCallback(async () => {
    try {
      const s = await api<any>("/api/paper-trading/status");
      setPaperStatus(s);
      if (s.interval_seconds) setPaperInterval(String(s.interval_seconds));
    } catch {}
  }, []);

  useEffect(() => {
    loadPaperStatus();
    const id = setInterval(loadPaperStatus, 10000);
    return () => clearInterval(id);
  }, [loadPaperStatus]);

  const loadPaperPositions = useCallback(async () => {
    try {
      const pp = await api<any[]>("/api/intelligence/paper-positions");
      setPaperPositions(pp);
    } catch {}
  }, []);

  useEffect(() => {
    loadPaperPositions();
    const id = setInterval(loadPaperPositions, activeTab === "paper" ? 5000 : 10000);
    return () => clearInterval(id);
  }, [activeTab, loadPaperPositions]);

  const handleToggleAutoSell = async (positionId: number, enabled: boolean) => {
    try {
      await api(`/api/positions/${positionId}/auto-sell?enabled=${enabled}`, { method: "PATCH" });
      toast(`Auto-sell ${enabled ? "activado" : "desactivado"} para posición #${positionId}`, enabled);
      // WS will push the update — no manual reload needed
    } catch (e: any) {
      toast(`Error al cambiar auto-sell: ${e.message}`, false);
    }
  };

  const handleClosePosition = async (p: any) => {
    const pid = p.id || 0;
    const sym = p.symbol;
    const qty = Number(p.quantity || 0);
    setClosingIds(prev => new Set([...prev, pid]));
    try {
      const body: any = { symbol: sym, broker_id: p.broker_id || "binance" };
      if (pid > 0) body.position_id = pid;
      if (qty > 0) body.quantity = qty;
      const result = await api<any>("/api/positions/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (result.status === "executed") {
        toast(`Posición ${sym} cerrada en mercado`, true);
        // WS will push the update — no manual reload needed
      } else {
        toast(`Error al cerrar: ${result.reason || "desconocido"}`, false);
      }
    } catch (e: any) {
      toast(`Error al cerrar posición: ${e.message}`, false);
    } finally {
      setClosingIds(prev => { const s = new Set(prev); s.delete(pid); return s; });
    }
  };

  const handleSetSlTp = async () => {
    if (!slTpModal) return;
    const { symbol, positionId } = slTpModal;
    try {
      const body: any = { symbol, broker_id: "binance" };
      if (positionId && positionId > 0) body.position_id = positionId;
      if (slInput) {
        const val = parseFloat(slInput);
        if (val > 0 && val < 1) body.stop_loss_pct = val;
        else body.stop_loss = val;
      }
      if (tpInput) {
        const val = parseFloat(tpInput);
        if (val > 0 && val < 1) body.take_profit_pct = val;
        else body.take_profit = val;
      }
      const result = await api<any>("/api/positions/set-sl-tp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (result.status === "executed") {
        toast(`SL/TP actualizado para ${symbol}`, true);
        setSlTpModal(null);
        setSlInput("");
        setTpInput("");
        // WS will push the update — no manual reload needed
      } else {
        toast(`Error: ${result.reason || "desconocido"}`, false);
      }
    } catch (e: any) {
      toast(`Error al setear SL/TP: ${e.message}`, false);
    }
  };

  const handlePaperSell = async (positionId: number) => {
    try {
      await api(`/api/intelligence/paper-positions/${positionId}/sell`, { method: "POST" });
      await loadPaperPositions();
    } catch (e) {
      console.error("Paper sell failed:", e);
    }
  };

  const handlePaperStart = async () => {
    setPaperAction("starting");
    try {
      await api("/api/paper-trading/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategies: ["trend"], interval_seconds: parseInt(paperInterval) }),
      });
      await loadPaperStatus();
    } catch {}
    setPaperAction("");
  };

  const handlePaperStop = async () => {
    setPaperAction("stopping");
    try {
      await api("/api/paper-trading/stop", { method: "POST" });
      await loadPaperStatus();
    } catch {}
    setPaperAction("");
  };

  const handlePaperDeposit = async () => {
    try {
      await api("/api/paper-trading/deposit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount: parseFloat(depositAmount) }),
      });
    } catch {}
  };

  const handlePaperInterval = async () => {
    try {
      await api("/api/paper-trading/interval", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval_seconds: parseInt(paperInterval) }),
      });
      await loadPaperStatus();
    } catch {}
  };

  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");
  const totalPnl = closed.reduce((a, p) => a + (p.pnl || 0), 0);
  const winCount = closed.filter((p) => (p.pnl || 0) > 0).length;

  const paperTotalPnl = paperPositions.reduce((a, p) => a + (p.unrealized_pnl || 0), 0);
  const paperTotalValue = paperPositions.reduce((a, p) => a + (p.usd_value || 0), 0);

  return (
    <div className="p-5 space-y-4">
      {/* Tab selector */}
      <div className="flex gap-2 border-b border-[var(--color-border)] pb-2">
        <button
          className={cn(
            "px-3 h-8 rounded-[6px] text-[12px] font-bold transition-colors",
            activeTab === "live"
              ? "bg-[var(--color-primary)] text-white"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          )}
          onClick={() => setActiveTab("live")}
        >
          Live
        </button>
        <button
          className={cn(
            "px-3 h-8 rounded-[6px] text-[12px] font-bold transition-colors flex items-center gap-1.5",
            activeTab === "paper"
              ? "bg-[var(--color-info)] text-white"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          )}
          onClick={() => setActiveTab("paper")}
        >
          Paper Positions
          {paperPositions.length > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[9px] bg-[var(--color-info)]/20 text-[var(--color-info)]">
              {paperPositions.length}
            </span>
          )}
        </button>
      </div>

      {/* Paper Positions Tab */}
      {activeTab === "paper" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card>
              <CardLabel>Paper Posiciones Activas</CardLabel>
              <CardValue className="text-[var(--color-info)]">
                {paperPositions.length}
              </CardValue>
            </Card>
            <Card>
              <CardLabel>Valor Total</CardLabel>
              <CardValue>${fmt(paperTotalValue)}</CardValue>
            </Card>
            <Card>
              <CardLabel>PnL No Realizado</CardLabel>
              <CardValue
                className={
                  paperTotalPnl >= 0
                    ? "text-[var(--color-success)]"
                    : "text-[var(--color-danger)]"
                }
              >
                {paperTotalPnl >= 0 ? "+" : ""}${fmt(Math.abs(paperTotalPnl))}
              </CardValue>
            </Card>
          </div>

          {/* Paper Trading Control Panel */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-[var(--color-primary)]">
                Paper Trading
              </h3>
              <span
                className={`text-[11px] font-bold px-2 h-5 rounded flex items-center ${
                  paperStatus?.status === "running"
                    ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                    : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                }`}
              >
                {paperStatus?.status === "running" ? "RUNNING" : "STOPPED"}
              </span>
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              {paperStatus?.status === "running" ? (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handlePaperStop}
                  disabled={!!paperAction}
                >
                  {paperAction === "stopping" ? "Stopping..." : "Stop"}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handlePaperStart}
                  disabled={!!paperAction}
                >
                  {paperAction === "starting" ? "Starting..." : "Start"}
                </Button>
              )}
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                  Interval (sec)
                </label>
                <div className="flex gap-1">
                  <input
                    type="number"
                    value={paperInterval}
                    onChange={(e) => setPaperInterval(e.target.value)}
                    min={5}
                    className="w-20 h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                  />
                  <Button variant="default" size="sm" onClick={handlePaperInterval}>
                    Set
                  </Button>
                </div>
              </div>
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">
                  Deposit (USDT)
                </label>
                <div className="flex gap-1">
                  <input
                    type="number"
                    value={depositAmount}
                    onChange={(e) => setDepositAmount(e.target.value)}
                    className="w-24 h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
                  />
                  <Button variant="default" size="sm" onClick={handlePaperDeposit}>
                    Deposit
                  </Button>
                </div>
              </div>
              {paperStatus?.local_time && (
                <span className="text-[11px] text-[var(--color-text-muted)] ml-auto">
                  {paperStatus.local_time}
                </span>
              )}
            </div>
          </Card>

          {paperPositions.length === 0 ? (
            <div className="text-center py-12 text-[12px] text-[var(--color-text-muted)]">
              No hay paper positions activas.
              <br />
              Acepta recomendaciones desde la pestaña Reportes para crear posiciones simuladas.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {paperPositions.map((p) => {
                const entry = Number(p.entry_price || 0);
                const current = Number(p.current_price || 0);
                const sl = Number(p.stop_loss || 0);
                const tp = Number(p.take_profit || 0);
                const pnl = Number(p.unrealized_pnl || 0);
                const pnlPct = Number(p.pnl_pct || 0);
                const isProfit = pnl >= 0;
                const qty = Number(p.quantity || 0);
                const invested = Number(p.invested || 0);
                const meta = p.metadata_json || {};
                return (
                  <Card key={p.id}>
                    {/* Header */}
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        <CryptoIcon symbol={p.symbol} size={32} />
                        <div>
                          <span className="font-bold text-lg">{p.symbol}</span>
                          <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-info)] text-white">PAPER</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-[var(--color-text-muted)]">
                          {fmtDate(p.opened_at)}
                        </div>
                        <div
                          className={`text-lg font-bold ${
                            isProfit
                              ? "text-[var(--color-success)]"
                              : "text-[var(--color-danger)]"
                          }`}
                        >
                          {isProfit ? "+" : ""}${fmt(Math.abs(pnl))}
                        </div>
                      </div>
                    </div>

                    {/* Chart with entry marker + SL/TP zone */}
                    <div className="mb-3">
                      <PositionChart
                        symbol={p.symbol}
                        entry={entry}
                        stopLoss={sl}
                        takeProfit={tp}
                        side={p.side || "BUY"}
                        openedAt={p.opened_at}
                        height={180}
                      />
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Entry</div>
                        <div className="num font-bold">${fmt(entry)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Actual</div>
                        <div className={`num font-bold ${isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                          ${fmt(current)}
                        </div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Cant.</div>
                        <div className="num font-bold">{qty.toFixed(6)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-danger)] uppercase">Stop Loss</div>
                        <div className="num font-bold text-[var(--color-danger)]">${fmt(sl)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-success)] uppercase">Take Profit</div>
                        <div className="num font-bold text-[var(--color-success)]">${fmt(tp)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Inversión</div>
                        <div className="num font-bold">${fmt(invested)}</div>
                      </div>
                    </div>

                    {/* PnL progress bar */}
                    <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                      <div className="flex justify-between items-center mb-1.5">
                        <span className="text-xs text-[var(--color-text-muted)]">PnL {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</span>
                        <span className={`text-sm font-bold ${isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                          {isProfit ? "+" : ""}${fmt(Math.abs(pnl))}
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full bg-[var(--color-surface-3)] overflow-hidden">
                        {isProfit && tp > 0 ? (
                          <div
                            className="absolute left-1/2 h-full bg-[var(--color-success)] rounded-full"
                            style={{ width: `${Math.min(Math.abs(pnlPct) / Math.abs(((tp - entry) / entry) * 100) * 50, 50)}%` }}
                          />
                        ) : !isProfit && sl > 0 ? (
                          <div
                            className="absolute right-1/2 h-full bg-[var(--color-danger)] rounded-full"
                            style={{ width: `${Math.min(Math.abs(pnlPct) / Math.abs(((entry - sl) / entry) * 100) * 50, 50)}%` }}
                          />
                        ) : null}
                        <div className="absolute top-0 left-1/2 w-px h-full bg-[var(--color-border)]" />
                      </div>
                      <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-1">
                        <span>SL ${fmt(sl)}</span>
                        <span>Entry ${fmt(entry)}</span>
                        <span>TP ${fmt(tp)}</span>
                      </div>
                    </div>

                    {/* Reason */}
                    {meta.reason && (
                      <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Razón IA</span>
                        <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{meta.reason}</p>
                      </div>
                    )}

                    {/* Sell button */}
                    <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                      <Button
                        variant="danger"
                        size="sm"
                        className="w-full"
                        onClick={() => handlePaperSell(p.id)}
                      >
                        Vender (Paper)
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Positions Tab */}
      {activeTab === "live" && (
        <>
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        <Card>
          <CardLabel>{t("portfolio.openPositions")}</CardLabel>
          <CardValue className="text-[var(--color-primary)]">
            {open.length}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Posiciones Cerradas</CardLabel>
          <CardValue>{closed.length}</CardValue>
        </Card>
        <Card>
          <CardLabel>PnL Total</CardLabel>
          <CardValue
            className={
              totalPnl >= 0
                ? "text-[var(--color-success)]"
                : "text-[var(--color-danger)]"
            }
          >
            ${fmt(totalPnl)}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Win Rate</CardLabel>
          <CardValue>
            {closed.length > 0
              ? fmt((winCount / closed.length) * 100)
              : "0.00"}
            %
          </CardValue>
        </Card>
      </div>

      {/* Filter */}
      <div className="flex gap-2 items-center">
        <Select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">Todos</option>
          <option value="open">Abiertas</option>
          <option value="closed">Cerradas</option>
        </Select>
        <Button variant="primary" size="sm" onClick={load}>
          Filtrar
        </Button>
      </div>

      {/* Open positions — dynamic grid with mini charts */}
      {open.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
            {t("portfolio.openPositions")}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {open.map((p) => {
              const entry = Number(p.entry_price || 0);
              const current = Number(p.current_price || wsPrices[p.symbol] || 0);
              const sl = Number(p.stop_loss || 0);
              const tp = Number(p.take_profit || 0);
              const pnl = Number(p.unrealized_pnl || p.pnl || 0);
              const pnlPct = entry > 0 ? ((current - entry) / entry) * 100 : 0;
              const isLong = (p.side || "").toLowerCase() === "long" || (p.side || "").toUpperCase() === "BUY";
              const isProfit = pnl >= 0;
              const qty = Number(p.quantity || 0);
              const invested = qty * entry;
              const isHeld = !!(p.metadata_json?.hold);
              const autoSell = p.auto_sell_enabled !== false;
              return (
                <Card key={p.id}>
                  {/* Header */}
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-2">
                      <CryptoIcon symbol={p.symbol} size={32} />
                      <div>
                        <span className="font-bold text-lg">{p.symbol}</span>
                        <Badge
                          variant={isLong ? "success" : "danger"}
                          className="ml-2"
                        >
                          {p.side}
                        </Badge>
                        {isHeld && (
                          <Badge variant="primary" className="ml-2">
                            HOLD
                          </Badge>
                        )}
                        {autoSell ? (
                          <Badge variant="success" className="ml-2">AUTO-SELL</Badge>
                        ) : (
                          <Badge variant="warning" className="ml-2">MANUAL</Badge>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-[var(--color-text-muted)]">
                        {fmtDate(p.opened_at)}
                      </div>
                      <div
                        className={`text-lg font-bold ${
                          isProfit
                            ? "text-[var(--color-success)]"
                            : "text-[var(--color-danger)]"
                        }`}
                      >
                        {isProfit ? "+" : ""}${fmt(Math.abs(pnl))}
                      </div>
                    </div>
                  </div>

                  {/* Chart with 10 style options */}
                  <div className="mb-3">
                    <PositionChart
                      symbol={p.symbol}
                      entry={entry}
                      stopLoss={sl}
                      takeProfit={tp}
                      side={p.side}
                      openedAt={p.opened_at}
                      height={200}
                    />
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Entry</div>
                      <div className="num font-bold">${fmt(entry)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Actual</div>
                      <div className={`num font-bold ${isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                        ${fmt(current)}
                      </div>
                    </div>
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Cant.</div>
                      <div className="num font-bold">{qty}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-danger)] uppercase">Stop Loss</div>
                      <div className="num font-bold text-[var(--color-danger)]">${fmt(sl)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-success)] uppercase">Take Profit</div>
                      <div className="num font-bold text-[var(--color-success)]">${fmt(tp)}</div>
                    </div>
                    <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                      <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Inversión</div>
                      <div className="num font-bold">${fmt(invested)}</div>
                    </div>
                  </div>

                  {/* PnL progress bar */}
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                    <div className="flex justify-between items-center mb-1.5">
                      <span className="text-xs text-[var(--color-text-muted)]">PnL {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</span>
                      <span className={`text-sm font-bold ${isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                        {isProfit ? "+" : ""}${fmt(Math.abs(pnl))}
                      </span>
                    </div>
                    <div className="relative h-2 rounded-full bg-[var(--color-surface-3)] overflow-hidden">
                      {isProfit && tp > 0 ? (
                        <div
                          className="absolute left-1/2 h-full bg-[var(--color-success)] rounded-full"
                          style={{ width: `${Math.min(Math.abs(pnlPct) / Math.abs(((tp - entry) / entry) * 100) * 50, 50)}%` }}
                        />
                      ) : !isProfit && sl > 0 ? (
                        <div
                          className="absolute right-1/2 h-full bg-[var(--color-danger)] rounded-full"
                          style={{ width: `${Math.min(Math.abs(pnlPct) / Math.abs(((entry - sl) / entry) * 100) * 50, 50)}%` }}
                        />
                      ) : null}
                      <div className="absolute top-0 left-1/2 w-px h-full bg-[var(--color-border)]" />
                    </div>
                    <div className="flex justify-between text-[9px] text-[var(--color-text-muted)] mt-1">
                      <span>SL ${fmt(sl)}</span>
                      <span>Entry ${fmt(entry)}</span>
                      <span>TP ${fmt(tp)}</span>
                    </div>
                  </div>

                  {/* Sell, SL/TP & Auto-Sell toggle */}
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex gap-2">
                      <Button
                        variant="danger"
                        size="sm"
                        className="flex-1"
                        title="Vende y cierra la posición inmediatamente al precio de mercado"
                        disabled={closingIds.has(p.id || 0)}
                        onClick={() => handleClosePosition(p)}
                      >
                        {closingIds.has(p.id || 0) ? "Cerrando..." : "Sell"}
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        className="flex-1"
                        title="Configurar Stop Loss y Take Profit"
                        onClick={() => {
                          setSlTpModal({ symbol: p.symbol, positionId: p.id > 0 ? p.id : null, entry });
                          setSlInput(sl > 0 ? String(sl) : "");
                          setTpInput(tp > 0 ? String(tp) : "");
                        }}
                      >
                        SL/TP
                      </Button>
                      <Button
                        variant={autoSell ? "primary" : "default"}
                        size="sm"
                        className="flex-1"
                        title={autoSell ? "Desactivar auto-sell: la IA no venderá esta posición automáticamente" : "Activar auto-sell: la IA venderá automáticamente según SL/TP/indicadores"}
                        onClick={() => handleToggleAutoSell(p.id, !autoSell)}
                        disabled={!p.id || p.id === 0}
                      >
                        {autoSell ? "Auto-Sell ✓" : "Auto-Sell"}
                      </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Closed positions table — virtualized when >30 items */}
      {closed.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
            {t("portfolio.closedPositions")} ({closed.length})
          </h3>
          {closed.length > 30 ? (
            <>
              <Table>
                <thead>
                  <Tr>
                    <Th>ID</Th>
                    <Th>Símbolo</Th>
                    <Th>Lado</Th>
                    <Th>Cant.</Th>
                    <Th>Entry</Th>
                    <Th>Exit</Th>
                    <Th>Inversión</Th>
                    <Th>PnL</Th>
                    <Th>PnL %</Th>
                    <Th>Duración</Th>
                  </Tr>
                </thead>
              </Table>
              <VirtualList
                items={closed.slice().reverse()}
                estimateSize={42}
                height={400}
                renderItem={(p) => (
                  <div className="flex items-center text-[12px] border-b border-[var(--color-border)]/50 px-2 h-[42px]">
                    <span className="w-12 flex-shrink-0 text-[var(--color-text-muted)]">{p.id}</span>
                    <span className="w-24 flex-shrink-0 flex items-center gap-1.5 font-bold text-[var(--color-text)]">
                      <CryptoIcon symbol={p.symbol} size={18} />
                      {p.symbol}
                    </span>
                    <span className="w-16 flex-shrink-0">{p.side}</span>
                    <span className="w-20 flex-shrink-0">{fmt(p.quantity)}</span>
                    <span className="w-24 flex-shrink-0">${fmt(p.entry_price)}</span>
                    <span className="w-24 flex-shrink-0">${fmt(p.exit_price)}</span>
                    <span className="w-24 flex-shrink-0">${fmt(p.invested)}</span>
                    <span className={cn("w-24 flex-shrink-0 font-bold", (p.pnl || 0) >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      ${fmt(p.pnl)}
                    </span>
                    <span className="w-20 flex-shrink-0">{fmt(p.pnl_pct)}%</span>
                    <span className="flex-1 text-[var(--color-text-muted)]">{p.duration || "-"}</span>
                  </div>
                )}
              />
            </>
          ) : (
            <Table>
              <thead>
                <Tr>
                  <Th>ID</Th>
                  <Th>Símbolo</Th>
                  <Th>Lado</Th>
                  <Th>Cant.</Th>
                  <Th>Entry</Th>
                  <Th>Exit</Th>
                  <Th>Inversión</Th>
                  <Th>PnL</Th>
                  <Th>PnL %</Th>
                  <Th>Duración</Th>
                </Tr>
              </thead>
              <tbody>
                {closed.slice(-30).reverse().map((p) => (
                  <Tr key={p.id}>
                    <Td>{p.id}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <CryptoIcon symbol={p.symbol} size={24} />
                        {p.symbol}
                      </div>
                    </Td>
                    <Td>{p.side}</Td>
                    <Td>{fmt(p.quantity)}</Td>
                    <Td>${fmt(p.entry_price)}</Td>
                    <Td>${fmt(p.exit_price)}</Td>
                    <Td>${fmt(p.invested)}</Td>
                    <Td
                      className={
                        (p.pnl || 0) >= 0
                          ? "text-[var(--color-success)]"
                          : "text-[var(--color-danger)]"
                      }
                    >
                      ${fmt(p.pnl)}
                    </Td>
                    <Td>{fmt(p.pnl_pct)}%</Td>
                    <Td>{p.duration || "-"}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>
      )}

      {/* Risk events */}
      {riskEvents.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-danger)] mb-3">
            {t("portfolio.riskEvents")}
          </h3>
          <Table>
            <thead>
              <Tr>
                <Th>ID</Th>
                <Th>Fecha</Th>
                <Th>Tipo</Th>
                <Th>Mensaje</Th>
                <Th>Severidad</Th>
              </Tr>
            </thead>
            <tbody>
              {riskEvents.slice(-20).reverse().map((r) => (
                <Tr key={r.id}>
                  <Td>{r.id}</Td>
                  <Td>{fmtDate(r.timestamp)}</Td>
                  <Td>{r.event_type}</Td>
                  <Td>{r.message}</Td>
                  <Td>
                    <Badge
                      variant={
                        r.severity === "critical"
                          ? "danger"
                          : r.severity === "warning"
                            ? "warning"
                            : "default"
                      }
                    >
                      {r.severity}
                    </Badge>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      {positions.length === 0 && (
        <Card className="text-center py-12">
          <p className="text-[var(--color-text-muted)]">
            Sin posiciones. El AI Agent abrirá posiciones automáticamente.
          </p>
        </Card>
      )}

      {/* SL/TP Modal */}
      {slTpModal && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setSlTpModal(null)}
        >
          <div
            className="bg-[var(--color-surface)] rounded-xl p-6 w-96 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold mb-1">Configurar SL/TP</h3>
            <p className="text-xs text-[var(--color-text-muted)] mb-4">
              {slTpModal.symbol} — Entry: ${fmt(slTpModal.entry)}
            </p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[var(--color-text-muted)] uppercase">Stop Loss</label>
                <input
                  type="number"
                  step="any"
                  value={slInput}
                  onChange={(e) => setSlInput(e.target.value)}
                  placeholder="Valor absoluto (ej: 60000) o % (ej: 0.05 = 5%)"
                  className="w-full mt-1 px-3 py-2 rounded-lg bg-[var(--color-surface-2)] text-sm border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--color-text-muted)] uppercase">Take Profit</label>
                <input
                  type="number"
                  step="any"
                  value={tpInput}
                  onChange={(e) => setTpInput(e.target.value)}
                  placeholder="Valor absoluto (ej: 70000) o % (ej: 0.10 = 10%)"
                  className="w-full mt-1 px-3 py-2 rounded-lg bg-[var(--color-surface-2)] text-sm border border-[var(--color-border)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button variant="default" size="sm" className="flex-1" onClick={() => setSlTpModal(null)}>
                  Cancelar
                </Button>
                <Button variant="primary" size="sm" className="flex-1" onClick={handleSetSlTp}>
                  Guardar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
      )}
    </div>
  );
}
