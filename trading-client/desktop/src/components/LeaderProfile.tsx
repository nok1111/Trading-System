/** Leader Profile — detailed view with equity curve, stats, and signal history. */

import { useEffect, useState, useCallback } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  Award,
  TrendingUp,
  Target,
  Zap,
  Activity,
  DollarSign,
  UserPlus,
} from "lucide-react";
import { cn, fmtDateShort } from "../lib/utils";
import { Card } from "./ui/Card";
import { Button } from "./ui/Button";
import { Table, Th, Td, Tr } from "./ui/Table";
import { Badge } from "./ui/Badge";
import { toast } from "./ui/Toast";
import { CryptoIcon } from "./CryptoIcon";
import * as socialApi from "../lib/socialApi";
import type { LeaderProfile as LeaderProfileData } from "../lib/socialApi";

export function LeaderProfile({
  leaderId,
  onBack,
}: {
  leaderId: number;
  onBack: () => void;
}) {
  const [profile, setProfile] = useState<LeaderProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [followLoading, setFollowLoading] = useState(false);
  const [signalFilter, setSignalFilter] = useState<"all" | "active" | "closed">("all");

  const load = useCallback(async () => {
    try {
      const r = await socialApi.getLeaderProfile(leaderId);
      setProfile(r);
    } catch (e: any) {
      toast(e.message || "Error al cargar perfil", false);
    } finally {
      setLoading(false);
    }
  }, [leaderId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleFollow = async () => {
    setFollowLoading(true);
    try {
      await socialApi.followLeader({ leader_id: leaderId });
      toast("Siguiendo al líder");
      load();
    } catch (e: any) {
      toast(e.message || "Error al seguir", false);
    } finally {
      setFollowLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-[13px] text-[var(--color-text-muted)]">Cargando perfil...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Award size={32} className="text-[var(--color-text-muted)] opacity-50" />
        <div className="text-[13px] text-[var(--color-text-muted)]">Líder no encontrado</div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft size={14} /> Volver
        </Button>
      </div>
    );
  }

  const filteredSignals = profile.recent_signals.filter((s) => {
    if (signalFilter === "active") return s.status === "active";
    if (signalFilter === "closed") return s.status === "closed" || s.status === "cancelled";
    return true;
  });

  const equityData = profile.equity_curve.map((p) => ({
    t: fmtDateShort(p.timestamp),
    v: p.equity,
  }));

  const roiPositive = profile.roi_30d >= 0;

  return (
    <div className="space-y-4">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-[11px] font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
      >
        <ArrowLeft size={14} /> Volver al leaderboard
      </button>

      {/* Header card */}
      <Card>
        <div className="p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-14 h-14 rounded-full bg-[var(--color-primary)]/20 flex items-center justify-center text-[20px] font-bold text-[var(--color-primary)]">
                {profile.display_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <h2 className="text-[18px] font-bold text-[var(--color-text)]">{profile.display_name}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="primary" className="!text-[9px] uppercase">{profile.broker_id}</Badge>
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    {profile.total_followers} followers
                  </span>
                  {profile.is_public && (
                    <span className="text-[9px] text-[var(--color-success)] font-bold">PUBLIC</span>
                  )}
                </div>
                {profile.bio && (
                  <p className="text-[11px] text-[var(--color-text-muted)] mt-2 max-w-md">{profile.bio}</p>
                )}
              </div>
            </div>
            <Button variant="primary" onClick={handleFollow} disabled={followLoading} className="!h-9">
              <UserPlus size={14} /> {followLoading ? "Siguiendo..." : "Seguir"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          icon={<TrendingUp size={14} />}
          label="ROI 30d"
          value={`${roiPositive ? "+" : ""}${profile.roi_30d.toFixed(2)}%`}
          positive={roiPositive}
        />
        <StatCard
          icon={<Target size={14} />}
          label="Win Rate"
          value={`${profile.win_rate.toFixed(0)}%`}
          sub={`${profile.wins}W / ${profile.losses}L`}
        />
        <StatCard
          icon={<Activity size={14} />}
          label="Trades"
          value={String(profile.total_trades)}
          sub={`${profile.open_positions} activos`}
        />
        <StatCard
          icon={<DollarSign size={14} />}
          label="Equity"
          value={`$${profile.latest_equity_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`PnL: $${profile.total_pnl_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
      </div>

      {/* Secondary stats */}
      <div className="grid grid-cols-6 gap-2">
        <MiniStat label="ROI 90d" value={`${profile.roi_90d.toFixed(1)}%`} positive={profile.roi_90d >= 0} />
        <MiniStat label="ROI Total" value={`${profile.roi_all.toFixed(1)}%`} positive={profile.roi_all >= 0} />
        <MiniStat label="Max DD" value={`${profile.max_drawdown.toFixed(1)}%`} positive={false} />
        <MiniStat label="Sharpe" value={profile.sharpe_ratio.toFixed(2)} positive={profile.sharpe_ratio >= 0} />
        <MiniStat label="Best" value={`+${profile.best_trade_pct.toFixed(1)}%`} positive={true} />
        <MiniStat label="Worst" value={`${profile.worst_trade_pct.toFixed(1)}%`} positive={false} />
      </div>

      {/* Equity curve */}
      <Card>
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[12px] font-bold text-[var(--color-text)] flex items-center gap-1.5">
              <TrendingUp size={13} className="text-[var(--color-primary)]" />
              Equity Curve (30 días)
            </h3>
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {profile.equity_curve.length} puntos
            </span>
          </div>
          {equityData.length > 1 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={equityData}>
                <defs>
                  <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" opacity={0.3} />
                <XAxis dataKey="t" tick={{ fontSize: 9, fill: "var(--color-text-muted)" }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 9, fill: "var(--color-text-muted)" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
                  width={60}
                />
                <RTooltip
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "8px",
                    fontSize: "11px",
                  }}
                  formatter={(v: any) => [`$${Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`, "Equity"]}
                />
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  fill="url(#equityGrad)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-[11px] text-[var(--color-text-muted)]">
              Sin datos de equity suficientes todavía
            </div>
          )}
        </div>
      </Card>

      {/* Signal history */}
      <Card>
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[12px] font-bold text-[var(--color-text)] flex items-center gap-1.5">
              <Zap size={13} className="text-[var(--color-primary)]" />
              Historial de Señales
            </h3>
            {/* Filter buttons */}
            <div className="flex gap-1">
              {(["all", "active", "closed"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setSignalFilter(f)}
                  className={cn(
                    "px-2 h-6 rounded-[5px] text-[9px] font-bold transition-colors",
                    signalFilter === f
                      ? "bg-[var(--color-primary)] text-white"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
                  )}
                >
                  {f === "all" ? "Todas" : f === "active" ? "Activas" : "Cerradas"}
                </button>
              ))}
            </div>
          </div>

          {filteredSignals.length === 0 ? (
            <div className="text-center py-12 text-[11px] text-[var(--color-text-muted)]">
              No hay señales {signalFilter !== "all" ? (signalFilter === "active" ? "activas" : "cerradas") : ""}
            </div>
          ) : (
            <Table>
              <thead>
                <Tr>
                  <Th>Símbolo</Th>
                  <Th>Side</Th>
                  <Th>Entry</Th>
                  <Th>SL</Th>
                  <Th>TP</Th>
                  <Th>PnL</Th>
                  <Th>Estado</Th>
                  <Th>Fecha</Th>
                </Tr>
              </thead>
              <tbody>
                {filteredSignals.map((s) => (
                  <Tr key={s.id}>
                    <Td>
                      <div className="flex items-center gap-1.5">
                        <CryptoIcon symbol={s.symbol} size={16} />
                        <span className="font-bold text-[11px]">{s.symbol}</span>
                      </div>
                    </Td>
                    <Td>
                      <span
                        className={cn(
                          "text-[10px] font-bold px-1.5 py-0.5 rounded",
                          s.side === "BUY"
                            ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
                            : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
                        )}
                      >
                        {s.side}
                      </span>
                    </Td>
                    <Td className="text-[10px]">{s.entry_price ? `$${s.entry_price}` : "—"}</Td>
                    <Td className="text-[10px] text-[var(--color-danger)]">{s.stop_loss ? `$${s.stop_loss}` : "—"}</Td>
                    <Td className="text-[10px] text-[var(--color-success)]">{s.take_profit ? `$${s.take_profit}` : "—"}</Td>
                    <Td className={cn("font-bold text-[10px]", s.pnl_pct > 0 ? "text-[var(--color-success)]" : s.pnl_pct < 0 ? "text-[var(--color-danger)]" : "text-[var(--color-text-muted)]")}>
                      {s.pnl_pct !== 0 ? `${s.pnl_pct > 0 ? "+" : ""}${s.pnl_pct.toFixed(2)}%` : "—"}
                    </Td>
                    <Td>
                      <Badge
                        variant={s.status === "active" ? "success" : s.status === "closed" ? "default" : "danger"}
                        className="!text-[9px]"
                      >
                        {s.status}
                      </Badge>
                    </Td>
                    <Td className="text-[9px] text-[var(--color-text-muted)]">
                      {fmtDateShort(s.created_at)}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>
      </Card>
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  positive,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  return (
    <Card>
      <div className="p-3">
        <div className="flex items-center gap-1.5 text-[var(--color-text-muted)] mb-1">
          {icon}
          <span className="text-[9px] font-bold uppercase">{label}</span>
        </div>
        <div
          className={cn(
            "text-[16px] font-bold",
            positive === true ? "text-[var(--color-success)]" : positive === false ? "text-[var(--color-danger)]" : "text-[var(--color-text)]"
          )}
        >
          {value}
        </div>
        {sub && <div className="text-[9px] text-[var(--color-text-muted)] mt-0.5">{sub}</div>}
      </div>
    </Card>
  );
}

function MiniStat({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <Card>
      <div className="p-2 text-center">
        <div className="text-[8px] font-bold text-[var(--color-text-muted)] uppercase mb-0.5">{label}</div>
        <div
          className={cn(
            "text-[11px] font-bold",
            positive === true ? "text-[var(--color-success)]" : positive === false ? "text-[var(--color-danger)]" : "text-[var(--color-text)]"
          )}
        >
          {value}
        </div>
      </div>
    </Card>
  );
}
