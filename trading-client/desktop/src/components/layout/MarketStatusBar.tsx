import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Activity, DollarSign, Bell } from "lucide-react";
import { cn } from "../../lib/utils";
import { AccountSelector } from "../brokers/AccountSelector";
import { DataUnavailable } from "../common/DataUnavailable";
import { getMarketOverview, getFearGreed, getDominance, getAlerts } from "../../lib/intelligenceApi";
import type { MarketOverview, FearGreedData, DominanceData } from "../../lib/intelligenceTypes";

export function MarketStatusBar() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);
  const [dominance, setDominance] = useState<DominanceData | null>(null);
  const [alertCount, setAlertCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [ov, fg, dom, alerts] = await Promise.all([
          getMarketOverview(),
          getFearGreed(),
          getDominance(),
          getAlerts(1),
        ]);
        if (!alive) return;
        setOverview(ov);
        setFearGreed(fg);
        setDominance(dom);
        setAlertCount(alerts.length);
      } catch {
        // graceful degradation
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const riskOn = overview?.riskOnOff === "risk_on";

  return (
    <div className="flex items-center gap-3 px-4 h-12 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex-shrink-0">
      {/* Risk On/Off */}
      <div className="flex items-center gap-1.5">
        {loading ? (
          <div className="h-5 w-16 rounded-[6px] bg-[var(--color-surface-2)] animate-pulse" />
        ) : overview ? (
          <span
            className={cn(
              "flex items-center gap-1 px-2 h-6 rounded-[6px] text-[11px] font-bold uppercase tracking-wide",
              riskOn
                ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                : "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
            )}
          >
            {riskOn ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {riskOn ? "Risk On" : "Risk Off"}
          </span>
        ) : (
          <DataUnavailable label="Risk" />
        )}
      </div>

      <div className="w-px h-5 bg-[var(--color-border)]" />

      {/* Fear & Greed */}
      <div className="flex items-center gap-1.5">
        {loading ? (
          <div className="h-5 w-20 rounded-[6px] bg-[var(--color-surface-2)] animate-pulse" />
        ) : fearGreed ? (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-[var(--color-text-muted)]">
            <Activity size={12} />
            F&G: <span className="font-bold text-[var(--color-text)]">{fearGreed.value}</span>
            <span className="text-[10px]">{fearGreed.classification}</span>
          </span>
        ) : (
          <DataUnavailable label="F&G" />
        )}
      </div>

      <div className="w-px h-5 bg-[var(--color-border)]" />

      {/* BTC Dominance */}
      <div className="flex items-center gap-1.5">
        {loading ? (
          <div className="h-5 w-20 rounded-[6px] bg-[var(--color-surface-2)] animate-pulse" />
        ) : dominance ? (
          <span className="flex items-center gap-1 text-[11px] font-semibold text-[var(--color-text-muted)]">
            <DollarSign size={12} />
            BTC.D: <span className="font-bold text-[var(--color-text)]">{dominance.btc.toFixed(1)}%</span>
          </span>
        ) : (
          <DataUnavailable label="BTC.D" />
        )}
      </div>

      <div className="flex-1" />

      {/* Account selector */}
      <AccountSelector />

      {/* Alerts */}
      <div className="flex items-center gap-1.5">
        <Bell size={14} className="text-[var(--color-text-muted)]" />
        <span className="text-[11px] font-bold text-[var(--color-text)]">{alertCount}</span>
      </div>
    </div>
  );
}
