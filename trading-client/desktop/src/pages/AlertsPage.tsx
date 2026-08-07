import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { cn } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";

interface PriceAlert {
  id: number;
  symbol: string;
  condition: string;
  target_price: number;
  note: string | null;
  triggered: boolean;
  acknowledged: boolean;
  created_at: string;
  triggered_at?: string;
  triggered_price?: number;
}

const symbols = [
  "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "TRXUSDT", "LTCUSDT", "AVAXUSDT",
  "LINKUSDT", "DOTUSDT", "MATICUSDT", "ATOMUSDT", "NEARUSDT", "ARBUSDT", "OPUSDT", "APTUSDT", "FILUSDT", "INJUSDT",
  "SUIUSDT", "SEIUSDT", "TIAUSDT", "RNDRUSDT", "FETUSDT", "WLDUSDT", "ORDIUSDT", "TONUSDT", "JUPUSDT", "PYTHUSDT",
  "PEPEUSDT", "SHIBUSDT", "WIFUSDT", "FLOKIUSDT", "BONKUSDT",
];

export function PriceAlertsContent() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [priceAlerts, setPriceAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(true);

  // Price alert form state
  const [alertSymbol, setAlertSymbol] = useState("BTCUSDT");
  const [alertCondition, setAlertCondition] = useState<"above" | "below">("above");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertNote, setAlertNote] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    const [a, pa] = await Promise.all([
      api<any[]>("/api/intelligence/alerts?limit=20").catch(() => []),
      api<PriceAlert[]>("/api/intelligence/price-alerts").catch(() => []),
    ]);
    setAlerts(a);
    setPriceAlerts(pa);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const handleCreateAlert = async () => {
    if (!alertPrice || parseFloat(alertPrice) <= 0) return;
    setCreating(true);
    try {
      await api("/api/intelligence/price-alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: alertSymbol,
          condition: alertCondition,
          target_price: parseFloat(alertPrice),
          note: alertNote || null,
        }),
      });
      setAlertPrice("");
      setAlertNote("");
      await load();
    } catch {
      // ignore
    }
    setCreating(false);
  };

  const handleDeleteAlert = async (id: number) => {
    await api(`/api/intelligence/price-alerts/${id}`, { method: "DELETE" });
    setPriceAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const handleCheckAlerts = async () => {
    await api("/api/intelligence/price-alerts/check", { method: "POST" });
    await load();
  };

  return (
    <div className="p-5 space-y-6 max-w-[800px] mx-auto">
      {/* Price Alert Creator */}
      <div className="panel p-5">
        <h3 className="text-[14px] font-bold text-[var(--color-text)] mb-4">Crear Alerta de Precio</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Símbolo</label>
            <select
              value={alertSymbol}
              onChange={(e) => setAlertSymbol(e.target.value)}
              className="w-full h-9 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[13px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            >
              {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Condición</label>
            <select
              value={alertCondition}
              onChange={(e) => setAlertCondition(e.target.value as "above" | "below")}
              className="w-full h-9 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[13px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            >
              <option value="above">Por encima de</option>
              <option value="below">Por debajo de</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Precio (USDT)</label>
            <input
              type="number"
              value={alertPrice}
              onChange={(e) => setAlertPrice(e.target.value)}
              placeholder="0.00"
              className="w-full h-9 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[13px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
          <div>
            <label className="block text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1">Nota (opcional)</label>
            <input
              type="text"
              value={alertNote}
              onChange={(e) => setAlertNote(e.target.value)}
              placeholder="..."
              className="w-full h-9 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] px-2 text-[13px] font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
            />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleCreateAlert}
            disabled={creating || !alertPrice}
            className={cn(
              "h-9 px-4 rounded-[8px] text-[13px] font-bold transition-all",
              creating || !alertPrice
                ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] cursor-not-allowed"
                : "bg-[var(--color-primary)] text-white hover:opacity-90"
            )}
          >
            {creating ? "Creando..." : "Crear Alerta"}
          </button>
          <button
            onClick={handleCheckAlerts}
            className="h-9 px-4 rounded-[8px] text-[13px] font-bold bg-[var(--color-surface-2)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
          >
            Verificar Ahora
          </button>
        </div>
      </div>

      {/* Active Price Alerts */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Alertas de Precio Activas</h3>
        {loading ? (
          <LoadingSkeleton lines={3} />
        ) : priceAlerts.length === 0 ? (
          <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">No hay alertas configuradas</p>
        ) : (
          <div className="space-y-2">
            {priceAlerts.map((a) => (
              <div
                key={a.id}
                className={cn(
                  "flex items-center justify-between rounded-[8px] p-3 border",
                  a.triggered
                    ? "bg-[var(--color-warning)]/10 border-[var(--color-warning)]/30"
                    : "bg-[var(--color-surface-2)] border-[var(--color-border)]"
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="text-[14px] font-extrabold text-[var(--color-text)] flex items-center gap-1.5"><CryptoIcon symbol={a.symbol} size={18} />{a.symbol}</span>
                  <span className="text-[12px] text-[var(--color-text-muted)]">
                    {a.condition === "above" ? "\u2265" : "\u2264"} ${a.target_price.toLocaleString("en-US")}
                  </span>
                  {a.triggered && (
                    <span className="text-[11px] font-bold text-[var(--color-warning)]">
                      ¡Disparada! @ ${a.triggered_price?.toLocaleString("en-US")}
                    </span>
                  )}
                  {a.note && <span className="text-[11px] text-[var(--color-text-muted)]">— {a.note}</span>}
                </div>
                <button
                  onClick={() => handleDeleteAlert(a.id)}
                  className="text-[11px] font-bold text-[var(--color-danger)] hover:opacity-80"
                >
                  Eliminar
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Alerts Feed */}
      <div className="panel p-4">
        <h3 className="text-[13px] font-bold text-[var(--color-text)] mb-3">Alertas Recientes</h3>
        {loading ? (
          <LoadingSkeleton lines={4} />
        ) : alerts.length === 0 ? (
          <p className="text-[12px] text-[var(--color-text-muted)] py-4 text-center">Sin alertas recientes</p>
        ) : (
          <div className="space-y-2">
            {alerts.map((a, i) => (
              <div key={i} className="flex items-start gap-3 rounded-[8px] bg-[var(--color-surface-2)] p-3">
                <div className={cn(
                  "w-2 h-2 rounded-full mt-1.5 shrink-0",
                  a.severity === "high" ? "bg-[var(--color-danger)]" :
                  a.severity === "medium" ? "bg-[var(--color-warning)]" :
                  "bg-[var(--color-primary)]"
                )} />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    {a.symbol && <span className="text-[12px] font-bold text-[var(--color-text)] flex items-center gap-1"><CryptoIcon symbol={a.symbol} size={16} />{a.symbol}</span>}
                    <span className="text-[10px] text-[var(--color-text-muted)]">{a.type}</span>
                  </div>
                  <p className="text-[12px] text-[var(--color-text)] mt-0.5">{a.message}</p>
                  {a.timestamp && (
                    <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                      {new Date(a.timestamp).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AlertsPage() {
  return <PriceAlertsContent />;
}
