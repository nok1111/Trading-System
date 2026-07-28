import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { fmt, fmtDate } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { PositionChart } from "../components/PositionChart";

export function PositionsPage() {
  const [positions, setPositions] = useState<any[]>([]);
  const [riskEvents, setRiskEvents] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  const [prices, setPrices] = useState<Record<string, number>>({});
  const priceHistoryRef = useRef<Record<string, number[]>>({});
  const [paperStatus, setPaperStatus] = useState<any>(null);
  const [paperAction, setPaperAction] = useState("");
  const [depositAmount, setDepositAmount] = useState("1000");
  const [paperInterval, setPaperInterval] = useState("30");

  const load = useCallback(async () => {
    try {
      const p = await api<any[]>(
        "/api/positions" + (filter ? `?status=${filter}` : "")
      );
      setPositions(p);
    } catch {}
    try {
      const r = await api<any[]>("/api/risk-events");
      setRiskEvents(r);
    } catch {}
    try {
      const pr = await api<any>("/api/prices/live");
      const priceList = Array.isArray(pr)
        ? pr
        : pr?.prices
          ? Object.entries(pr.prices).map(([symbol, price]) => ({ symbol, price: Number(price) }))
          : [];
      const priceMap: Record<string, number> = {};
      for (const p of priceList) {
        priceMap[p.symbol] = Number(p.price);
        const hist = priceHistoryRef.current[p.symbol] || [];
        hist.push(Number(p.price));
        if (hist.length > 60) hist.shift();
        priceHistoryRef.current[p.symbol] = hist;
      }
      setPrices(priceMap);
    } catch {}
  }, [filter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
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

  return (
    <div className="p-5 space-y-4">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        <Card>
          <CardLabel>Posiciones Abiertas</CardLabel>
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
            Posiciones Abiertas
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {open.map((p) => {
              const entry = Number(p.entry_price || 0);
              const current = Number(p.current_price || prices[p.symbol] || 0);
              const sl = Number(p.stop_loss || 0);
              const tp = Number(p.take_profit || 0);
              const pnl = Number(p.unrealized_pnl || p.pnl || 0);
              const pnlPct = entry > 0 ? ((current - entry) / entry) * 100 : 0;
              const isLong = (p.side || "").toLowerCase() === "long" || (p.side || "").toUpperCase() === "BUY";
              const isProfit = pnl >= 0;
              const qty = Number(p.quantity || 0);
              const invested = qty * entry;
              const isHeld = !!(p.metadata_json?.hold);
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

                  {/* Sell & Hold buttons */}
                  <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex gap-2">
                      <Button
                        variant="danger"
                        size="sm"
                        className="flex-1"
                        title="Vende y cierra la posición inmediatamente al precio de mercado"
                        onClick={async () => {
                          try {
                            await api("/api/paper-trading/sell", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ symbol: p.symbol }),
                            });
                            load();
                          } catch (e) {
                            console.error("Sell failed:", e);
                          }
                        }}
                      >
                        Sell
                      </Button>
                      <Button
                        variant={isHeld ? "primary" : "default"}
                        size="sm"
                        className="flex-1"
                        title={isHeld ? "Quitar Hold: la IA podrá vender esta posición" : "Hold: la IA no venderá esta posición automáticamente"}
                        onClick={async () => {
                          try {
                            await api("/api/paper-trading/hold", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ symbol: p.symbol, hold: !isHeld }),
                            });
                            load();
                          } catch (e) {
                            console.error("Hold failed:", e);
                          }
                        }}
                      >
                        {isHeld ? "Hold ✓" : "Hold"}
                      </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Closed positions table */}
      {closed.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
            Historial de Posiciones Cerradas
          </h3>
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
        </div>
      )}

      {/* Risk events */}
      {riskEvents.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-danger)] mb-3">
            Eventos de Riesgo
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
    </div>
  );
}
