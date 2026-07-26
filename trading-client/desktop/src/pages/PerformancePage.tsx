import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { toast } from "../components/ui/Toast";
import { fmt } from "../lib/utils";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const CHART_COLORS = [
  "var(--color-success)",
  "var(--color-danger)",
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-warning)",
];

export function PerformancePage() {
  const [stats, setStats] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [aiStats, setAiStats] = useState<any>(null);
  const [strategyStats, setStrategyStats] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const s = await api<any>("/api/stats");
      setStats(s);
    } catch {}
    try {
      const snap = await api<any[]>("/api/snapshots");
      setSnapshots(snap.slice(-100));
    } catch {}
    try {
      const t = await api<any[]>("/api/trades");
      setTrades(t);
    } catch {}
    try {
      const a = await api<any>("/api/ai-agent/stats");
      setAiStats(a);
    } catch {}
    try {
      const st = await api<any[]>("/api/stats/by-strategy");
      setStrategyStats(st);
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const resetStats = async () => {
    if (!confirm("¿Reiniciar todas las stats?")) return;
    try {
      await api("/api/stats/reset", { method: "POST" });
      toast("Stats reiniciadas");
      load();
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const equityData = snapshots.map((s) => ({
    name: new Date(s.timestamp).toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "2-digit",
    }),
    equity: s.total_equity,
  }));

  const pnlData = trades.slice(-50).map((t, i) => ({
    name: `#${i + 1}`,
    pnl: t.pnl || 0,
  }));

  const winLossData = [
    {
      name: "Aciertos",
      value: trades.filter((t) => (t.pnl || 0) > 0).length,
    },
    {
      name: "Fallos",
      value: trades.filter((t) => (t.pnl || 0) < 0).length,
    },
  ];

  return (
    <div className="p-5 space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-[var(--color-accent)]">
            Performance Dashboard
          </h2>
          <p className="text-sm text-[var(--color-text-muted)]">
            Métricas de trading y AI Agent
          </p>
        </div>
        <Button variant="danger" size="sm" onClick={resetStats}>
          Reiniciar Stats
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">
        <Card>
          <CardLabel>Total Trades</CardLabel>
          <CardValue>{stats?.total_trades ?? 0}</CardValue>
        </Card>
        <Card>
          <CardLabel>Win Rate</CardLabel>
          <CardValue className="text-[var(--color-success)]">
            {fmt(stats?.win_rate)}%
          </CardValue>
        </Card>
        <Card>
          <CardLabel>PnL Total</CardLabel>
          <CardValue
            className={
              (stats?.total_pnl ?? 0) >= 0
                ? "text-[var(--color-success)]"
                : "text-[var(--color-danger)]"
            }
          >
            ${fmt(stats?.total_pnl)}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Mejor Trade</CardLabel>
          <CardValue className="text-[var(--color-success)]">
            ${fmt(stats?.best_trade)}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Peor Trade</CardLabel>
          <CardValue className="text-[var(--color-danger)]">
            ${fmt(stats?.worst_trade)}
          </CardValue>
        </Card>
        <Card>
          <CardLabel>Sharpe</CardLabel>
          <CardValue>{fmt(stats?.sharpe_ratio)}</CardValue>
        </Card>
      </div>

      {/* Equity chart */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-success)] mb-4">
          Curva de Equity
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={equityData}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-border)"
            />
            <XAxis dataKey="name" stroke="var(--color-text-muted)" />
            <YAxis stroke="var(--color-text-muted)" />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
              }}
            />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="var(--color-primary)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* PnL per trade + Win/Loss */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-warning)] mb-4">
            PnL por Trade
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={pnlData}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--color-border)"
              />
              <XAxis dataKey="name" stroke="var(--color-text-muted)" />
              <YAxis stroke="var(--color-text-muted)" />
              <Tooltip
                contentStyle={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "8px",
                }}
              />
              <Bar dataKey="pnl" fill="var(--color-warning)" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-success)] mb-4">
            Aciertos vs Fallos
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={winLossData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {winLossData.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "8px",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* AI Agent stats */}
      {aiStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardLabel>AI Decisiones</CardLabel>
            <CardValue className="text-[var(--color-accent)]">
              {aiStats.total_decisions ?? 0}
            </CardValue>
          </Card>
          <Card>
            <CardLabel>AI Trades</CardLabel>
            <CardValue className="text-[var(--color-primary)]">
              {aiStats.total_trades ?? 0}
            </CardValue>
          </Card>
          <Card>
            <CardLabel>AI PnL</CardLabel>
            <CardValue
              className={
                (aiStats.total_pnl ?? 0) >= 0
                  ? "text-[var(--color-success)]"
                  : "text-[var(--color-danger)]"
              }
            >
              ${fmt(aiStats.total_pnl)}
            </CardValue>
          </Card>
          <Card>
            <CardLabel>AI Win Rate</CardLabel>
            <CardValue>{fmt(aiStats.win_rate)}%</CardValue>
          </Card>
        </div>
      )}

      {/* Strategy stats */}
      {strategyStats.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
            Stats por Estrategia
          </h3>
          <Table>
            <thead>
              <Tr>
                <Th>Estrategia</Th>
                <Th>Trades</Th>
                <Th>Win Rate</Th>
                <Th>PnL</Th>
                <Th>Mejor</Th>
                <Th>Peor</Th>
              </Tr>
            </thead>
            <tbody>
              {strategyStats.map((s) => (
                <Tr key={s.strategy}>
                  <Td>{s.strategy}</Td>
                  <Td>{s.total_trades}</Td>
                  <Td>{fmt(s.win_rate)}%</Td>
                  <Td
                    className={
                      (s.total_pnl || 0) >= 0
                        ? "text-[var(--color-success)]"
                        : "text-[var(--color-danger)]"
                    }
                  >
                    ${fmt(s.total_pnl)}
                  </Td>
                  <Td>${fmt(s.best_trade)}</Td>
                  <Td>${fmt(s.worst_trade)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
}
