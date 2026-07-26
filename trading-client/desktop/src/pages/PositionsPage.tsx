import { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { fmt, fmtDate } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import {
  ComposedChart,
  Line,
  Area,
  ReferenceLine,
  ResponsiveContainer,
  YAxis,
  Tooltip,
} from "recharts";

export function PositionsPage() {
  const [positions, setPositions] = useState<any[]>([]);
  const [riskEvents, setRiskEvents] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  const [prices, setPrices] = useState<Record<string, number>>({});
  const priceHistoryRef = useRef<Record<string, number[]>>({});

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
              const hist = priceHistoryRef.current[p.symbol] || [];

              // Build chart data
              const chartData = hist.map((v, i) => ({ i, v }));

              // Chart domain: include entry, SL, TP, current
              const allPrices = [entry, current, sl, tp].filter((v) => v > 0);
              const minPrice = Math.min(...allPrices);
              const maxPrice = Math.max(...allPrices);
              const padding = (maxPrice - minPrice) * 0.15 || maxPrice * 0.05;
              const yDomain: [number | string, number | string] = [
                Math.max(0, minPrice - padding),
                maxPrice + padding,
              ];

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

                  {/* Mini chart with Entry/SL/TP lines */}
                  <div className="h-[120px] mb-3 -mx-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={chartData} margin={{ top: 5, right: 8, bottom: 5, left: 8 }}>
                        <defs>
                          <linearGradient id={`grad-${p.id}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={isProfit ? "var(--color-success)" : "var(--color-danger)"} stopOpacity={0.25} />
                            <stop offset="100%" stopColor={isProfit ? "var(--color-success)" : "var(--color-danger)"} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <YAxis domain={yDomain} hide />
                        <Tooltip
                          contentStyle={{
                            background: "var(--color-surface)",
                            border: "1px solid var(--color-border)",
                            borderRadius: 8,
                            fontSize: 11,
                          }}
                          formatter={(v: any) => [`$${fmt(v)}`, "Precio"]}
                          labelFormatter={() => ""}
                        />
                        {chartData.length > 1 && (
                          <Area
                            type="monotone"
                            dataKey="v"
                            stroke="none"
                            fill={`url(#grad-${p.id})`}
                            strokeWidth={0}
                          />
                        )}
                        {chartData.length > 1 && (
                          <Line
                            type="monotone"
                            dataKey="v"
                            stroke={isProfit ? "var(--color-success)" : "var(--color-danger)"}
                            strokeWidth={2}
                            dot={false}
                          />
                        )}
                        {/* Entry line */}
                        <ReferenceLine
                          y={entry}
                          stroke="var(--color-text-muted)"
                          strokeDasharray="4 4"
                          strokeWidth={1}
                          label={{ value: "Entry", position: "left", fill: "var(--color-text-muted)", fontSize: 9 }}
                        />
                        {/* SL line */}
                        {sl > 0 && (
                          <ReferenceLine
                            y={sl}
                            stroke="var(--color-danger)"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: "SL", position: "left", fill: "var(--color-danger)", fontSize: 9 }}
                          />
                        )}
                        {/* TP line */}
                        {tp > 0 && (
                          <ReferenceLine
                            y={tp}
                            stroke="var(--color-success)"
                            strokeDasharray="3 3"
                            strokeWidth={1}
                            label={{ value: "TP", position: "left", fill: "var(--color-success)", fontSize: 9 }}
                          />
                        )}
                        {/* Current price line */}
                        {current > 0 && (
                          <ReferenceLine
                            y={current}
                            stroke={isProfit ? "var(--color-success)" : "var(--color-danger)"}
                            strokeWidth={1.5}
                          />
                        )}
                      </ComposedChart>
                    </ResponsiveContainer>
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
