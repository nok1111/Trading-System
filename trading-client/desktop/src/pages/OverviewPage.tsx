import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  ArrowLeftRight,
  Bot,
  Coins,
  Layers,
  Power,
  Repeat,
  RefreshCw,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../lib/api";
import { Panel, StatCard } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { toast } from "../components/ui/Toast";
import { cn, fmt, fmtDate, nowTime } from "../lib/utils";

const PIE_COLORS = [
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-success)",
  "var(--color-warning)",
  "var(--color-cyan)",
  "var(--color-danger)",
];

const RANGES = [
  { label: "20", n: 20 },
  { label: "50", n: 50 },
  { label: "100", n: 100 },
  { label: "Todo", n: 9999 },
];

interface HealthResponse {
  status: string;
  trading_mode: string;
  live_trading_enabled: boolean;
}

interface Snapshot {
  id: number;
  timestamp: string;
  equity: any;
  cash: any;
  total_pnl: any;
  total_equity?: any;
  positions_value?: any;
  open_positions_count: number;
}

interface Stats {
  trades_closed: number;
  open_positions: number;
  total_pnl: number;
  win_rate: number;
  wins: number;
  losses: number;
}

interface BinanceBalance {
  assets: { asset: string; free: string; locked: string }[];
  total_usd: number;
  total_mxn: number;
  error?: string;
}

export function OverviewPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [balance, setBalance] = useState<BinanceBalance | null>(null);
  const [allocatedCapital, setAllocatedCapital] = useState<number>(0);
  const [capitalInput, setCapitalInput] = useState("");
  const [signals, setSignals] = useState<any[]>([]);
  const [aiLog, setAiLog] = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const [prices, setPrices] = useState<any[]>([]);
  const [txFilter, setTxFilter] = useState<"ALL" | "BUY" | "SELL">("ALL");
  const [rangeN, setRangeN] = useState(20);
  const sparkRef = useRef<Record<string, number[]>>({});

  const loadData = useCallback(async () => {
    try {
      const h = await api<HealthResponse>("/health");
      setHealth(h);
    } catch {}
    try {
      const s = await api<any>("/api/snapshots");
      console.log("SNAPSHOTS:", Array.isArray(s) ? s.length : typeof s, s?.[0]);
      setSnapshots(Array.isArray(s) ? s.slice(-200) : []);
    } catch (e) { console.log("SNAPSHOTS ERROR:", e); }
    try {
      const p = await api<any>("/api/positions");
      setPositions(Array.isArray(p) ? p : []);
    } catch {}
    try {
      const pr = await api<any>("/api/prices/live");
      const priceList = Array.isArray(pr)
        ? pr
        : pr?.prices
          ? Object.entries(pr.prices).map(([symbol, price]) => ({ symbol, price }))
          : [];
      setPrices(priceList);
      for (const t of priceList) {
        const arr = sparkRef.current[t.symbol] || [];
        arr.push(Number(t.price) || 0);
        if (arr.length > 40) arr.shift();
        sparkRef.current[t.symbol] = arr;
      }
    } catch {}
    try {
      const st = await api<any>("/api/stats");
      setStats(st?.today ?? null);
    } catch {}
    try {
      const b = await api<BinanceBalance>("/api/binance/balance");
      setBalance(b);
    } catch {}
    try {
      const sig = await api<any>("/api/signals");
      const sigArr = Array.isArray(sig) ? sig : [];
      setSignals(sigArr.slice(-10).reverse());
    } catch {}
    try {
      const log = await api<any>("/api/ai-agent/log");
      const logArr = Array.isArray(log) ? log : [];
      setAiLog(logArr.slice(-10).reverse());
    } catch {}
    try {
      const cap = await api<any>("/api/trading-mode");
      console.log("TRADING-MODE:", cap);
      setAllocatedCapital(cap?.allocated_capital ?? 0);
    } catch (e) { console.log("TRADING-MODE ERROR:", e); }
  }, []);

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 5000);
    return () => clearInterval(id);
  }, [loadData]);

  const setCapital = async () => {
    const val = parseFloat(capitalInput);
    if (isNaN(val)) return;
    try {
      await api(`/api/ai-agent/capital?amount=${val}`, {
        method: "PATCH",
      });
      setAllocatedCapital(val);
      setCapitalInput("");
      toast("Capital asignado");
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const toggleKillSwitch = async () => {
    try {
      const r = await api<any>("/api/kill-switch", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true }),
      });
      toast(r.kill_switch ? "Kill switch activado" : "Kill switch desactivado");
      loadData();
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const safeSnapshots = snapshots ?? [];
  const latestSnapshot = safeSnapshots[safeSnapshots.length - 1];
  const prevSnapshot = safeSnapshots[safeSnapshots.length - 2];

  const pnl = stats?.total_pnl ?? 0;
  const pnlUp = pnl >= 0;
  const isLive = health?.trading_mode === "live";

  const ranged = useMemo(() => (snapshots ?? []).slice(-rangeN), [snapshots, rangeN]);

  const equityData = useMemo(
    () => (ranged ?? []).map((s: any, i) => ({ i, v: Number(s.equity ?? s.total_equity ?? 0) })),
    [ranged]
  );

  const growthData = useMemo(
    () =>
      (ranged ?? []).map((s: any, i) => ({
        i: i + 1,
        cash: Number(s.cash ?? 0),
        pos: Number(s.equity ?? s.total_equity ?? 0) - Number(s.cash ?? 0),
      })),
    [ranged]
  );

  const equityDeltaPct = useMemo(() => {
    const a = prevSnapshot ? Number(prevSnapshot.equity ?? prevSnapshot.total_equity ?? 0) : 0;
    const b = latestSnapshot ? Number(latestSnapshot.equity ?? latestSnapshot.total_equity ?? 0) : 0;
    if (!a || !b) return 0;
    return ((b - a) / a) * 100;
  }, [latestSnapshot, prevSnapshot]);

  const priceOf = useCallback(
    (asset: string) => {
      if (asset === "USDT" || asset === "BUSD" || asset === "USDC") return 1;
      const t = (prices ?? []).find((p) => p.symbol === `${asset}USDT`);
      return t ? Number(t.price) || 0 : 0;
    },
    [prices]
  );

  const walletAssets = useMemo(() => {
    if (!balance?.assets) return [];
    return (balance.assets ?? [])
      .map((b) => {
        const qty = parseFloat(b.free) + parseFloat(b.locked || "0");
        const px = priceOf(b.asset);
        return { asset: b.asset, qty, usd: qty * px };
      })
      .filter((b) => b.qty > 0)
      .sort((a, b) => b.usd - a.usd)
      .slice(0, 5);
  }, [balance, priceOf]);

  const openPositions = useMemo(
    () => (positions ?? []).filter((p) => p.status === "open"),
    [positions]
  );

  const allocation = useMemo(() => {
    const items = (openPositions ?? []).map((p) => ({
      name: p.symbol as string,
      value: (p.quantity || 0) * (p.entry_price || 0),
    }));
    const cash = latestSnapshot ? Number(latestSnapshot.cash ?? 0) : 0;
    if (cash > 0) items.push({ name: "Cash", value: cash });
    return items.filter((i) => i.value > 0);
  }, [openPositions, latestSnapshot]);

  const allocTotal = allocation.reduce((a, i) => a + i.value, 0);

  const closed = useMemo(
    () => (positions ?? []).filter((p) => p.status === "closed"),
    [positions]
  );
  const grossProfit = (closed ?? []).reduce(
    (a, p) => a + Math.max(p.pnl || 0, 0),
    0
  );
  const grossLoss = (closed ?? []).reduce((a, p) => a + Math.min(p.pnl || p.realized_pnl || 0, 0), 0);

  const transactions = useMemo(() => {
    const rows = [...openPositions, ...closed]
      .sort(
        (a, b) =>
          new Date(b.opened_at || 0).getTime() -
          new Date(a.opened_at || 0).getTime()
      )
      .slice(0, 8);
    return txFilter === "ALL"
      ? rows
      : rows.filter((r) => r.side === txFilter);
  }, [openPositions, closed, txFilter]);

  const tickers = useMemo(
    () =>
      (prices ?? []).slice(0, 6).map((p) => ({
        symbol: p.symbol as string,
        price: Number(p.price) || 0,
        spark: (sparkRef.current[p.symbol] || []).map((v, i) => ({ i, v })),
      })),
    [prices]
  );

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={health?.status === "ok" ? "success" : "danger"}>
            <ShieldCheck size={11} />
            {health?.status === "ok" ? "Sistema OK" : "Error"}
          </Badge>
          <Badge variant={isLive ? "danger" : "primary"}>
            {health?.trading_mode || "..."}
          </Badge>
          {health?.live_trading_enabled && (
            <Badge variant="danger">
              <Zap size={11} />
              Live
            </Badge>
          )}
          <span className="text-[11px] text-[var(--color-text-muted)] num ml-1">
            Actualizado {nowTime()}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => loadData()}>
            <RefreshCw size={14} />
            Actualizar
          </Button>
          <Button variant="danger" size="sm" onClick={toggleKillSwitch}>
            <Power size={14} />
            Kill Switch
          </Button>
        </div>
      </div>

      {/* Row 1 — Wallet / Balance / Transacciones */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-[1.25fr_1fr_1fr] gap-4">
        <Panel
          title="Wallet"
          icon={<Wallet size={14} />}
          tone="primary"
          actions={
            <Badge variant="primary">{walletAssets.length} activos</Badge>
          }
        >
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0 space-y-2">
              {walletAssets.length === 0 ? (
                <p className="text-[12px] text-[var(--color-text-muted)] py-4">
                  Sin balances disponibles.
                </p>
              ) : (
                walletAssets.map((a, idx) => (
                  <div key={a.asset} className="flex items-center gap-2.5">
                    <span
                      className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                      style={{
                        background: `color-mix(in srgb, ${
                          PIE_COLORS[idx % PIE_COLORS.length]
                        } 16%, transparent)`,
                        color: PIE_COLORS[idx % PIE_COLORS.length],
                      }}
                    >
                      {a.asset.slice(0, 3)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-bold text-[var(--color-text)] leading-none truncate">
                        {a.asset}
                      </div>
                      <div className="num text-[11px] text-[var(--color-text-muted)] mt-1">
                        {a.qty.toFixed(6)}
                      </div>
                    </div>
                    <span className="num text-[12px] font-semibold text-[var(--color-text-secondary)]">
                      ${fmt(a.usd)}
                    </span>
                  </div>
                ))
              )}
            </div>
            <div className="w-[128px] h-[128px] flex-shrink-0 relative">
              {allocation.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={allocation}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={40}
                        outerRadius={62}
                        paddingAngle={2}
                        stroke="none"
                      >
                        {allocation.map((_, i) => (
                          <Cell
                            key={i}
                            fill={PIE_COLORS[i % PIE_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "var(--color-surface)",
                          border: "1px solid var(--color-border)",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                        formatter={(v: any, n: any) => [`$${fmt(v)}`, n]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="num text-[13px] font-extrabold text-[var(--color-text)]">
                      ${fmt(allocTotal)}
                    </span>
                    <span className="text-[9px] uppercase tracking-wide text-[var(--color-text-muted)]">
                      Total
                    </span>
                  </div>
                </>
              ) : (
                <div className="w-full h-full rounded-full border-[10px] border-[var(--color-border)]" />
              )}
            </div>
          </div>
        </Panel>

        <Panel title="Balance" icon={<Coins size={14} />} tone="success">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="num text-[26px] font-extrabold text-[var(--color-text)] leading-none truncate">
                ${fmt(latestSnapshot ? Number(latestSnapshot.equity ?? latestSnapshot.total_equity ?? 0) : undefined)}
              </div>
              <div className="flex items-center gap-1.5 mt-2">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 text-[11px] font-bold px-1.5 py-0.5 rounded-md",
                    equityDeltaPct >= 0
                      ? "bg-[var(--color-success)]/14 text-[var(--color-success)]"
                      : "bg-[var(--color-danger)]/14 text-[var(--color-danger)]"
                  )}
                >
                  {equityDeltaPct >= 0 ? (
                    <ArrowUpRight size={11} />
                  ) : (
                    <ArrowDownRight size={11} />
                  )}
                  {fmt(equityDeltaPct)}%
                </span>
                <span className="text-[11px] text-[var(--color-text-muted)]">
                  vs snapshot previo
                </span>
              </div>
            </div>
            <div className="w-[110px] h-[46px] flex-shrink-0">
              {equityData.length > 1 && (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityData}>
                    <defs>
                      <linearGradient id="balSpark" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="0%"
                          stopColor="var(--color-success)"
                          stopOpacity={0.4}
                        />
                        <stop
                          offset="100%"
                          stopColor="var(--color-success)"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="v"
                      stroke="var(--color-success)"
                      strokeWidth={1.6}
                      fill="url(#balSpark)"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-[var(--color-border)]">
            <div>
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--color-text-muted)]">
                <ArrowUpRight
                  size={12}
                  className="text-[var(--color-success)]"
                />
                Profit bruto
              </div>
              <div className="num text-[15px] font-bold text-[var(--color-success)] mt-1">
                ${fmt(grossProfit)}
              </div>
            </div>
            <div className="pl-3 divider-y">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--color-text-muted)]">
                <ArrowDownRight
                  size={12}
                  className="text-[var(--color-danger)]"
                />
                Pérdida bruta
              </div>
              <div className="num text-[15px] font-bold text-[var(--color-danger)] mt-1">
                ${fmt(Math.abs(grossLoss))}
              </div>
            </div>
          </div>
        </Panel>

        <Panel
          title="Transacciones"
          icon={<ArrowLeftRight size={14} />}
          tone="cyan"
          actions={
            <Select
              value={txFilter}
              onChange={(e) => setTxFilter(e.target.value as any)}
              className="!py-1 !text-[11px]"
            >
              <option value="ALL">Todas</option>
              <option value="BUY">Compras</option>
              <option value="SELL">Ventas</option>
            </Select>
          }
          bodyClassName="p-0"
        >
          <div className="max-h-[190px] overflow-y-auto divide-y divide-[var(--color-border)]">
            {transactions.length === 0 ? (
              <div className="px-4 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
                Sin transacciones
              </div>
            ) : (
              transactions.map((t) => {
                const buy = t.side === "BUY";
                return (
                  <div
                    key={`${t.id}-${t.status}`}
                    className="flex items-center gap-2.5 px-4 py-2 hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    <span
                      className={cn(
                        "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0",
                        buy
                          ? "bg-[var(--color-success)]/14 text-[var(--color-success)]"
                          : "bg-[var(--color-danger)]/14 text-[var(--color-danger)]"
                      )}
                    >
                      {buy ? (
                        <ArrowDownRight size={14} />
                      ) : (
                        <ArrowUpRight size={14} />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-bold text-[var(--color-text)] truncate leading-none">
                        {t.symbol}
                      </div>
                      <div className="text-[10px] text-[var(--color-text-muted)] mt-1 uppercase tracking-wide">
                        {t.side} · {t.status}
                      </div>
                    </div>
                    <span className="num text-[12px] font-semibold text-[var(--color-text-secondary)]">
                      {fmt(t.quantity)}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </Panel>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          icon={<Wallet size={17} />}
          label="Equity Total"
          value={`$${fmt(latestSnapshot ? Number(latestSnapshot.equity ?? latestSnapshot.total_equity ?? 0) : undefined)}`}
          tone="primary"
        />
        <StatCard
          icon={<Coins size={17} />}
          label="Cash"
          value={`$${fmt(latestSnapshot ? Number(latestSnapshot.cash ?? 0) : undefined)}`}
          tone="cyan"
        />
        <StatCard
          icon={<Layers size={17} />}
          label="Posiciones"
          value={stats?.open_positions ?? 0}
          tone="accent"
        />
        <StatCard
          icon={pnlUp ? <TrendingUp size={17} /> : <TrendingDown size={17} />}
          label="PnL Total"
          value={`$${fmt(pnl)}`}
          tone={pnlUp ? "success" : "danger"}
          delta={{ value: pnlUp ? "▲ Profit" : "▼ Loss", positive: pnlUp }}
        />
        <StatCard
          icon={<Target size={17} />}
          label="Win Rate"
          value={`${fmt(stats?.win_rate)}%`}
          tone="warning"
        />
        <StatCard
          icon={<Repeat size={17} />}
          label="Total Trades"
          value={stats?.trades_closed ?? 0}
          tone="primary"
        />
      </div>

      {/* Row 2 — Capital del agente + Crecimiento */}
      <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-4">
        <Panel
          title="Capital del AI Agent"
          icon={<Bot size={14} />}
          tone="accent"
        >
          <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-[10px] bg-[var(--color-surface-2)]">
            <span className="text-[12px] font-semibold text-[var(--color-text-muted)]">
              Saldo Binance
            </span>
            <span className="num text-[13px] font-bold text-[var(--color-success)]">
              ${fmt(balance?.total_usd)}
            </span>
          </div>

          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-[0.06em] font-semibold text-[var(--color-text-muted)]">
              Asignado
            </div>
            <div className="num text-[24px] font-extrabold text-[var(--color-accent)] leading-tight mt-1">
              ${fmt(allocatedCapital)}
            </div>
          </div>

          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-[0.06em] font-semibold text-[var(--color-text-muted)] mb-1.5">
              Nuevo límite (USD)
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                step="0.01"
                min="0"
                placeholder="0 = todo"
                value={capitalInput}
                onChange={(e) => setCapitalInput(e.target.value)}
                className="flex-1 min-w-0"
              />
              <Button variant="primary" size="sm" onClick={setCapital}>
                Asignar
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-1.5 mt-2">
            {[25, 50, 100].map((pct) => (
              <button
                key={pct}
                onClick={() =>
                  setCapitalInput(
                    (((balance?.total_usd ?? 0) * pct) / 100).toFixed(2)
                  )
                }
                className="h-7 rounded-lg text-[11px] font-bold text-[var(--color-text-muted)] bg-[var(--color-surface-2)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                {pct}%
              </button>
            ))}
          </div>

          <p className="text-[11px] text-[var(--color-text-muted)] mt-2.5 leading-relaxed">
            Define cuánto capital puede operar el agente. 0 = sin límite.
          </p>
        </Panel>

        <Panel
          title="Crecimiento de la cuenta"
          icon={<Activity size={14} />}
          tone="primary"
          actions={
            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-[var(--color-surface-2)]">
              {RANGES.map((r) => (
                <button
                  key={r.label}
                  onClick={() => setRangeN(r.n)}
                  className={cn(
                    "px-2.5 h-6 rounded-md text-[11px] font-bold transition-colors",
                    rangeN === r.n
                      ? "bg-[var(--color-primary)] text-white"
                      : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  )}
                >
                  {r.label}
                </button>
              ))}
            </div>
          }
          bodyClassName="p-3"
        >
          {growthData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart
                data={growthData}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                barGap={2}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                  vertical={false}
                />
                <XAxis
                  dataKey="i"
                  tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                  tickFormatter={(v: any) => `$${Math.round(v)}`}
                />
                <Tooltip
                  cursor={{ fill: "var(--color-surface-hover)" }}
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 10,
                    fontSize: 12,
                  }}
                  formatter={(v: any, n: any) => [
                    `$${fmt(v)}`,
                    n === "cash" ? "Cash" : "En posiciones",
                  ]}
                />
                <Bar
                  dataKey="cash"
                  fill="var(--color-primary)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={18}
                />
                <Bar
                  dataKey="pos"
                  fill="var(--color-accent)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={18}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-[13px] text-[var(--color-text-muted)]">
              Sin snapshots todavía
            </div>
          )}
        </Panel>
      </div>

      {/* Row 3 — Ticker strip con sparkline */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {tickers.length === 0
          ? Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="panel h-[92px] flex items-center justify-center text-[11px] text-[var(--color-text-muted)]"
              >
                Conectando...
              </div>
            ))
          : tickers.map((t, idx) => {
              const first = t.spark[0]?.v ?? 0;
              const last = t.spark[t.spark.length - 1]?.v ?? 0;
              const up = last >= first;
              const color = up ? "var(--color-success)" : "var(--color-danger)";
              const pct = first ? ((last - first) / first) * 100 : 0;
              return (
                <div key={t.symbol} className="panel p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                        style={{
                          background: `color-mix(in srgb, ${
                            PIE_COLORS[idx % PIE_COLORS.length]
                          } 16%, transparent)`,
                          color: PIE_COLORS[idx % PIE_COLORS.length],
                        }}
                      >
                        {t.symbol.replace("USDT", "").slice(0, 3)}
                      </span>
                      <span className="text-[12px] font-bold text-[var(--color-text)] truncate">
                        {t.symbol}
                      </span>
                    </span>
                    <span
                      className="text-[10px] font-bold num"
                      style={{ color }}
                    >
                      {up ? "▲" : "▼"} {fmt(Math.abs(pct))}%
                    </span>
                  </div>
                  <div className="flex items-end justify-between gap-2 mt-1.5">
                    <span className="num text-[15px] font-extrabold text-[var(--color-text)] truncate">
                      ${fmt(t.price)}
                    </span>
                    <div className="w-[70px] h-[30px] flex-shrink-0">
                      {t.spark.length > 1 && (
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={t.spark}>
                            <Area
                              type="monotone"
                              dataKey="v"
                              stroke={color}
                              strokeWidth={1.5}
                              fill={color}
                              fillOpacity={0.14}
                              dot={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
      </div>

      {/* Activity feeds */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel
          title="Actividad Reciente"
          icon={<Activity size={14} />}
          tone="primary"
          actions={
            <Badge variant="primary">{signals.length}</Badge>
          }
          bodyClassName="p-0"
        >
          <div className="max-h-[260px] overflow-y-auto divide-y divide-[var(--color-border)]">
            {signals.length === 0 ? (
              <div className="px-4 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
                Esperando señales...
              </div>
            ) : (
              signals.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-3 px-4 py-2 hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <Badge
                    variant={
                      s.signal_type === "BUY"
                        ? "success"
                        : s.signal_type === "SELL"
                          ? "danger"
                          : "default"
                    }
                  >
                    {s.signal_type}
                  </Badge>
                  <span className="text-[13px] font-bold text-[var(--color-text)] flex-1 min-w-0 truncate">
                    {s.symbol}
                  </span>
                  <span className="num text-[11px] text-[var(--color-text-muted)]">
                    {fmtDate(s.timestamp)}
                  </span>
                </div>
              ))
            )}
          </div>
        </Panel>

        <Panel
          title="AI Agent — Actividad"
          icon={<Bot size={14} />}
          tone="accent"
          actions={<Badge variant="accent">{aiLog.length}</Badge>}
          bodyClassName="p-0"
        >
          <div className="max-h-[260px] overflow-y-auto divide-y divide-[var(--color-border)]">
            {aiLog.length === 0 ? (
              <div className="px-4 py-8 text-center text-[12px] text-[var(--color-text-muted)]">
                Activa el AI Agent para ver su actividad.
              </div>
            ) : (
              aiLog.map((entry, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2.5 px-4 py-2 hover:bg-[var(--color-surface-hover)] transition-colors"
                >
                  <span className="num text-[11px] text-[var(--color-text-muted)] mt-0.5 flex-shrink-0">
                    {entry.timestamp || nowTime()}
                  </span>
                  <span className="text-[12px] text-[var(--color-text)] leading-snug">
                    {entry.message || entry.action || JSON.stringify(entry)}
                  </span>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
