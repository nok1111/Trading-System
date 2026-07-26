import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { fmt, fmtDate } from "../lib/utils";

export function PositionsPage() {
  const [positions, setPositions] = useState<any[]>([]);
  const [riskEvents, setRiskEvents] = useState<any[]>([]);
  const [filter, setFilter] = useState("");

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
  }, [filter]);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
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

      {/* Open positions as cards */}
      {open.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {open.map((p) => (
            <Card key={p.id}>
              <div className="flex justify-between items-start mb-3">
                <div>
                  <span className="font-bold text-lg">{p.symbol}</span>
                  <Badge
                    variant={p.side === "BUY" ? "success" : "danger"}
                    className="ml-2"
                  >
                    {p.side}
                  </Badge>
                </div>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {fmtDate(p.opened_at)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-[var(--color-text-muted)]">Cant: </span>
                  {fmt(p.quantity)}
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)]">Entry: </span>$
                  {fmt(p.entry_price)}
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)]">SL: </span>$
                  {fmt(p.stop_loss)}
                </div>
                <div>
                  <span className="text-[var(--color-text-muted)]">TP: </span>$
                  {fmt(p.take_profit)}
                </div>
                <div className="col-span-2">
                  <span className="text-[var(--color-text-muted)]">PnL: </span>
                  <span
                    className={
                      (p.pnl || 0) >= 0
                        ? "text-[var(--color-success)] font-semibold"
                        : "text-[var(--color-danger)] font-semibold"
                    }
                  >
                    ${fmt(p.pnl)}
                  </span>
                </div>
              </div>
            </Card>
          ))}
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
                  <Td>{p.symbol}</Td>
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
