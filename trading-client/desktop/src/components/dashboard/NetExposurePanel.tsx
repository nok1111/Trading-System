import { useEffect, useState, useCallback } from "react";
import { Scale } from "lucide-react";
import { getNetExposure, type NetExposure } from "../../lib/portfolioApi";

export function NetExposurePanel() {
  const [data, setData] = useState<NetExposure | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const d = await getNetExposure();
      setData(d);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading || !data) {
    return (
      <div className="panel p-4 min-h-[120px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px]">Cargando exposición...</div>
      </div>
    );
  }

  if (data.by_asset.length === 0) {
    return (
      <div className="panel p-4 min-h-[120px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px]">Sin posiciones abiertas</div>
      </div>
    );
  }

  const totalUsd = data.total_long_usd + data.total_short_usd;
  const longPct = totalUsd > 0 ? (data.total_long_usd / totalUsd) * 100 : 0;
  const shortPct = totalUsd > 0 ? (data.total_short_usd / totalUsd) * 100 : 0;

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Scale size={16} className="text-[var(--color-text-muted)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Exposición Neta</h3>
      </div>

      {/* Long vs Short bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-[11px] mb-1">
          <span className="text-[var(--color-success)] font-semibold">
            Long: ${data.total_long_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </span>
          <span className="text-[var(--color-danger)] font-semibold">
            Short: ${data.total_short_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div className="h-2 rounded-full bg-[var(--color-surface-2)] overflow-hidden flex">
          <div
            className="h-full bg-[var(--color-success)] transition-all"
            style={{ width: `${longPct}%` }}
          />
          <div
            className="h-full bg-[var(--color-danger)] transition-all"
            style={{ width: `${shortPct}%` }}
          />
        </div>
      </div>

      {/* Per-asset exposure */}
      <div className="space-y-1.5">
        {data.by_asset.slice(0, 8).map((asset) => (
          <div key={asset.asset} className="flex items-center gap-2 text-[12px]">
            <span className="font-semibold text-[var(--color-text)] w-12">{asset.asset}</span>
            <div className="flex-1 flex items-center gap-1">
              {asset.net_side === "long" ? (
                <span className="text-[var(--color-success)] font-mono">
                  +{asset.net_quantity.toFixed(4)}
                </span>
              ) : asset.net_side === "short" ? (
                <span className="text-[var(--color-danger)] font-mono">
                  {asset.net_quantity.toFixed(4)}
                </span>
              ) : (
                <span className="text-[var(--color-text-muted)] font-mono">flat</span>
              )}
              <span className="text-[10px] text-[var(--color-text-muted)]">
                (${asset.usd_value.toLocaleString("en-US", { maximumFractionDigits: 0 })})
              </span>
            </div>
            <span className="text-[10px] text-[var(--color-text-muted)]">
              {asset.brokers.length} {asset.brokers.length === 1 ? "broker" : "brokers"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
