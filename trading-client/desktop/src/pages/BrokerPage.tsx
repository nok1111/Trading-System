import { useEffect, useState } from "react";
import { Wallet, TrendingUp, Settings as SettingsIcon, BarChart3, History, LineChart } from "lucide-react";
import { api } from "../lib/api";
import { useBrokerContext } from "../context/BrokerContext";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { NotConnectedState } from "../components/common/NotConnectedState";
import { BrokerStatusBadge } from "../components/brokers/BrokerStatusBadge";
import { cn, fmt, fmtVol, fmtDate } from "../lib/utils";
import type { BrokerAccount } from "../lib/brokerTypes";

interface BrokerPageProps {
  brokerId: string | null;
  moduleId: string | null;
}

const MODULE_LABELS: Record<string, string> = {
  overview: "Resumen",
  portfolio: "Portafolio",
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
  markets: <TrendingUp size={16} />,
  orders: <SettingsIcon size={16} />,
  history: <History size={16} />,
  earn: <LineChart size={16} />,
  futures: <LineChart size={16} />,
  config: <SettingsIcon size={16} />,
};

export function BrokerPage({ brokerId, moduleId }: BrokerPageProps) {
  const { supportedBrokers, connectedAccounts } = useBrokerContext();
  const [balanceData, setBalanceData] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
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
        const [bal, pos, ord, tr] = await Promise.all([
          api<any>("/api/binance/balance").catch(() => null),
          api<any[]>("/api/positions").catch(() => []),
          api<any[]>("/api/orders").catch(() => []),
          api<any[]>("/api/trades?limit=20").catch(() => []),
        ]);
        if (!alive) return;
        setBalanceData(bal);
        setPositions(pos);
        setOrders(ord);
        setTrades(tr);
      } catch {
        // graceful
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [brokerId]);

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
      {loading ? (
        <LoadingSkeleton lines={5} />
      ) : module === "overview" ? (
        <OverviewModule balanceData={balanceData} positions={positions} orders={orders} />
      ) : module === "portfolio" ? (
        <PortfolioModule balanceData={balanceData} />
      ) : module === "markets" ? (
        <MarketsModule />
      ) : module === "orders" ? (
        <OrdersModule orders={orders} />
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

function OverviewModule({ balanceData, positions, orders }: { balanceData: any; positions: any[]; orders: any[] }) {
  const assets: any[] = balanceData?.assets || [];
  const totalUsd = balanceData?.total_usd || 0;
  const totalMxn = balanceData?.total_mxn || 0;
  const activePositions = positions.filter((p) => p.status === "open").length;
  const activeOrders = orders.filter((o) => o.status === "SUBMITTED" || o.status === "PARTIALLY_FILLED" || o.status === "PENDING_APPROVAL").length;

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

function MarketsModule() {
  return (
    <div className="panel p-6 text-center">
      <TrendingUp size={28} className="mx-auto text-[var(--color-text-muted)] mb-2" />
      <p className="text-[14px] font-bold text-[var(--color-text)]">Mercados</p>
      <p className="text-[12px] text-[var(--color-text-muted)] mt-1">Datos de mercado en vivo próximamente</p>
    </div>
  );
}

function OrdersModule({ orders }: { orders: any[] }) {
  const active = orders.filter((o) => o.status === "SUBMITTED" || o.status === "PARTIALLY_FILLED" || o.status === "PENDING_APPROVAL" || o.status === "APPROVED");
  return (
    <div className="panel p-4">
      <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Órdenes Activas ({active.length})</h3>
      {active.length === 0 ? (
        <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">Sin órdenes activas</p>
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
              <th className="text-right pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {active.map((o, i) => (
              <tr key={i} className="border-b border-[var(--color-border)]/50">
                <td className="py-2 font-bold text-[var(--color-text)]">{o.symbol}</td>
                <td className={cn("font-bold", o.side === "BUY" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>{o.side}</td>
                <td className="text-[var(--color-text-muted)]">{o.order_type}</td>
                <td className="text-right text-[var(--color-text)]">{fmt(o.quantity)}</td>
                <td className="text-right text-[var(--color-text-muted)]">{fmt(o.filled_quantity)}</td>
                <td className="text-right text-[var(--color-text)]">{o.price ? fmt(o.price) : "—"}</td>
                <td className="text-right text-[var(--color-text-muted)]">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
