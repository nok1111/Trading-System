import { useEffect, useState, useCallback } from "react";
import { Wallet, TrendingUp, Settings as SettingsIcon, BarChart3, History, LineChart } from "lucide-react";
import { api } from "../lib/api";
import { useBrokerContext } from "../context/BrokerContext";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { NotConnectedState } from "../components/common/NotConnectedState";
import { BrokerStatusBadge } from "../components/brokers/BrokerStatusBadge";
import { cn, fmt, fmtVol, fmtDate } from "../lib/utils";
import { PriceChart } from "../components/charts/PriceChart";
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
        if (module === "overview") {
          tasks.push({ key: "positions", fn: () => api<any>("/api/binance/positions").catch(() => null) });
        }
        if (module === "overview" || module === "orders") {
          tasks.push({ key: "orders", fn: () => api<any>("/api/binance/all-orders?limit=50").catch(() => null) });
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
          else if (t.key === "positions") setPositions(data?.positions || []);
          else if (t.key === "orders") {
            setBinanceActiveOrders(data?.active || []);
            setBinanceFilledOrders(data?.filled || []);
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
                  <td className="py-2 font-bold text-[var(--color-text)]">{p.symbol}</td>
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
                <td className="py-2 font-bold text-[var(--color-text)]">{b.asset}</td>
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
  const [livePrice, setLivePrice] = useState<number | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "XRPUSDT", "ADAUSDT", "LINKUSDT", "DOTUSDT"];

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

  const computedQty = (() => {
    if (quantity) return parseFloat(quantity);
    if (amountUsd && livePrice && livePrice > 0) return parseFloat(amountUsd) / livePrice;
    return 0;
  })();

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

      const r = await api<any>("/api/binance/manual-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setResult(r);
      if (r.error) setError(r.error);
    } catch (e: any) {
      setError(e.message || "Error al enviar orden");
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
              onClick={() => setSide("BUY")}
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
              onClick={() => setSide("SELL")}
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
                onClick={() => setOrderType(t)}
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

          {/* Amount input */}
          {orderType === "MARKET" && side === "BUY" ? (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Monto en USDT
              </label>
              <div className="relative">
                <input
                  type="number"
                  value={amountUsd}
                  onChange={(e) => setAmountUsd(e.target.value)}
                  placeholder="100"
                  className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] focus:border-[var(--color-primary)] outline-none"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] font-bold text-[var(--color-text-muted)]">USDT</span>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Cantidad ({symbol.replace("USDT", "")})
              </label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0.001"
                className="w-full h-10 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-3 text-[14px] font-bold text-[var(--color-text)] focus:border-[var(--color-primary)] outline-none"
              />
            </div>
          )}

          {/* Limit price */}
          {orderType === "LIMIT" && (
            <div>
              <label className="block text-[11px] font-bold text-[var(--color-text-muted)] uppercase mb-1.5">
                Precio límite (USDT)
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

          {/* Summary */}
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
                <span className="text-[var(--color-text-muted)]">Cantidad aprox.</span>
                <span className="font-bold text-[var(--color-text)]">{computedQty.toFixed(6)} {symbol.replace("USDT", "")}</span>
              </div>
            )}
            {amountUsd && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Total</span>
                <span className="font-bold text-[var(--color-text)]">${parseFloat(amountUsd).toLocaleString("en-US")} USDT</span>
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
            {submitting ? "Enviando..." : `${side === "BUY" ? "Comprar" : "Vender"} ${symbol.replace("USDT", "")}`}
          </button>

          {/* Error */}
          {error && (
            <div className="rounded-[8px] bg-[var(--color-danger)]/10 p-3 text-[12px] font-semibold text-[var(--color-danger)]">
              {error}
            </div>
          )}

          {/* Success */}
          {result && result.status === "ok" && (
            <div className="rounded-[8px] bg-[var(--color-success)]/10 p-3 space-y-1 text-[12px] font-semibold text-[var(--color-success)]">
              <p>Orden ejecutada</p>
              <p className="text-[var(--color-text-muted)]">ID: {result.orderId} · {result.executedQty} {result.symbol} · {result.status}</p>
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
  const [symbol, setSymbol] = useState("BTCUSDT");
  const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "XRPUSDT", "ADAUSDT"];

  return (
    <div className="space-y-4">
      <div className="flex gap-1.5 flex-wrap">
        {symbols.map((s) => (
          <button
            key={s}
            onClick={() => setSymbol(s)}
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
                <td className="py-2 font-bold text-[var(--color-text)]">{o.symbol}</td>
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
                  <td className="font-bold text-[var(--color-text)]">{o.symbol}</td>
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
                <td className="font-bold text-[var(--color-text)]">{t.symbol}</td>
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
