import { useEffect, useState, useCallback } from "react";
import { Grid3x3 } from "lucide-react";
import { getConcentration, type ConcentrationAnalysis } from "../../lib/portfolioApi";

export function PortfolioHeatmap() {
  const [data, setData] = useState<ConcentrationAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const d = await getConcentration();
      setData(d);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading || !data) {
    return (
      <div className="panel p-4 min-h-[120px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px]">Cargando heatmap...</div>
      </div>
    );
  }

  if (data.by_asset.length === 0) {
    return (
      <div className="panel p-4 min-h-[120px] flex items-center justify-center">
        <div className="text-[var(--color-text-muted)] text-[12px]">Sin datos para mostrar</div>
      </div>
    );
  }

  const maxPct = Math.max(...data.by_asset.map((a) => a.percentage), 1);

  // Color: green for high concentration (more value), fading to muted
  const getBgColor = (pct: number) => {
    const intensity = Math.min(pct / maxPct, 1);
    const alpha = 0.15 + intensity * 0.5;
    return `rgba(34, 197, 94, ${alpha})`;
  };

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Grid3x3 size={16} className="text-[var(--color-text-muted)]" />
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Heatmap por Asset</h3>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {data.by_asset.slice(0, 16).map((item) => (
          <div
            key={item.asset}
            className="rounded-lg p-3 text-center transition-all hover:scale-105 cursor-default"
            style={{ backgroundColor: getBgColor(item.percentage) }}
            title={`${item.asset}: $${item.usd_value.toFixed(2)} (${item.percentage.toFixed(1)}%)`}
          >
            <div className="text-[14px] font-bold text-[var(--color-text)]">{item.asset}</div>
            <div className="text-[11px] text-[var(--color-text-muted)]">
              {item.percentage.toFixed(1)}%
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
              ${item.usd_value < 1000 ? item.usd_value.toFixed(2) : (item.usd_value / 1000).toFixed(1) + "k"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
