import { useEffect, useState, useCallback } from "react";
import { Activity, Fuel, Waves, ArrowDownUp, RefreshCw, Loader2 } from "lucide-react";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { fmtVol } from "../../lib/utils";
import {
  getDefiTvl,
  getGasTracker,
  getWhaleMovements,
  getExchangeFlows,
  type TvlData,
  type GasData,
  type WhaleData,
  type ExchangeFlowData,
} from "../../lib/defiApi";

export function OnChainAnalytics() {
  const [tvl, setTvl] = useState<TvlData | null>(null);
  const [gas, setGas] = useState<GasData | null>(null);
  const [whales, setWhales] = useState<WhaleData | null>(null);
  const [flows, setFlows] = useState<ExchangeFlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [tvlRes, gasRes, whaleRes, flowRes] = await Promise.allSettled([
        getDefiTvl(),
        getGasTracker(),
        getWhaleMovements(),
        getExchangeFlows(),
      ]);
      setTvl(tvlRes.status === "fulfilled" ? tvlRes.value : null);
      setGas(gasRes.status === "fulfilled" ? gasRes.value : null);
      setWhales(whaleRes.status === "fulfilled" ? whaleRes.value : null);
      setFlows(flowRes.status === "fulfilled" ? flowRes.value : null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">On-Chain Analytics</h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-[var(--color-primary)]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* TVL */}
      <div className="panel p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-[var(--color-primary)]" />
            <h3 className="text-[14px] font-bold text-[var(--color-text)]">DeFi TVL</h3>
          </div>
          {tvl && !tvl.error && (
            <span className="text-[18px] font-bold text-[var(--color-success)]">
              ${fmtVol(tvl.total_tvl_usd)}
            </span>
          )}
        </div>
        {tvl?.error ? (
          <div className="text-[12px] text-[var(--color-danger)]">{tvl.error}</div>
        ) : tvl ? (
          <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
            {tvl.chains.slice(0, 8).map((c) => (
              <div key={c.name} className="flex items-center justify-between text-[12px]">
                <span className="font-semibold text-[var(--color-text)]">{c.name}</span>
                <span className="text-[var(--color-text-muted)]">${fmtVol(c.tvl_usd)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {/* Gas Tracker */}
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Fuel size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Gas Tracker (ETH)</h3>
        </div>
        {gas?.error ? (
          <div className="text-[12px] text-[var(--color-danger)]">{gas.error}</div>
        ) : gas ? (
          <div className="grid grid-cols-3 gap-3">
            {gas.fast != null && (
              <GasCard label="Fast" value={gas.fast} unit={gas.unit} color="var(--color-danger)" />
            )}
            {gas.average != null && (
              <GasCard label="Average" value={gas.average} unit={gas.unit} color="var(--color-warning)" />
            )}
            {gas.safe_low != null && (
              <GasCard label="Safe Low" value={gas.safe_low} unit={gas.unit} color="var(--color-success)" />
            )}
            {gas.base_fee != null && (
              <GasCard label="Base Fee" value={gas.base_fee} unit={gas.unit} color="var(--color-primary)" />
            )}
          </div>
        ) : null}
        {gas && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-2">
            Fuente: {gas.source}
          </div>
        )}
      </div>

      {/* Whale Movements */}
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Waves size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Whale Movements</h3>
        </div>
        {whales?.error ? (
          <div className="text-[12px] text-[var(--color-danger)]">{whales.error}</div>
        ) : whales && whales.transactions.length > 0 ? (
          <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
            {whales.transactions.slice(0, 8).map((tx, i) => (
              <div key={i} className="flex items-center justify-between text-[12px] px-2 py-1.5 rounded-lg bg-[var(--color-surface-2)]">
                <div className="flex items-center gap-2">
                  <Badge variant="primary">{(tx as any).protocol || (tx as any).blockchain || "—"}</Badge>
                  <span className="text-[var(--color-text-muted)] truncate max-w-[120px]">
                    {(tx as any).chain || (tx as any).symbol || ""}
                  </span>
                </div>
                <span className="font-semibold text-[var(--color-text)]">
                  {(tx as any).tvl_usd ? `$${fmtVol((tx as any).tvl_usd)}` : (tx as any).amount_usd ? `$${fmtVol((tx as any).amount_usd)}` : "—"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-[12px] text-[var(--color-text-muted)] text-center py-4">Sin datos</div>
        )}
        {whales?.note && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-2">{whales.note}</div>
        )}
      </div>

      {/* Exchange Flows */}
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <ArrowDownUp size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Exchange Flows</h3>
        </div>
        {flows?.error ? (
          <div className="text-[12px] text-[var(--color-danger)]">{flows.error}</div>
        ) : flows ? (
          <div className="space-y-2">
            {flows.total_cex_tvl != null && (
              <div className="flex justify-between text-[12px]">
                <span className="text-[var(--color-text-muted)]">CEX TVL total</span>
                <span className="font-bold text-[var(--color-success)]">${fmtVol(flows.total_cex_tvl)}</span>
              </div>
            )}
            {flows.flows && flows.flows.map((f, i) => (
              <div key={i} className="flex justify-between text-[12px]">
                <span className="text-[var(--color-text-muted)]">{f.chain}</span>
                <span className="font-semibold">${fmtVol(f.tvl_usd)}</span>
              </div>
            ))}
            {flows.note && (
              <div className="text-[10px] text-[var(--color-text-muted)]">{flows.note}</div>
            )}
          </div>
        ) : null}
      </div>

      {/* Refresh button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => fetchData(true)}
        disabled={refreshing}
        className="w-full"
      >
        <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
        Actualizar
      </Button>
    </div>
  );
}

function GasCard({ label, value, unit, color }: { label: string; value: number; unit: string; color: string }) {
  return (
    <div className="rounded-lg p-2.5 text-center" style={{ backgroundColor: `${color}10` }}>
      <div className="text-[10px] font-bold uppercase" style={{ color }}>{label}</div>
      <div className="text-[18px] font-bold" style={{ color }}>{value.toFixed(1)}</div>
      <div className="text-[9px] text-[var(--color-text-muted)]">{unit}</div>
    </div>
  );
}
