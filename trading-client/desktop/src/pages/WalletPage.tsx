import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "../lib/api";
import { useLivePrices } from "../hooks/useLivePrices";
import { useBrokerContext } from "../context/BrokerContext";
import { isBrokerConnected } from "../lib/brokerTypes";
import { Card } from "../components/ui/Card";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { Badge } from "../components/ui/Badge";
import { fmt } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import {
  TrendingUp,
  TrendingDown,
  Coins,
  DollarSign,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

interface BrokerAsset {
  asset: string;
  free: string;
  locked: string;
}

interface BrokerBalance {
  assets: BrokerAsset[];
  total_usd: number;
  total_mxn: number;
  error?: string;
}

interface Position {
  id: number;
  symbol: string;
  side: string;
  quantity: string;
  entry_price: string;
  current_price: string;
  unrealized_pnl: string;
  status: string;
}

export function WalletPage() {
  const { connectedAccounts } = useBrokerContext();
  const firstConnectedBroker = connectedAccounts.find((a) => isBrokerConnected(a.status));
  const activeBrokerId = firstConnectedBroker?.brokerId || null;

  const [balance, setBalance] = useState<BrokerBalance | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Real-time prices via WebSocket
  const { prices: wsPrices } = useLivePrices([], 10000);
  const prices = useMemo(() => {
    return Object.entries(wsPrices).map(([symbol, price]) => ({ symbol, price }));
  }, [wsPrices]);

  const loadData = useCallback(async () => {
    try {
      if (activeBrokerId) {
        const b = await api<any>(`/api/broker/${activeBrokerId}/balance`);
        setBalance(b);
      } else {
        setBalance(null);
      }
    } catch {}
    try {
      const p = await api<any>("/api/positions");
      setPositions(Array.isArray(p) ? p : []);
    } catch {}
    setLoading(false);
    setRefreshing(false);
  }, [activeBrokerId]);

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 15000);
    return () => clearInterval(id);
  }, [loadData]);

  const priceOf = useCallback(
    (asset: string) => {
      const STABLES = ["USDT", "BUSD", "USDC", "USD", "FDUSD", "TUSD", "UST", "USDP", "GUSD"];
      if (STABLES.includes(asset)) return 1;
      // Try multiple quote currencies
      const QUOTES = ["USDT", "USDC", "USD", "FDUSD", "TUSD", "BUSD"];
      for (const q of QUOTES) {
        const t = (prices ?? []).find((p) => p.symbol === `${asset}${q}`);
        if (t && Number(t.price) > 0) return Number(t.price);
      }
      return 0;
    },
    [prices]
  );

  const enrichedAssets = useMemo(() => {
    if (balance?.assets && balance.assets.length > 0) {
      return balance.assets
        .map((b) => {
          const free = parseFloat(b.free || "0");
          const locked = parseFloat(b.locked || "0");
          const total = free + locked;
          const px = priceOf(b.asset);
          const usd = total * px;
          return { asset: b.asset, free, locked, total, price: px, usd };
        })
        .filter((a) => a.total > 0)
        .sort((a, b) => b.usd - a.usd);
    }
    // Derive from positions
    return (positions ?? [])
      .filter((p) => p.status === "open")
      .map((p) => {
        const qty = Number(p.quantity || 0);
        const px = Number(p.current_price || p.entry_price || 0);
        return {
          asset: p.symbol,
          free: qty,
          locked: 0,
          total: qty,
          price: px,
          usd: qty * px,
        };
      })
      .sort((a, b) => b.usd - a.usd);
  }, [balance, positions, priceOf]);

  const totalUsd = useMemo(() => {
    if (balance?.total_usd && balance.total_usd > 0) return balance.total_usd;
    return enrichedAssets.reduce((a, b) => a + b.usd, 0);
  }, [balance, enrichedAssets]);

  const openPositions = useMemo(
    () => (positions ?? []).filter((p) => p.status === "open"),
    [positions]
  );

  const totalUnrealizedPnl = useMemo(
    () => openPositions.reduce((a, p) => a + Number(p.unrealized_pnl || 0), 0),
    [openPositions]
  );

  const pnlPositive = totalUnrealizedPnl >= 0;

  if (loading) {
    return (
      <div className="p-5 flex items-center justify-center min-h-[400px]">
        <div className="text-[var(--color-text-muted)]">Cargando wallet...</div>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[var(--color-text)]">Wallet</h2>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
            Balance detallado y exposición
          </p>
        </div>
        <button
          onClick={() => {
            setRefreshing(true);
            loadData();
          }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-3)] transition-colors text-sm text-[var(--color-text-muted)]"
        >
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          Actualizar
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Balance */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--color-primary)]/15 flex items-center justify-center">
              <DollarSign size={18} className="text-[var(--color-primary)]" />
            </div>
            <div>
              <div className="text-xs text-[var(--color-text-muted)] font-semibold uppercase tracking-wide">
                Balance Total USD
              </div>
            </div>
          </div>
          <div className="num text-2xl font-extrabold text-[var(--color-text)]">
            ${fmt(totalUsd)}
          </div>
          {balance?.total_mxn && balance.total_mxn > 0 && (
            <div className="num text-sm text-[var(--color-text-muted)] mt-1">
              ≈ ${fmt(balance.total_mxn)} MXN
            </div>
          )}
        </Card>

        {/* Unrealized PnL */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                pnlPositive
                  ? "bg-[var(--color-success)]/15"
                  : "bg-[var(--color-danger)]/15"
              }`}
            >
              {pnlPositive ? (
                <TrendingUp size={18} className="text-[var(--color-success)]" />
              ) : (
                <TrendingDown size={18} className="text-[var(--color-danger)]" />
              )}
            </div>
            <div>
              <div className="text-xs text-[var(--color-text-muted)] font-semibold uppercase tracking-wide">
                PnL No Realizado
              </div>
            </div>
          </div>
          <div
            className={`num text-2xl font-extrabold ${
              pnlPositive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
            }`}
          >
            {pnlPositive ? "+" : ""}${fmt(Math.abs(totalUnrealizedPnl))}
          </div>
          <div className="text-sm text-[var(--color-text-muted)] mt-1">
            {openPositions.length} posiciones abiertas
          </div>
        </Card>

        {/* Active Assets */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--color-accent)]/15 flex items-center justify-center">
              <Coins size={18} className="text-[var(--color-accent)]" />
            </div>
            <div>
              <div className="text-xs text-[var(--color-text-muted)] font-semibold uppercase tracking-wide">
                Activos Activos
              </div>
            </div>
          </div>
          <div className="num text-2xl font-extrabold text-[var(--color-text)]">
            {enrichedAssets.length}
          </div>
          <div className="text-sm text-[var(--color-text-muted)] mt-1">
            {balance?.assets && balance.assets.length > 0 ? `Vía ${firstConnectedBroker?.displayName || "Broker"} API` : "Vía posiciones"}
          </div>
        </Card>
      </div>

      {/* API Key Warning */}
      {balance?.error && enrichedAssets.length === 0 && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
          <AlertCircle size={18} className="text-[var(--color-warning)] shrink-0" />
          <div className="text-sm text-[var(--color-text)]">
            {balance.error}
          </div>
        </div>
      )}

      {/* Asset Allocation Bar */}
      {enrichedAssets.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
            Distribución de Activos
          </h3>
          <div className="flex h-8 rounded-lg overflow-hidden">
            {enrichedAssets.slice(0, 8).map((a, i) => {
              const pct = (a.usd / totalUsd) * 100;
              const colors = [
                "var(--color-primary)",
                "var(--color-success)",
                "var(--color-accent)",
                "var(--color-warning)",
                "var(--color-danger)",
                "#8b5cf6",
                "#ec4899",
                "#14b8a6",
              ];
              return (
                <div
                  key={a.asset}
                  style={{
                    width: `${pct}%`,
                    backgroundColor: colors[i % colors.length],
                  }}
                  className="flex items-center justify-center text-[10px] font-bold text-white transition-all hover:opacity-80"
                  title={`${a.asset}: $${fmt(a.usd)} (${pct.toFixed(1)}%)`}
                >
                  {pct > 5 && a.asset.replace("USDT", "")}
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-3 mt-3">
            {enrichedAssets.slice(0, 8).map((a) => {
              const pct = (a.usd / totalUsd) * 100;
              return (
                <div key={a.asset} className="flex items-center gap-1.5">
                  <CryptoIcon symbol={a.asset} size={16} />
                  <span className="text-xs text-[var(--color-text-muted)] font-medium">
                    {a.asset.replace("USDT", "")} {pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Detailed Asset Table */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
          Activos Detallados
        </h3>
        <Table>
          <thead>
            <Tr>
              <Th>Activo</Th>
              <Th>Cantidad</Th>
              <Th>Disponible</Th>
              <Th>Bloqueada</Th>
              <Th>Precio USD</Th>
              <Th>Valor USD</Th>
              <Th>% del Total</Th>
            </Tr>
          </thead>
          <tbody>
            {enrichedAssets.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  <div style={{ textAlign: "center", padding: "8px" }}>Sin activos disponibles</div>
                </Td>
              </Tr>
            ) : (
              enrichedAssets.map((a) => (
                <Tr key={a.asset}>
                  <Td className="font-semibold">
                    <div className="flex items-center gap-2">
                      <CryptoIcon symbol={a.asset} size={28} />
                      {a.asset}
                    </div>
                  </Td>
                  <Td className="num">{a.total.toFixed(8)}</Td>
                  <Td className="num text-[var(--color-success)]">{a.free.toFixed(8)}</Td>
                  <Td className="num text-[var(--color-warning)]">{a.locked.toFixed(8)}</Td>
                  <Td className="num">${fmt(a.price)}</Td>
                  <Td className="num font-bold">${fmt(a.usd)}</Td>
                  <Td className="num">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-[var(--color-surface-3)] overflow-hidden">
                        <div
                          className="h-full bg-[var(--color-primary)] rounded-full"
                          style={{ width: `${(a.usd / totalUsd) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {((a.usd / totalUsd) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </Card>

      {/* Open Positions as Assets */}
      {openPositions.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">
            Posiciones Abiertas
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {openPositions.map((p) => {
              const qty = Number(p.quantity || 0);
              const entry = Number(p.entry_price || 0);
              const current = Number(p.current_price || 0);
              const pnl = Number(p.unrealized_pnl || 0);
              const pnlPct = entry > 0 ? ((current - entry) / entry) * 100 : 0;
              const isProfit = pnl >= 0;
              const usdValue = qty * current;

              return (
                <div
                  key={p.id}
                  className="p-4 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-primary)]/40 transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <CryptoIcon symbol={p.symbol} size={32} />
                      <div>
                        <div className="font-bold text-sm text-[var(--color-text)]">
                          {p.symbol}
                        </div>
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">
                          {p.side}
                        </div>
                      </div>
                    </div>
                    <Badge variant={isProfit ? "success" : "danger"}>
                      {isProfit ? "+" : ""}
                      {pnlPct.toFixed(2)}%
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--color-text-muted)]">Cantidad</span>
                      <span className="num font-semibold">{qty}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--color-text-muted)]">Entrada</span>
                      <span className="num">${fmt(entry)}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--color-text-muted)]">Actual</span>
                      <span className="num font-semibold">${fmt(current)}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--color-text-muted)]">Valor USD</span>
                      <span className="num font-bold">${fmt(usdValue)}</span>
                    </div>
                    <div className="flex justify-between text-xs pt-2 border-t border-[var(--color-border)]">
                      <span className="text-[var(--color-text-muted)]">PnL</span>
                      <span
                        className={`num font-bold ${
                          isProfit
                            ? "text-[var(--color-success)]"
                            : "text-[var(--color-danger)]"
                        }`}
                      >
                        {isProfit ? "+" : ""}${fmt(Math.abs(pnl))}
                      </span>
                    </div>
                  </div>

                  {/* PnL Bar */}
                  <div className="mt-3">
                    <div className="relative h-1.5 rounded-full bg-[var(--color-surface-3)] overflow-hidden">
                      <div
                        className={`absolute top-0 left-1/2 h-full rounded-full ${
                          isProfit
                            ? "bg-[var(--color-success)]"
                            : "bg-[var(--color-danger)]"
                        }`}
                        style={{
                          width: `${Math.min(Math.abs(pnlPct) * 2, 50)}%`,
                          transform: isProfit ? "translateX(0)" : "translateX(-100%)",
                        }}
                      />
                      <div className="absolute top-0 left-1/2 w-px h-full bg-[var(--color-border)]" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
