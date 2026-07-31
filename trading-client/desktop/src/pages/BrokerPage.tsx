import { useEffect, useState, useCallback } from "react";
import { Wallet, TrendingUp, Settings as SettingsIcon, BarChart3, History, LineChart, Layers, ChevronUp, ChevronDown } from "lucide-react";
import { api } from "../lib/api";
import { useBrokerContext } from "../context/BrokerContext";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { toast } from "../components/ui/Toast";
import { NotConnectedState } from "../components/common/NotConnectedState";
import { BrokerStatusBadge } from "../components/brokers/BrokerStatusBadge";
import { cn, fmt, fmtVol, fmtDate } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";
import { PriceChart } from "../components/charts/PriceChart";
import { SlTpPanel } from "../components/SlTpPanel";
import * as binanceProxy from "../lib/binanceProxy";
import type { BrokerAccount } from "../lib/brokerTypes";

interface BrokerPageProps {
  brokerId: string | null;
  moduleId: string | null;
  presetSymbol?: string;
}

const MODULE_LABELS: Record<string, string> = {
  overview: "Resumen",
  portfolio: "Portafolio",
  trade: "Comprar / Vender",
  markets: "Mercados",
  positions: "Posiciones",
  orders: "Órdenes",
  history: "Historial",
  earn: "Earn",
  futures: "Futures",
  config: "Configuración",
};

const MODULE_ICONS: Record<string, React.ReactNode> = {
  overview: <BarChart3 size={16} />,
  portfolio: <Wallet size={16} />,
  trade: <TrendingUp size={16} />,
  markets: <TrendingUp size={16} />,
  positions: <Layers size={16} />,
  orders: <SettingsIcon size={16} />,
  history: <History size={16} />,
  earn: <LineChart size={16} />,
  futures: <LineChart size={16} />,
  config: <SettingsIcon size={16} />,
};

export function BrokerPage({ brokerId, moduleId, presetSymbol }: BrokerPageProps) {
  const { supportedBrokers, connectedAccounts } = useBrokerContext();
  const [balanceData, setBalanceData] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [binanceActiveOrders, setBinanceActiveOrders] = useState<any[]>([]);
  const [binanceFilledOrders, setBinanceFilledOrders] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const account = brokerId ? connectedAccounts.find((a) => a.brokerId === brokerId) || null : null;
  const broker = brokerId ? supportedBrokers.find((b) => b.brokerId === brokerId) || null : null;
  const module = moduleId || "overview";

  useEffect(() => {
    if (!brokerId) return;
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const tasks: { key: string; fn: () => Promise<any> }[] = [];
        if (module === "overview" || module === "portfolio") {
          tasks.push({ key: "balance", fn: () => api<any>("/api/binance/balance").catch(() => null) });
        }
        if (module === "overview" || module === "positions") {
          tasks.push({ key: "positions", fn: () => api<any[]>("/api/positions").catch(() => []) });
        }
        if (module === "overview") {
          tasks.push({ key: "open-orders", fn: () => api<any[]>("/api/orders?status=open").catch(() => []) });
        }
        if (module === "orders") {
          tasks.push({ key: "orders", fn: () => api<any[]>("/api/orders?limit=50").catch(() => []) });
        }
        if (module === "history") {
          tasks.push({ key: "trades", fn: () => api<any[]>("/api/trades?limit=20").catch(() => []) });
        }

        if (tasks.length === 0) {
          if (alive) setLoading(false);
          return;
        }

        const results = await Promise.all(tasks.map(t => t.fn()));
        if (!alive) return;

        tasks.forEach((t, i) => {
          const data = results[i];
          if (t.key === "balance") setBalanceData(data);
          else if (t.key === "positions") setPositions(Array.isArray(data) ? data : (data?.positions || []));
          else if (t.key === "open-orders") {
            setBinanceActiveOrders(Array.isArray(data) ? data : (data?.orders || []));
          }
          else if (t.key === "orders") {
            setBinanceActiveOrders(Array.isArray(data) ? data.filter((o: any) => o.status === "open" || o.status === "pending") : (data?.active || []));
            setBinanceFilledOrders(Array.isArray(data) ? data.filter((o: any) => o.status === "filled" || o.status === "closed") : (data?.filled || []));
          }
          else if (t.key === "trades") setTrades(data || []);
        });
      } catch {
        // graceful
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [brokerId, module]);

  if (!brokerId || !broker) {
    return (
      <div className="p-5">
        <NotConnectedState brokerName="Selecciona un broker" />
      </div>
    );
  }

  if (!account) {
    return (
      <div className="p-5">
        <NotConnectedState brokerName={broker.displayName} />
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4 max-w-[1000px] mx-auto">
      {/* Broker header */}
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-[12px] bg-[var(--color-surface-2)] flex items-center justify-center text-[18px] font-extrabold text-[var(--color-text)]">
          {broker.displayName[0]}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h2 className="text-[18px] font-extrabold text-[var(--color-text)]">{broker.displayName}</h2>
            <BrokerStatusBadge status={account.status} />
          </div>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
            {account.displayName || "Cuenta"} · {account.environment} · {account.apiKeyPreview}
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--color-text-muted)]">
          {MODULE_ICONS[module]}
          {MODULE_LABELS[module] || module}
        </div>
      </div>

      {/* Module content */}
      {loading && module !== "trade" && module !== "markets" ? (
        <LoadingSkeleton lines={5} />
      ) : module === "overview" ? (
        <OverviewModule balanceData={balanceData} positions={positions} activeOrdersCount={binanceActiveOrders.length} />
      ) : module === "portfolio" ? (
        <PortfolioModule balanceData={balanceData} />
      ) : module === "trade" ? (
        <TradeModule brokerId={brokerId} presetSymbol={presetSymbol} />
      ) : module === "markets" ? (
        <MarketsModule />
      ) : module === "positions" ? (
        <PositionsModule positions={positions} brokerId={brokerId} />
      ) : module === "orders" ? (
        <OrdersModule activeOrders={binanceActiveOrders} filledOrders={binanceFilledOrders} />
      ) : module === "history" ? (
        <HistoryModule trades={trades} />
      ) : module === "config" ? (
        <ConfigModule account={account} broker={broker} />
      ) : (
        <div className="panel p-6 text-center">
          <p className="text-[14px] font-bold text-[var(--color-text)]">{MODULE_LABELS[module] || module}</p>
          <p className="text-[12px] text-[var(--color-text-muted)] mt-1">Próximamente disponible</p>
        </div>
      )}
    </div>
  );
}

function OverviewModule({ balanceData, positions, activeOrdersCount }: { balanceData: any; positions: any[]; activeOrdersCount: number }) {
  const assets: any[] = balanceData?.assets || [];
  const totalUsd = balanceData?.total_usd || 0;
  const totalMxn = balanceData?.total_mxn || 0;
  const activePositions = positions.filter((p) => p.status === "open").length;
  const activeOrders = activeOrdersCount;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="panel p-4">
          <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase">Balance Total</p>
          <p className="text-[22px] font-extrabold text-[var(--color-text)] mt-1">${fmtVol(totalUsd)}</p>
          {totalMxn > 0 && (
            <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">≈ ${fmtVol(totalMxn)} MXN</p>
          )}
        </div>
        <div className="panel p-4">
          <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase">Posiciones</p>
          <p className="text-[22px] font-extrabold text-[var(--color-text)] mt-1">{activePositions}</p>
        </div>
        <div className="panel p-4">
          <p className="text-[11px] font-semibold text-[var(--color-text-muted)] uppercase">Órdenes Activas</p>
          <p className="text-[22px] font-extrabold text-[var(--color-text)] mt-1">{activeOrders}</p>
        </div>
      </div>

      {balanceData?.error && (
        <div className="panel p-3 border-l-2 border-[var(--color-warning)]">
          <p className="text-[12px] text-[var(--color-warning)]">{balanceData.error}</p>
        </div>
      )}

      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Top Holdings</h3>
        {assets.length === 0 ? (
          <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">Sin balances disponibles</p>
        ) : (
          <div className="space-y-1.5">
            {assets.slice(0, 8).map((b, i) => (
              <div key={i} className="flex items-center gap-3 h-8">
                <span className="text-[12px] font-bold text-[var(--color-text)] w-16 truncate">{b.asset}</span>
                <span className="text-[12px] text-[var(--color-text-muted)] flex-1">{fmt(b.free)} (free) · {fmt(b.locked)} (locked)</span>
                <span className="text-[12px] font-bold text-[var(--color-text)]">${fmtVol(b.usd_value || 0)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {activePositions > 0 && (
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Posiciones Activas ({activePositions})</h3>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <th className="text-left pb-2">Symbol</th>
                <th className="text-left pb-2">Side</th>
                <th className="text-right pb-2">Qty</th>
                <th className="text-right pb-2">Entry</th>
                <th className="text-right pb-2">Current</th>
                <th className="text-right pb-2">PnL</th>
              </tr>
            </thead>
            <tbody>
              {positions.filter((p) => p.status === "open").map((p, i) => (
                <tr key={i} className="border-b border-[var(--color-border)]/50">
                  <td className="py-2 font-bold text-[var(--color-text)]">
                    <div className="flex items-center gap-1.5">
                      <CryptoIcon symbol={p.symbol} size={18} />
                      {p.symbol}
                    </div>
                  </td>
                  <td className={cn("font-bold", p.side === "long" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>{p.side}</td>
                  <td className="text-right text-[var(--color-text)]">{fmt(p.quantity)}</td>
                  <td className="text-right text-[var(--color-text-muted)]">{fmt(p.entry_price)}</td>
                  <td className="text-right text-[var(--color-text)]">{p.current_price ? fmt(p.current_price) : "—"}</td>
                  <td className={cn("text-right font-bold", Number(p.unrealized_pnl) >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                    {Number(p.unrealized_pnl) !== 0 ? fmtVol(p.unrealized_pnl) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PortfolioModule({ balanceData }: { balanceData: any }) {
  const assets: any[] = balanceData?.assets || [];
  const total = balanceData?.total_usd || 0;

  return (
    <div className="panel p-4">
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Portafolio Completo</h3>
      {balanceData?.error && (
        <p className="text-[12px] text-[var(--color-warning)] mb-3">{balanceData.error}</p>
      )}
      {assets.length === 0 ? (
        <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">Sin balances disponibles</p>
      ) : (
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
              <th className="text-left pb-2">Asset</th>
              <th className="text-right pb-2">Free</th>
              <th className="text-right pb-2">Locked</th>
              <th className="text-right pb-2">USD Value</th>
              <th className="text-right pb-2">% Total</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((b, i) => (
              <tr key={i} className="border-b border-[var(--color-border)]/50">
                <td className="py-2 font-bold text-[var(--color-text)]">
                  <div className="flex items-center gap-1.5">
                    <CryptoIcon symbol={b.asset} size={18} />
                    {b.asset}
                  </div>
                </td>
                <td className="text-right text-[var(--color-text-muted)]">{fmt(b.free)}</td>
                <td className="text-right text-[var(--color-text-muted)]">{fmt(b.locked)}</td>
                <td className="text-right font-bold text-[var(--color-text)]">${fmtVol(b.usd_value || 0)}</td>
                <td className="text-right text-[var(--color-text-muted)]">{total > 0 ? ((b.usd_value / total) * 100).toFixed(1) : 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TradeModule({ brokerId, presetSymbol }: { brokerId: string; presetSymbol?: string }) {
  const { connectedAccounts } = useBrokerContext();
  const account = connectedAccounts.find((a) => a.brokerId === brokerId);
  const [symbol, setSymbol] = useState(presetSymbol || "BTCUSDT");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [amountUsd, setAmountUsd] = useState("100");
  const [quantity, setQuantity] = useState("");
  const [limitPrice, setLimitPrice] = useState("");
  const [stopLossPrice, setStopLossPrice] = useState("");
  const [takeProfitPrice, setTakeProfitPrice] = useState("");
  const [riskPct, setRiskPct] = useState("2");
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [quoteCurrency, setQuoteCurrency] = useState("USDT");
  const [userBalance, setUserBalance] = useState<any>(null);
  const [openPositions, setOpenPositions] = useState<any[]>([]);

  const BINANCE_FEE_RATE = 0.001; // 0.1% spot fee
  const baseSymbols = ["BTC", "ETH", "SOL", "BNB", "DOGE", "AVAX", "XRP", "ADA", "LINK", "DOT"];
  const symbols = baseSymbols.map((s) => s + quoteCurrency);

  // Detect quote currency from user's balance and load balance + positions
  useEffect(() => {
    api<any>("/api/binance/balance").then((data) => {
      if (!data?.assets) return;
      setUserBalance(data);
      const stablecoins = ["USDT", "BUSD", "USDC", "FDUSD", "TUSD", "EUR", "TRY", "BRL", "MXN"];
      for (const a of data.assets) {
        if (stablecoins.includes(a.asset) && a.total > 0) {
          setQuoteCurrency(a.asset);
          break;
        }
      }
    }).catch(() => {});
    // Load open positions for P&L calculation
    api<any[]>("/api/intelligence/paper-positions").then((positions) => {
      setOpenPositions(positions || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (presetSymbol) setSymbol(presetSymbol);
  }, [presetSymbol]);

  const fetchPrice = useCallback(async () => {
    setPriceLoading(true);
    try {
      const r = await api<any>(`/api/binance/price?symbol=${symbol}`);
      if (r.price) {
        setLivePrice(r.price);
        if (orderType === "LIMIT" && !limitPrice) setLimitPrice(r.price.toString());
      }
    } catch {
      setLivePrice(null);
    }
    setPriceLoading(false);
  }, [symbol]);

  useEffect(() => {
    fetchPrice();
    const id = setInterval(fetchPrice, 10000);
    return () => clearInterval(id);
  }, [fetchPrice]);

  // Available balance for the current operation
  const baseAsset = symbol.replace(quoteCurrency, "");
  const availableUsdt = userBalance?.assets?.find((a: any) => a.asset === quoteCurrency)?.free || 0;
  const availableAsset = userBalance?.assets?.find((a: any) => a.asset === baseAsset)?.free || 0;

  // Find open position for P&L calculation (sell)
  const openPos = openPositions.find((p: any) => p.symbol === symbol && p.status === "open");
  const entryPrice = openPos ? parseFloat(openPos.entry_price) : null;
  const heldQty = openPos ? parseFloat(openPos.quantity) : 0;

  const computedQty = (() => {
    if (quantity) return parseFloat(quantity);
    if (amountUsd && livePrice && livePrice > 0) return parseFloat(amountUsd) / livePrice;
    return 0;
  })();

  // Fee and P&L calculations
  const orderValue = computedQty * (orderType === "LIMIT" && limitPrice ? parseFloat(limitPrice) : (livePrice || 0));
  const fee = orderValue * BINANCE_FEE_RATE;
  const netValue = orderValue - fee;

  // For SELL: calculate P&L if we have entry price
  const sellPnl = (side === "SELL" && entryPrice && computedQty > 0)
    ? (orderValue - fee) - (entryPrice * computedQty)
    : null;
  const sellPnlPct = (side === "SELL" && entryPrice && computedQty > 0)
    ? ((orderValue - fee) / (entryPrice * computedQty) - 1) * 100
    : null;

  // Validation
  const maxBuyUsd = availableUsdt;
  const maxSellQty = Math.min(availableAsset, heldQty || availableAsset);
  const exceedsBalance = (side === "BUY" && amountUsd && parseFloat(amountUsd) > maxBuyUsd)
    || (side === "SELL" && quantity && parseFloat(quantity) > maxSellQty);

  const handleSubmit = async () => {
    setError("");
    setResult(null);
    if (orderType === "LIMIT" && !limitPrice) {
      setError("Precio límite requerido");
      return;
    }
    if (!computedQty || computedQty <= 0) {
      setError("Cantidad inválida");
      return;
    }
    if (exceedsBalance) {
      setError(side === "BUY"
        ? `Excede tu saldo disponible de ${maxBuyUsd.toFixed(2)} ${quoteCurrency}`
        : `Excede tu saldo disponible de ${maxSellQty.toFixed(6)} ${baseAsset}`);
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = {
        symbol,
        side,
        order_type: orderType,
      };
      if (orderType === "MARKET" && side === "BUY" && amountUsd && !quantity) {
        payload.quote_order_qty = parseFloat(amountUsd);
      } else {
        payload.quantity = computedQty;
      }
      if (orderType === "LIMIT") {
        payload.price = parseFloat(limitPrice);
      }
      if (stopLossPrice) payload.stop_loss_price = parseFloat(stopLossPrice);
      if (takeProfitPrice) payload.take_profit_price = parseFloat(takeProfitPrice);

      const r = await api<any>("/api/binance/manual-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setResult(r);
      if (r.error) {
        setError(r.error);
        toast(r.error, false);
      } else if (r.status === "ok") {
        toast(`Orden ejecutada: ${r.executedQty || r.quantity || ""} ${r.symbol || symbol}`, true);
      } else {
        toast(`Respuesta: ${JSON.stringify(r)}`, true);
      }
    } catch (e: any) {
      setError(e.message || "Error al enviar orden");
      toast(e.message || "Error al enviar orden", false);
    }
    setSubmitting(false);
  };

  return (
    <div className="space-y-4">
      {/* Trading permission warning */}
      {account && !account.permissions.trade && (
        <div className="rounded-[10px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 p-3 text-[12px] font-semibold text-[var(--color-warning)]">
          Esta cuenta no tiene permisos de trading. Solo lectura.
        </div>
      )}

      {/* Symbol selector */}
      <div className="flex gap-1.5 flex-wrap">
        {symbols.map((s) => (
          <button
            key={s}
            onClick={() => { setSymbol(s); setResult(null); setError(""); }}
            className={`px-3 h-8 rounded-[8px] text-[12px] font-bold transition-colors ${
              symbol === s
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Order form */}
        <div className="panel p-4 space-y-4">
          {/* Live price */}
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Precio actual</span>
              <p className="text-[20px] font-extrabold text-[var(--color-text)]">
                {priceLoading ? "..." : livePrice ? `$${livePrice.toLocaleString("en-US", { maximumFractionDigits: 6 })}` : "—"}
              </p>
            </div>
            <button onClick={fetchPrice} className="text-[11px] font-bold text-[var(--color-primary)] hover:opacity-80">
              Actualizar
            </button>
          </div>

          {/* Buy/Sell toggle */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => { setSide("BUY"); setQuantity(""); setAmountUsd(""); setResult(null); setError(""); }}
              className={cn(
                "h-11 rounded-[10px] text-[14px] font-extrabold transition-all",
                side === "BUY"
                  ? "bg-[var(--color-success)] text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              )}
            >
              Comprar
            </button>
            <button
              onClick={() => { setSide("SELL"); setQuantity(""); setAmountUsd(""); setResult(null); setError(""); }}
              className={cn(
                "h-11 rounded-[10px] text-[14px] font-extrabold transition-all",
                side === "SELL"
                  ? "bg-[var(--color-danger)] text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
              )}
            >
              Vender
            </button>
          </div>

          {/* Order type */}
          <div className="flex gap-2">
            {(["MARKET", "LIMIT"] as const).map((t) => (
              <button
                key={t}
                onClick={() => { setOrderType(t); if (t === "MARKET") setLimitPrice(""); }}
                className={cn(
                  "flex-1 h-8 rounded-[8px] text-[12px] font-bold transition-colors",
                  orderType === t
                    ? "bg-[var(--color-primary)]/12 text-[var(--color-primary)]"
                    : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                )}
              >
                {t === "MARKET" ? "Mercado" : "Límite"}
              </button>
            ))}
          </div>

          {/* Available balance display */}
          <div className="flex items-center justify-between text-[11px] rounded-[8px] bg-[var(--color-surface-2)]/50 px-3 py-2">
            <span className="text-[var(--color-text-muted)] font-bold">Disponible:</span>
            {side === "BUY" ? (
              <span className="font-bold text-green-400">{availableUsdt.toFixed(2)} {quoteCurrency}</span>
            ) : (
              <span className="font-bold text-red-400">{availableAsset.toFixed(6)} {baseAsset}{heldQty > 0 && heldQty < availableAsset ? ` (pos: ${heldQty.toFixed(6)})` : ""}</span>
            )}
          </div>

          {/* Amount input */}
          {orderType === "MARKET" && side === "BUY" ? (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Monto en {quoteCurrency}
              </label>
              <div className="relative">
                <input
                  type="number"
                  value={amountUsd}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    if (v > availableUsdt) setAmountUsd(availableUsdt.toString());
                    else setAmountUsd(e.target.value);
                  }}
                  placeholder="100"
                  max={availableUsdt}
                  className={cn(
                    "w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border px-3 text-[14px] font-bold text-[var(--color-text)] outline-none",
                    exceedsBalance ? "border-red-500/50" : "border-[var(--color-border)] focus:border-[var(--color-primary)]"
                  )}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] font-bold text-[var(--color-text-muted)]">{quoteCurrency}</span>
              </div>
              {exceedsBalance && (
                <div className="text-[10px] text-red-400 font-bold mt-1">⚠ Excede tu saldo disponible</div>
              )}
              {/* Quick percentage buttons */}
              <div className="flex gap-1 mt-1.5">
                {[25, 50, 75, 100].map((pct) => (
                  <button
                    key={pct}
                    onClick={() => setAmountUsd((availableUsdt * pct / 100).toFixed(2))}
                    className="flex-1 h-6 rounded-[4px] text-[10px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Cantidad ({baseAsset})
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => {
                  const v = parseFloat(e.target.value);
                  if (v > maxSellQty) setQuantity(maxSellQty.toString());
                  else setQuantity(e.target.value);
                }}
                placeholder="0.001"
                max={maxSellQty}
                className={cn(
                  "w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border px-3 text-[14px] font-bold text-[var(--color-text)] outline-none",
                  exceedsBalance ? "border-red-500/50" : "border-[var(--color-border)] focus:border-[var(--color-primary)]"
                )}
              />
              {exceedsBalance && (
                <div className="text-[10px] text-red-400 font-bold mt-1">⚠ Excede tu saldo disponible</div>
              )}
              {/* Quick percentage buttons for sell */}
              <div className="flex gap-1 mt-1.5">
                {[25, 50, 75, 100].map((pct) => (
                  <button
                    key={pct}
                    onClick={() => setQuantity((maxSellQty * pct / 100).toFixed(6))}
                    className="flex-1 h-6 rounded-[4px] text-[10px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Limit price */}
          {orderType === "LIMIT" && (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Precio límite ({quoteCurrency})
              </label>
              <input
                type="number"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                placeholder={livePrice?.toString() || "0"}
                className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] focus:border-[var(--color-primary)] outline-none"
              />
            </div>
          )}

          {/* Stop-Loss / Take-Profit (only for BUY) */}
          {side === "BUY" && (
            <div className="space-y-3 rounded-[10px] bg-[var(--color-surface-2)]/50 p-3 border border-[var(--color-border)]/30">
              <div className="text-[11px] font-bold text-[var(--color-text-muted)] uppercase">Gestión de riesgo</div>

              {/* Position sizer */}
              <div>
                <label className="block text-[10px] font-bold text-[var(--color-text-muted)] mb-1">
                  Riesgo por trade (% del capital)
                </label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={riskPct}
                    onChange={(e) => setRiskPct(e.target.value)}
                    step="0.5"
                    className="w-20 h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none"
                  />
                  <span className="text-[11px] text-[var(--color-text-muted)]">
                    {livePrice && stopLossPrice && parseFloat(riskPct) > 0
                      ? `Posición sugerida: ${((parseFloat(amountUsd || "0") * parseFloat(riskPct) / 100) / Math.abs(livePrice - parseFloat(stopLossPrice))).toFixed(6)} ${symbol.replace(quoteCurrency, "")}`
                      : "Ingresa SL para calcular"}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-danger)] mb-1">
                    Stop-Loss ({quoteCurrency})
                  </label>
                  <input
                    type="number"
                    value={stopLossPrice}
                    onChange={(e) => setStopLossPrice(e.target.value)}
                    placeholder={livePrice ? (livePrice * 0.97).toFixed(2) : "0"}
                    className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-danger)]"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-[var(--color-success)] mb-1">
                    Take-Profit ({quoteCurrency})
                  </label>
                  <input
                    type="number"
                    value={takeProfitPrice}
                    onChange={(e) => setTakeProfitPrice(e.target.value)}
                    placeholder={livePrice ? (livePrice * 1.06).toFixed(2) : "0"}
                    className="w-full h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-success)]"
                  />
                </div>
              </div>

              {/* R/R ratio display */}
              {livePrice && stopLossPrice && takeProfitPrice &&
                parseFloat(stopLossPrice) > 0 && parseFloat(takeProfitPrice) > 0 && (
                <div className="flex justify-between text-[11px]">
                  <span className="text-[var(--color-text-muted)]">
                    Riesgo: ${((livePrice - parseFloat(stopLossPrice)) * computedQty).toFixed(2)}
                  </span>
                  <span className="text-[var(--color-text-muted)]">
                    Reward: ${((parseFloat(takeProfitPrice) - livePrice) * computedQty).toFixed(2)}
                  </span>
                  <span className="font-bold text-[var(--color-primary)]">
                    R/R 1:{((parseFloat(takeProfitPrice) - livePrice) / (livePrice - parseFloat(stopLossPrice))).toFixed(1)}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Summary with fees and P&L */}
          <div className="rounded-[10px] bg-[var(--color-surface-2)] p-3 space-y-1.5 text-[12px]">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Orden</span>
              <span className="font-bold text-[var(--color-text)]">{side === "BUY" ? "Comprar" : "Vender"} {symbol}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Tipo</span>
              <span className="font-bold text-[var(--color-text)]">{orderType === "MARKET" ? "Mercado" : "Límite"}</span>
            </div>
            {computedQty > 0 && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Cantidad</span>
                <span className="font-bold text-[var(--color-text)]">{computedQty.toFixed(6)} {baseAsset}</span>
              </div>
            )}
            {orderValue > 0 && (
              <>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Valor orden</span>
                  <span className="font-bold text-[var(--color-text)]">${orderValue.toFixed(2)} {quoteCurrency}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Comisión (0.1%)</span>
                  <span className="font-bold text-yellow-400">−${fee.toFixed(4)} {quoteCurrency}</span>
                </div>
                <div className="flex justify-between border-t border-[var(--color-border)] pt-1.5">
                  <span className="text-[var(--color-text-muted)] font-bold">Recibes/Pagas</span>
                  <span className="font-bold text-[var(--color-text)]">${netValue.toFixed(2)} {quoteCurrency}</span>
                </div>
              </>
            )}
            {/* P&L for SELL */}
            {side === "SELL" && sellPnl !== null && (
              <div className={cn(
                "rounded-[6px] px-2 py-1.5 mt-1.5 border",
                sellPnl >= 0
                  ? "bg-green-500/10 border-green-500/30"
                  : "bg-red-500/10 border-red-500/30"
              )}>
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">
                    {sellPnl >= 0 ? "📈 Ganancia" : "📉 Pérdida"}
                  </span>
                  <span className={cn(
                    "text-[14px] font-extrabold",
                    sellPnl >= 0 ? "text-green-400" : "text-red-400"
                  )}>
                    {sellPnl >= 0 ? "+" : ""}{sellPnl.toFixed(2)} {quoteCurrency}
                  </span>
                </div>
                {sellPnlPct !== null && (
                  <div className="flex justify-between items-center mt-0.5">
                    <span className="text-[10px] text-[var(--color-text-muted)]">
                      Precio entrada: ${entryPrice?.toFixed(4)}
                    </span>
                    <span className={cn(
                      "text-[11px] font-bold",
                      sellPnlPct >= 0 ? "text-green-400" : "text-red-400"
                    )}>
                      {sellPnlPct >= 0 ? "+" : ""}{sellPnlPct.toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>
            )}
            {/* Entry price info for SELL */}
            {side === "SELL" && entryPrice && (
              <div className="flex justify-between text-[10px] text-[var(--color-text-muted)]">
                <span>Posición: {heldQty.toFixed(6)} {baseAsset} @ ${entryPrice.toFixed(4)}</span>
                <span>Costo: ${(entryPrice * (computedQty || heldQty)).toFixed(2)}</span>
              </div>
            )}
            {stopLossPrice && (
              <div className="flex justify-between">
                <span className="text-[var(--color-danger)]">Stop-Loss</span>
                <span className="font-bold text-[var(--color-danger)]">${parseFloat(stopLossPrice).toLocaleString("en-US")}</span>
              </div>
            )}
            {takeProfitPrice && (
              <div className="flex justify-between">
                <span className="text-[var(--color-success)]">Take-Profit</span>
                <span className="font-bold text-[var(--color-success)]">${parseFloat(takeProfitPrice).toLocaleString("en-US")}</span>
              </div>
            )}
          </div>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className={cn(
              "w-full h-11 rounded-[10px] text-[14px] font-extrabold transition-all",
              submitting
                ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                : side === "BUY"
                  ? "bg-[var(--color-success)] text-white hover:opacity-90"
                  : "bg-[var(--color-danger)] text-white hover:opacity-90"
            )}
          >
            {submitting ? "Enviando..." : `${side === "BUY" ? "Comprar" : "Vender"} ${baseAsset}`}
          </button>

          {/* Error */}
          {error && (
            <div className="rounded-[8px] bg-[var(--color-danger)]/10 p-3 text-[12px] font-semibold text-[var(--color-danger)]">
              {error}
            </div>
          )}

          {/* Success */}
          {result && result.status === "ok" && (
            <div className="rounded-[8px] bg-green-500/10 border border-green-500/30 p-3 space-y-1.5 text-[12px] font-semibold text-green-400">
              <div className="flex items-center gap-2">
                <span className="text-[14px]">✓</span>
                <span>Orden ejecutada correctamente</span>
              </div>
              <div className="text-[var(--color-text-muted)] text-[11px] space-y-0.5">
                <div>ID: {result.orderId}</div>
                <div>Símbolo: {result.symbol} · Lado: {result.side} · Tipo: {result.type}</div>
                <div>Cantidad ejecutada: {result.executedQty || "N/A"} · Estado: {result.status}</div>
                {result.price && <div>Precio: ${result.price}</div>}
                {result.ocoOrderId && <div className="text-yellow-400">OCO (SL/TP) configurado · ID: {result.ocoOrderId}</div>}
              </div>
            </div>
          )}
          {/* Show raw result if status is not "ok" but no error */}
          {result && result.status !== "ok" && !result.error && (
            <div className="rounded-[8px] bg-yellow-500/10 border border-yellow-500/30 p-3 text-[12px] font-semibold text-yellow-400">
              Respuesta del broker: {JSON.stringify(result)}
            </div>
          )}
        </div>

        {/* Chart */}
        <div className="space-y-3">
          <PriceChart symbol={symbol} interval="1h" height={380} />
        </div>
      </div>
    </div>
  );
}

function MarketsModule() {
  const [quoteCurrency, setQuoteCurrency] = useState("USDT");
  const [symbol, setSymbol] = useState("BTCUSDT");

  useEffect(() => {
    api<any>("/api/binance/balance").then((data) => {
      if (!data?.assets) return;
      const stablecoins = ["USDT", "BUSD", "USDC", "FDUSD", "TUSD", "EUR", "TRY", "BRL", "MXN"];
      for (const a of data.assets) {
        if (stablecoins.includes(a.asset) && a.total > 0) {
          setQuoteCurrency(a.asset);
          setSymbol("BTC" + a.asset);
          break;
        }
      }
    }).catch(() => {});
  }, []);

  const baseSymbols = ["BTC", "ETH", "SOL", "BNB", "DOGE", "AVAX", "XRP", "ADA"];
  const symbols = baseSymbols.map((s) => s + quoteCurrency);

  return (
    <div className="space-y-4">
      <div className="flex gap-1.5 flex-wrap">
        {symbols.map((s) => (
          <button
            key={s}
            onClick={() => setSymbol(s)}
            className={`px-3 h-8 rounded-[8px] text-[12px] font-bold transition-colors flex items-center gap-1.5 ${
              symbol === s
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}
          >
            <CryptoIcon symbol={s} size={16} />
            {s}
          </button>
        ))}
      </div>
      <PriceChart symbol={symbol} interval="1h" height={420} />
    </div>
  );
}

function OrdersModule({ activeOrders, filledOrders }: { activeOrders: any[]; filledOrders: any[] }) {
  return (
    <div className="space-y-4">
      <div className="panel p-4 border-l-2 border-[var(--color-primary)]">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-1">Órdenes Activas en Binance ({activeOrders.length})</h3>
        <p className="text-[10px] text-[var(--color-text-muted)] mb-3">Datos en tiempo real desde Binance API</p>
        {activeOrders.length === 0 ? (
          <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">No tienes órdenes activas en Binance actualmente</p>
        ) : (
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
              <th className="text-left pb-2">Symbol</th>
              <th className="text-left pb-2">Side</th>
              <th className="text-left pb-2">Type</th>
              <th className="text-right pb-2">Qty</th>
              <th className="text-right pb-2">Filled</th>
              <th className="text-right pb-2">Price</th>
              <th className="text-right pb-2">Stop</th>
              <th className="text-right pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {activeOrders.map((o, i) => (
              <tr key={i} className="border-b border-[var(--color-border)]/50">
                <td className="py-2 font-bold text-[var(--color-text)]">
                  <div className="flex items-center gap-1.5">
                    <CryptoIcon symbol={o.symbol} size={18} />
                    {o.symbol}
                  </div>
                </td>
                <td className={cn("font-bold", o.side === "BUY" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>{o.side}</td>
                <td className="text-[var(--color-text-muted)]">{o.type}</td>
                <td className="text-right text-[var(--color-text)]">{fmt(o.quantity)}</td>
                <td className="text-right text-[var(--color-text-muted)]">{fmt(o.filled_quantity)}</td>
                <td className="text-right text-[var(--color-text)]">{o.price ? fmt(o.price) : "—"}</td>
                <td className="text-right text-[var(--color-text-muted)]">{o.stop_price ? fmt(o.stop_price) : "—"}</td>
                <td className="text-right text-[var(--color-text-muted)]">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>

      {filledOrders.length > 0 && (
        <div className="panel p-4">
          <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Historial de Órdenes Binance ({filledOrders.length})</h3>
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                <th className="text-left pb-2">Time</th>
                <th className="text-left pb-2">Symbol</th>
                <th className="text-left pb-2">Side</th>
                <th className="text-left pb-2">Type</th>
                <th className="text-right pb-2">Qty</th>
                <th className="text-right pb-2">Avg Price</th>
                <th className="text-right pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {filledOrders.map((o, i) => (
                <tr key={i} className="border-b border-[var(--color-border)]/50">
                  <td className="py-2 text-[var(--color-text-muted)]">{o.time ? new Date(o.time).toLocaleString() : "—"}</td>
                  <td className="font-bold text-[var(--color-text)]">
                    <div className="flex items-center gap-1.5">
                      <CryptoIcon symbol={o.symbol} size={18} />
                      {o.symbol}
                    </div>
                  </td>
                  <td className={cn("font-bold", o.side === "BUY" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>{o.side}</td>
                  <td className="text-[var(--color-text-muted)]">{o.type}</td>
                  <td className="text-right text-[var(--color-text)]">{fmt(o.quantity)}</td>
                  <td className="text-right text-[var(--color-text)]">{o.avg_price ? fmt(o.avg_price) : o.price ? fmt(o.price) : "—"}</td>
                  <td className="text-right text-[var(--color-text-muted)]">{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HistoryModule({ trades }: { trades: any[] }) {
  return (
    <div className="panel p-4">
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Historial de Trades</h3>
      {trades.length === 0 ? (
        <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">Sin trades recientes</p>
      ) : (
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
              <th className="text-left pb-2">Time</th>
              <th className="text-left pb-2">Symbol</th>
              <th className="text-left pb-2">Side</th>
              <th className="text-right pb-2">Qty</th>
              <th className="text-right pb-2">Price</th>
              <th className="text-right pb-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i} className="border-b border-[var(--color-border)]/50">
                <td className="py-2 text-[var(--color-text-muted)]">{fmtDate(t.timestamp)}</td>
                <td className="font-bold text-[var(--color-text)]">
                  <div className="flex items-center gap-1.5">
                    <CryptoIcon symbol={t.symbol} size={18} />
                    {t.symbol}
                  </div>
                </td>
                <td className={cn("font-bold", t.side === "BUY" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>{t.side}</td>
                <td className="text-right text-[var(--color-text)]">{fmt(t.quantity)}</td>
                <td className="text-right text-[var(--color-text)]">{fmt(t.price)}</td>
                <td className="text-right font-bold text-[var(--color-text)]">${fmtVol(Number(t.quantity) * Number(t.price))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function PositionsModule({ positions: propPositions, brokerId }: { positions: any[]; brokerId: string | null }) {
  const [expandedCharts, setExpandedCharts] = useState<Set<string>>(new Set());
  const [paperStatus, setPaperStatus] = useState<any>(null);
  const [paperAction, setPaperAction] = useState("");
  const [depositAmount, setDepositAmount] = useState("1000");
  const [paperInterval, setPaperInterval] = useState("30");
  const [activeTab, setActiveTab] = useState<"live" | "paper">("live");
  const [paperPositions, setPaperPositions] = useState<any[]>([]);
  const [selectedPositions, setSelectedPositions] = useState<Set<number>>(new Set());
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisPopup, setAnalysisPopup] = useState<{ type: "error" | "info" | "success"; title: string; message: string; link?: string } | null>(null);
  const [aiProvider, setAiProvider] = useState<string | null>(null);
  const [aiModel, setAiModel] = useState<string | null>(null);
  const [livePositions, setLivePositions] = useState<any[]>(propPositions || []);
  const [showSlTpPanel, setShowSlTpPanel] = useState<Set<number>>(new Set());
  const [showPaperSlTpPanel, setShowPaperSlTpPanel] = useState<Set<number>>(new Set());

  // Fetch live positions directly (more reliable than parent props)
  const loadLivePositions = useCallback(async () => {
    try {
      const data = await api<any[]>("/api/positions");
      if (Array.isArray(data)) setLivePositions(data);
    } catch {}
  }, []);

  useEffect(() => {
    loadLivePositions();
    const id = setInterval(loadLivePositions, activeTab === "live" ? 5000 : 15000);
    return () => clearInterval(id);
  }, [activeTab, loadLivePositions]);

  // Load saved AI provider and model so analyze-positions uses the correct config
  useEffect(() => {
    (async () => {
      try {
        const plan = await api<any>("/api/ai-agent/plan");
        if (plan?.saved_provider) setAiProvider(plan.saved_provider);
        if (plan?.saved_model) setAiModel(plan.saved_model);
      } catch {}
    })();
  }, []);

  const allPositions = livePositions.length > 0 ? livePositions : (propPositions || []);
  const openPositions = allPositions.filter((p) => p.status === "open");
  const totalPnl = openPositions.reduce((sum, p) => sum + Number(p.unrealized_pnl || 0), 0);

  const loadPaperPositions = useCallback(async () => {
    try {
      const pp = await api<any[]>("/api/intelligence/paper-positions");
      setPaperPositions(pp || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadPaperPositions();
    const id = setInterval(loadPaperPositions, activeTab === "paper" ? 5000 : 10000);
    return () => clearInterval(id);
  }, [activeTab, loadPaperPositions]);

  const handlePaperSell = async (positionId: number) => {
    try {
      await api(`/api/intelligence/paper-positions/${positionId}/sell`, { method: "POST" });
      await loadPaperPositions();
    } catch (e) {
      console.error("Paper sell failed:", e);
    }
  };

  const toggleChart = (symbol: string) => {
    setExpandedCharts((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  const toggleSlTpPanel = (posId: number) => {
    setShowSlTpPanel((prev) => {
      const next = new Set(prev);
      if (next.has(posId)) next.delete(posId);
      else next.add(posId);
      return next;
    });
  };

  const togglePaperSlTpPanel = (posId: number) => {
    setShowPaperSlTpPanel((prev) => {
      const next = new Set(prev);
      if (next.has(posId)) next.delete(posId);
      else next.add(posId);
      return next;
    });
  };

  const handleCancelOco = async (positionId: number, symbol: string, ocoOrderId: string) => {
    try {
      const brokerSymbol = symbol.toUpperCase().replace(/[-_/]/g, "");
      await binanceProxy.cancelOCO(brokerSymbol, ocoOrderId);
      const res = await api<any>(`/api/intelligence/positions/${positionId}/clear-oco`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ oco_order_id: ocoOrderId }),
      });
      if (res?.status === "cancelled") {
        toast("OCO cancelado en Binance", true);
        await loadLivePositions();
      } else {
        toast(res?.error || "Error al cancelar OCO", false);
      }
    } catch (e: any) {
      toast(e?.message || "Error al cancelar OCO", false);
    }
  };

  const handleStopMonitoring = async (positionId: number, isPaper: boolean) => {
    try {
      const res = await api<any>(`/api/intelligence/positions/${positionId}/stop-monitoring`, { method: "POST" });
      if (res?.status === "monitoring_stopped") {
        toast("Monitoreo detenido", true);
        if (isPaper) await loadPaperPositions();
        else await loadLivePositions();
      } else {
        toast(res?.error || "Error al detener monitoreo", false);
      }
    } catch (e) {
      toast("Error al detener monitoreo", false);
    }
  };

  const loadPaperStatus = useCallback(async () => {
    try {
      const s = await api<any>("/api/paper-trading/status");
      setPaperStatus(s);
      if (s.interval_seconds) setPaperInterval(String(s.interval_seconds));
    } catch {}
  }, []);

  useEffect(() => {
    loadPaperStatus();
    const id = setInterval(loadPaperStatus, 10000);
    return () => clearInterval(id);
  }, [loadPaperStatus]);

  const handlePaperStart = async () => {
    setPaperAction("starting");
    try {
      await api("/api/paper-trading/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategies: ["trend"], interval_seconds: parseInt(paperInterval) }),
      });
      await loadPaperStatus();
    } catch {}
    setPaperAction("");
  };

  const handlePaperStop = async () => {
    setPaperAction("stopping");
    try {
      await api("/api/paper-trading/stop", { method: "POST" });
      await loadPaperStatus();
    } catch {}
    setPaperAction("");
  };

  const handlePaperDeposit = async () => {
    try {
      await api("/api/paper-trading/deposit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount: parseFloat(depositAmount) }),
      });
    } catch {}
  };

  const handlePaperInterval = async () => {
    try {
      await api("/api/paper-trading/interval", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval_seconds: parseInt(paperInterval) }),
      });
      await loadPaperStatus();
    } catch {}
  };

  const togglePositionSelection = (posId: number) => {
    setSelectedPositions((prev) => {
      const next = new Set(prev);
      if (next.has(posId)) next.delete(posId);
      else next.add(posId);
      return next;
    });
  };

  const handleAnalyze = async () => {
    if (selectedPositions.size === 0) return;
    setAnalyzing(true);

    // Build positions payload from selected open positions
    const selectedData = openPositions
      .filter((p) => selectedPositions.has(p.id))
      .map((p) => ({
        id: p.id,
        symbol: p.symbol,
        side: p.side || "long",
        entry_price: Number(p.entry_price),
        current_price: Number(p.current_price || 0),
        stop_loss: p.stop_loss ? Number(p.stop_loss) : null,
        take_profit: p.take_profit ? Number(p.take_profit) : null,
        quantity: Number(p.quantity),
        unrealized_pnl: Number(p.unrealized_pnl || 0),
      }));

    try {
      const body: any = { positions: selectedData, broker: brokerId || "paper" };
      if (aiProvider) body.provider = aiProvider;
      if (aiModel) body.model = aiModel;
      const res = await api<any>("/api/ai-agent/analyze-positions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (res?.status === "started") {
        setAnalysisPopup({
          type: "info",
          title: "Análisis iniciado",
          message: `Analizando ${res.positions_count} posiciones con IA (${res.provider}). Te notificaremos al terminar. Revisa las sugerencias en Reportes.`,
        });
        toast(`Análisis iniciado para ${res.positions_count} posiciones`, true);
        setSelectedPositions(new Set());
      }
    } catch (e: any) {
      const msg = e?.message || "";
      if (msg.includes("409") || msg.includes("activo") || msg.includes("detenerlo")) {
        setAnalysisPopup({
          type: "error",
          title: "Agente IA activo",
          message: "El agente IA está activo. Debes detenerlo primero para analizar posiciones.",
        });
      } else if (msg.includes("400") || msg.includes("API key") || msg.includes("configurada")) {
        setAnalysisPopup({
          type: "error",
          title: "IA no configurada",
          message: "No tienes una IA configurada en Trading Agent. Ve a AI Agent para configurar tu proveedor.",
          link: "ai-agent",
        });
      } else {
        setAnalysisPopup({
          type: "error",
          title: "Error",
          message: msg || "Error al iniciar el análisis",
        });
      }
    }
    setAnalyzing(false);
  };

  const paperTradingPanel = (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Paper Trading</h3>
        <span
          className={`text-[11px] font-bold px-2 h-5 rounded flex items-center ${
            paperStatus?.status === "running"
              ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          }`}
        >
          {paperStatus?.status === "running" ? "RUNNING" : "STOPPED"}
        </span>
      </div>
      <div className="flex flex-wrap gap-3 items-end">
        {paperStatus?.status === "running" ? (
          <button
            onClick={handlePaperStop}
            disabled={!!paperAction}
            className="h-8 px-3 rounded-[8px] text-[12px] font-bold bg-[var(--color-danger)] text-white hover:opacity-90 disabled:opacity-50"
          >
            {paperAction === "stopping" ? "Stopping..." : "Stop"}
          </button>
        ) : (
          <button
            onClick={handlePaperStart}
            disabled={!!paperAction}
            className="h-8 px-3 rounded-[8px] text-[12px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50"
          >
            {paperAction === "starting" ? "Starting..." : "Start"}
          </button>
        )}
        <div>
          <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Interval (sec)</label>
          <div className="flex gap-1">
            <input
              type="number"
              value={paperInterval}
              onChange={(e) => setPaperInterval(e.target.value)}
              min={5}
              className="w-20 h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
            <button
              onClick={handlePaperInterval}
              className="h-8 px-2 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
            >
              Set
            </button>
          </div>
        </div>
        <div>
          <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Deposit (USDT)</label>
          <div className="flex gap-1">
            <input
              type="number"
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
              className="w-24 h-8 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[12px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
            <button
              onClick={handlePaperDeposit}
              className="h-8 px-2 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
            >
              Deposit
            </button>
          </div>
        </div>
        {paperStatus?.local_time && (
          <span className="text-[11px] text-[var(--color-text-muted)] ml-auto">
            {paperStatus.local_time}
          </span>
        )}
      </div>
    </div>
  );

  const paperTotalPnl = paperPositions.reduce((a, p) => a + (p.unrealized_pnl || 0), 0);
  const paperTotalValue = paperPositions.reduce((a, p) => a + (p.usd_value || 0), 0);

  return (
    <div className="space-y-4">
      {/* Tab selector */}
      <div className="flex gap-2 border-b border-[var(--color-border)] pb-2">
        <button
          className={cn(
            "px-3 h-8 rounded-[6px] text-[12px] font-bold transition-colors",
            activeTab === "live"
              ? "bg-[var(--color-primary)] text-white"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          )}
          onClick={() => setActiveTab("live")}
        >
          Live ({openPositions.length})
        </button>
        <button
          className={cn(
            "px-3 h-8 rounded-[6px] text-[12px] font-bold transition-colors flex items-center gap-1.5",
            activeTab === "paper"
              ? "bg-[var(--color-info)] text-white"
              : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
          )}
          onClick={() => setActiveTab("paper")}
        >
          Paper Money ({paperPositions.length})
        </button>
      </div>

      {/* Live Tab */}
      {activeTab === "live" && (
        <>
          {openPositions.length === 0 ? (
            <div className="panel p-6 text-center">
              <Layers size={28} className="mx-auto text-[var(--color-text-muted)] mb-2" />
              <p className="text-[13px] font-bold text-[var(--color-text)]">Sin posiciones abiertas</p>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-1">
                Las posiciones que abras — manualmente o vía IA — aparecerán aquí con su gráfico en tiempo real.
              </p>
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="panel p-4 flex items-center gap-4">
                <div className="flex-1 flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedPositions.size === openPositions.length && openPositions.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedPositions(new Set(openPositions.map((p) => p.id)));
                      } else {
                        setSelectedPositions(new Set());
                      }
                    }}
                    className="w-4 h-4 rounded accent-[var(--color-primary)] cursor-pointer"
                    title="Seleccionar todas"
                  />
                  <div>
                    <h3 className="text-[13px] font-bold text-[var(--color-text)]">Posiciones Abiertas ({openPositions.length})</h3>
                    <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">PnL no realizado en tiempo real · Click en una posición para ver su gráfico</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {selectedPositions.size > 0 && (
                    <button
                      onClick={handleAnalyze}
                      disabled={analyzing}
                      className="h-8 px-3 rounded-[8px] text-[12px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-1.5"
                    >
                      {analyzing ? "Analizando..." : `Analizar con IA (${selectedPositions.size})`}
                    </button>
                  )}
                  <div className="text-right">
                    <p className="text-[10px] font-bold uppercase text-[var(--color-text-muted)]">PnL Total</p>
                    <p className={cn("text-[16px] font-extrabold", totalPnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      {totalPnl >= 0 ? "+" : ""}{fmtVol(totalPnl)} USD
                    </p>
                  </div>
                </div>
              </div>

              {/* Position cards with charts */}
              {openPositions.map((p, i) => {
                const pnl = Number(p.unrealized_pnl || 0);
                const pnlPct = p.entry_price && p.current_price
                  ? ((Number(p.current_price) - Number(p.entry_price)) / Number(p.entry_price) * 100)
                  : 0;
                const isExpanded = expandedCharts.has(p.symbol);
                const chartSymbol = p.symbol.includes("USDT") || p.symbol.includes("BTC") || p.symbol.includes("ETH") || p.symbol.includes("BNB") || p.symbol.includes("FDUSD") || p.symbol.includes("TUSD")
                  ? p.symbol.replace("/", "")
                  : p.symbol.replace("/", "") + "USDT";

                return (
                  <div key={i} className="panel overflow-hidden">
                    {/* Position header row */}
                    <div className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--color-surface-hover)] transition-colors text-left">
                      <input
                        type="checkbox"
                        checked={selectedPositions.has(p.id)}
                        onChange={(e) => { e.stopPropagation(); togglePositionSelection(p.id); }}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 rounded accent-[var(--color-primary)] cursor-pointer flex-shrink-0"
                      />
                      <button
                        onClick={() => toggleChart(p.symbol)}
                        className="flex items-center gap-3 flex-1 text-left"
                      >
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <CryptoIcon symbol={p.symbol} size={24} />
                        <div className={cn(
                          "w-7 h-7 rounded-[8px] flex items-center justify-center text-[10px] font-extrabold",
                          p.side === "long" ? "bg-[var(--color-success)]/15 text-[var(--color-success)]" : "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
                        )}>
                          {p.side === "long" ? "L" : "S"}
                        </div>
                        <span className="text-[13px] font-extrabold text-[var(--color-text)]">{p.symbol}</span>
                      </div>

                      <div className="flex items-center gap-4 flex-1 text-[11px]">
                        <div>
                          <span className="text-[var(--color-text-muted)]">Qty </span>
                          <span className="font-bold text-[var(--color-text)]">{fmt(p.quantity)}</span>
                        </div>
                        <div>
                          <span className="text-[var(--color-text-muted)]">Entry </span>
                          <span className="font-bold text-[var(--color-text)]">{fmt(p.entry_price)}</span>
                        </div>
                        <div>
                          <span className="text-[var(--color-text-muted)]">Live </span>
                          <span className="font-bold text-[var(--color-text)]">{p.current_price ? fmt(p.current_price) : "—"}</span>
                        </div>
                        {(p.stop_loss || p.take_profit) && (
                          <div className="text-[10px] text-[var(--color-text-muted)]">
                            {p.stop_loss && <span className="text-[var(--color-danger)]">SL {fmt(p.stop_loss)}</span>}
                            {p.stop_loss && p.take_profit && " · "}
                            {p.take_profit && <span className="text-[var(--color-success)]">TP {fmt(p.take_profit)}</span>}
                          </div>
                        )}
                        {p.strategy_name && (
                          <div className="text-[10px] text-[var(--color-text-muted)] italic">{p.strategy_name}</div>
                        )}
                      </div>

                      {/* PnL */}
                      <div className="text-right flex-shrink-0">
                        <p className={cn("text-[13px] font-extrabold", pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                          {pnl >= 0 ? "+" : ""}{fmtVol(pnl)} USD
                        </p>
                        {pnlPct !== 0 && (
                          <p className={cn("text-[10px] font-bold", pnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                            {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                          </p>
                        )}
                      </div>

                      {/* Expand icon */}
                      <div className="flex-shrink-0 text-[var(--color-text-muted)]">
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    </button>
                    </div>

                    {/* Inline chart */}
                    {isExpanded && (
                      <div className="border-t border-[var(--color-border)] p-3">
                        <PriceChart
                          symbol={chartSymbol}
                          interval="1h"
                          height={300}
                          stopLoss={p.stop_loss ? Number(p.stop_loss) : null}
                          takeProfit={p.take_profit ? Number(p.take_profit) : null}
                          entryPrice={p.entry_price ? Number(p.entry_price) : null}
                        />

                        {/* SL/TP action buttons */}
                        <div className="flex items-center gap-2 mt-3 flex-wrap">
                          {/* OCO active badge + cancel button */}
                          {p.metadata_json?.oco_order_id && (
                            <>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[var(--color-success)]/15 text-[var(--color-success)] border border-[var(--color-success)]/40">
                                OCO activo
                              </span>
                              <button
                                onClick={() => handleCancelOco(p.id, p.symbol, p.metadata_json?.oco_order_id)}
                                className="h-7 px-3 rounded-[6px] text-[11px] font-bold bg-[var(--color-danger)] text-white hover:opacity-90 transition-opacity"
                              >
                                Cancelar OCO
                              </button>
                            </>
                          )}

                          {/* Monitoring active badge + stop button */}
                          {p.metadata_json?.monitoring_active && !p.metadata_json?.oco_order_id && (
                            <>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[var(--color-info)]/15 text-[var(--color-info)] border border-[var(--color-info)]/40">
                                Monitoreando
                              </span>
                              <button
                                onClick={() => handleStopMonitoring(p.id, false)}
                                className="h-7 px-3 rounded-[6px] text-[11px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
                              >
                                Detener monitoreo
                              </button>
                            </>
                          )}

                          {/* Place SL/TP button (only if no OCO active) */}
                          {!p.metadata_json?.oco_order_id && (
                            <button
                              onClick={() => toggleSlTpPanel(p.id)}
                              className={cn(
                                "h-7 px-3 rounded-[6px] text-[11px] font-bold transition-opacity",
                                showSlTpPanel.has(p.id)
                                  ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                                  : "bg-[var(--color-success)] text-white hover:opacity-90"
                              )}
                            >
                              {showSlTpPanel.has(p.id) ? "✕ Cerrar" : "Colocar SL/TP"}
                            </button>
                          )}
                        </div>

                        {/* SlTpPanel inline */}
                        {showSlTpPanel.has(p.id) && !p.metadata_json?.oco_order_id && (
                          <SlTpPanel
                            positionId={p.id}
                            symbol={p.symbol}
                            currentPrice={Number(p.current_price || 0)}
                            entryPrice={Number(p.entry_price || 0)}
                            existingSl={p.stop_loss ? Number(p.stop_loss) : null}
                            existingTp={p.take_profit ? Number(p.take_profit) : null}
                            quantity={Number(p.quantity || 0)}
                            isLive={true}
                            isFutures={!!(p.metadata_json?.source && String(p.metadata_json.source).includes("futures"))}
                            side={p.side || "long"}
                            onSuccess={() => { loadLivePositions(); setShowSlTpPanel(new Set()); }}
                          />
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </>
      )}

      {/* Paper Tab */}
      {activeTab === "paper" && (
        <>
          {paperTradingPanel}

          {/* Paper stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="panel p-3">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Paper Posiciones</p>
              <p className="text-[18px] font-extrabold text-[var(--color-info)]">{paperPositions.length}</p>
            </div>
            <div className="panel p-3">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Valor Total</p>
              <p className="text-[18px] font-extrabold">${fmtVol(paperTotalValue)}</p>
            </div>
            <div className="panel p-3">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">PnL Total</p>
              <p className={cn("text-[18px] font-extrabold", paperTotalPnl >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                {paperTotalPnl >= 0 ? "+" : ""}{fmtVol(paperTotalPnl)}
              </p>
            </div>
            <div className="panel p-3">
              <p className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Estado</p>
              <p className={cn("text-[14px] font-extrabold", paperStatus?.status === "running" ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]")}>
                {paperStatus?.status === "running" ? "RUNNING" : "STOPPED"}
              </p>
            </div>
          </div>

          {paperPositions.length === 0 ? (
            <div className="panel p-6 text-center">
              <Layers size={28} className="mx-auto text-[var(--color-text-muted)] mb-2" />
              <p className="text-[13px] font-bold text-[var(--color-text)]">Sin paper positions activas</p>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-1">
                Acepta recomendaciones desde la pestaña Reportes para crear posiciones simuladas y trackear su profit en tiempo real.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {paperPositions.map((p) => {
                const entry = Number(p.entry_price || 0);
                const current = Number(p.current_price || 0);
                const sl = Number(p.stop_loss || 0);
                const tp = Number(p.take_profit || 0);
                const pnl = Number(p.unrealized_pnl || 0);
                const pnlPct = Number(p.pnl_pct || 0);
                const isProfit = pnl >= 0;
                const qty = Number(p.quantity || 0);
                const invested = Number(p.invested || 0);
                const meta = p.metadata_json || {};
                return (
                  <div key={p.id} className="panel p-4">
                    {/* Header */}
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        <CryptoIcon symbol={p.symbol} size={28} />
                        <div>
                          <span className="font-bold text-[14px]">{p.symbol}</span>
                          <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] font-bold bg-[var(--color-info)] text-white">PAPER</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] text-[var(--color-text-muted)]">{fmtDate(p.opened_at)}</div>
                        <div className={cn("text-[16px] font-extrabold", isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                          {isProfit ? "+" : ""}${fmtVol(Math.abs(pnl))}
                        </div>
                      </div>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Entry</div>
                        <div className="num font-bold">{fmt(entry)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Actual</div>
                        <div className={cn("num font-bold", isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                          {fmt(current)}
                        </div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Cant.</div>
                        <div className="num font-bold">{qty.toFixed(6)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-danger)] uppercase">SL</div>
                        <div className="num font-bold text-[var(--color-danger)]">{fmt(sl)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-success)] uppercase">TP</div>
                        <div className="num font-bold text-[var(--color-success)]">{fmt(tp)}</div>
                      </div>
                      <div className="p-2 rounded-lg bg-[var(--color-surface-2)]">
                        <div className="text-[10px] text-[var(--color-text-muted)] uppercase">Inversión</div>
                        <div className="num font-bold">${fmtVol(invested)}</div>
                      </div>
                    </div>

                    {/* PnL progress bar */}
                    <div className="pt-3 border-t border-[var(--color-border)]">
                      <div className="flex justify-between items-center mb-1.5">
                        <span className="text-[11px] text-[var(--color-text-muted)]">PnL {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%</span>
                        <span className={cn("text-[12px] font-bold", isProfit ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                          {isProfit ? "+" : ""}${fmtVol(Math.abs(pnl))}
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

                    {/* Reason */}
                    {meta.reason && (
                      <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                        <span className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase">Razón IA</span>
                        <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{meta.reason}</p>
                      </div>
                    )}

                    {/* SL/TP + Sell buttons */}
                    <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2">
                      {/* Monitoring badge */}
                      {meta.monitoring_active && (
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[var(--color-info)]/15 text-[var(--color-info)] border border-[var(--color-info)]/40">
                            Monitoreando
                          </span>
                          <button
                            onClick={() => handleStopMonitoring(p.id, true)}
                            className="h-6 px-2 rounded-[6px] text-[10px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors"
                          >
                            Detener
                          </button>
                        </div>
                      )}

                      <div className="flex gap-2">
                        <button
                          onClick={() => togglePaperSlTpPanel(p.id)}
                          className={cn(
                            "flex-1 h-8 rounded-[8px] text-[12px] font-bold transition-opacity",
                            showPaperSlTpPanel.has(p.id)
                              ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                              : "bg-[var(--color-info)] text-white hover:opacity-90"
                          )}
                        >
                          {showPaperSlTpPanel.has(p.id) ? "✕ Cerrar" : "Colocar SL/TP"}
                        </button>
                        <button
                          onClick={() => handlePaperSell(p.id)}
                          className="flex-1 h-8 rounded-[8px] text-[12px] font-bold bg-[var(--color-danger)] text-white hover:opacity-90 transition-opacity"
                        >
                          Vender
                        </button>
                      </div>

                      {/* SlTpPanel inline for paper */}
                      {showPaperSlTpPanel.has(p.id) && (
                        <SlTpPanel
                          positionId={p.id}
                          symbol={p.symbol}
                          currentPrice={current}
                          entryPrice={entry}
                          existingSl={sl > 0 ? sl : null}
                          existingTp={tp > 0 ? tp : null}
                          quantity={Number(p.quantity || 0)}
                          isLive={false}
                          onSuccess={() => { loadPaperPositions(); setShowPaperSlTpPanel(new Set()); }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Analysis Popup */}
      {analysisPopup && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setAnalysisPopup(null)}
        >
          <div
            className="w-[400px] panel p-5 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-8 h-8 rounded-[8px] flex items-center justify-center text-[14px] font-extrabold",
                analysisPopup.type === "error"
                  ? "bg-[var(--color-danger)]/15 text-[var(--color-danger)]"
                  : analysisPopup.type === "success"
                    ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
                    : "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
              )}>
                {analysisPopup.type === "error" ? "!" : analysisPopup.type === "success" ? "✓" : "i"}
              </div>
              <h3 className="text-[14px] font-extrabold text-[var(--color-text)]">{analysisPopup.title}</h3>
            </div>
            <p className="text-[12px] text-[var(--color-text-muted)] leading-relaxed">{analysisPopup.message}</p>
            <div className="flex justify-end gap-2 pt-2">
              {analysisPopup.link && (
                <button
                  onClick={() => {
                    window.dispatchEvent(new CustomEvent("navigate", { detail: { page: analysisPopup.link } }));
                    setAnalysisPopup(null);
                  }}
                  className="h-8 px-3 rounded-[8px] text-[12px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                >
                  Ir a AI Agent
                </button>
              )}
              <button
                onClick={() => setAnalysisPopup(null)}
                className="h-8 px-4 rounded-[8px] text-[12px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigModule({ account, broker }: { account: BrokerAccount; broker: any }) {
  return (
    <div className="space-y-3">
      <div className="panel p-4 space-y-3">
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Información de la Cuenta</h3>
        <div className="grid grid-cols-2 gap-3 text-[12px]">
          <div>
            <span className="text-[var(--color-text-muted)]">Broker: </span>
            <span className="font-bold text-[var(--color-text)]">{broker.displayName}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">Entorno: </span>
            <span className="font-bold text-[var(--color-text)]">{account.environment}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">API Key: </span>
            <span className="font-bold text-[var(--color-text)]">{account.apiKeyPreview}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">Estado: </span>
            <BrokerStatusBadge status={account.status} />
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">Permisos: </span>
            <span className="font-bold text-[var(--color-text)]">
              {account.permissions.read ? "Lectura" : ""}{account.permissions.trade ? " + Trading" : ""}
            </span>
          </div>
          <div>
            <span className="text-[var(--color-text-muted)]">Última sync: </span>
            <span className="font-bold text-[var(--color-text)]">{account.lastSyncAt ? fmtDate(account.lastSyncAt) : "Nunca"}</span>
          </div>
        </div>
      </div>

      <div className="panel p-4 space-y-3">
        <h3 className="text-[13px] font-bold text-[var(--color-text)]">Capabilities</h3>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(broker.capabilities || {}).map(([key, val]) => (
            <div key={key} className={cn(
              "rounded-[8px] px-2 py-1.5 text-[11px] font-semibold text-center",
              val ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            )}>
              {key}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
