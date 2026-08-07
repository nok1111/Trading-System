import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import { Play, Square, Trash2, Plus, Grid3x3, DollarSign, Activity } from "lucide-react";

// ─── Types ───

interface GridBot {
  id: number;
  name: string;
  broker_id: string;
  symbol: string;
  market_type: string;
  lower_price: string;
  upper_price: string;
  grid_count: number;
  investment_usd: string;
  is_active: boolean;
  status: string;
  orders_placed: number;
  orders_filled: number;
  realized_pnl: string;
  last_run_at: string | null;
  created_at: string;
}

interface DCABot {
  id: number;
  name: string;
  broker_id: string;
  symbol: string;
  market_type: string;
  buy_amount_usd: string;
  interval_minutes: number;
  max_buys: number;
  take_profit_pct: string;
  is_active: boolean;
  status: string;
  buys_executed: number;
  total_invested: string;
  total_quantity: string;
  avg_entry_price: string;
  realized_pnl: string;
  last_buy_at: string | null;
  created_at: string;
}

interface SchedulerStatus {
  is_running: boolean;
  cycle_count: number;
  last_cycle_at: string | null;
  active_grid_bots: number;
  active_dca_bots: number;
  total_grid_bots: number;
  total_dca_bots: number;
}

// ─── Component ───

export function BotsPage() {
  const [tab, setTab] = useState<"grid" | "dca">("grid");
  const [gridBots, setGridBots] = useState<GridBot[]>([]);
  const [dcaBots, setDCABots] = useState<DCABot[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  // Form state for grid bot
  const [gridForm, setGridForm] = useState({
    name: "", symbol: "BTC/USDT", lower_price: "", upper_price: "",
    grid_count: 10, investment_usd: "1000",
  });
  // Form state for DCA bot
  const [dcaForm, setDcaForm] = useState({
    name: "", symbol: "BTC/USDT", buy_amount_usd: "100",
    interval_minutes: 1440, max_buys: 0, take_profit_pct: 0,
  });

  const loadData = useCallback(async () => {
    try {
      const [grid, dca, sched] = await Promise.all([
        api("/api/bots/grid"),
        api("/api/bots/dca"),
        api("/api/bots/scheduler/status"),
      ]);
      setGridBots(grid as any);
      setDCABots(dca as any);
      setScheduler(sched as any);
    } catch (e) {
      console.error("Error loading bots:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const createGridBot = async () => {
    try {
      await api("/api/bots/grid", {
        method: "POST",
        body: JSON.stringify({
          ...gridForm,
          broker_id: "binance",
          market_type: "spot",
          lower_price: parseFloat(gridForm.lower_price),
          upper_price: parseFloat(gridForm.upper_price),
          grid_count: parseInt(String(gridForm.grid_count)),
          investment_usd: parseFloat(gridForm.investment_usd),
        }),
      });
      setShowCreate(false);
      setGridForm({ name: "", symbol: "BTC/USDT", lower_price: "", upper_price: "", grid_count: 10, investment_usd: "1000" });
      loadData();
    } catch (e: any) {
      alert(e.message || "Error creando grid bot");
    }
  };

  const createDCABot = async () => {
    try {
      await api("/api/bots/dca", {
        method: "POST",
        body: JSON.stringify({
          ...dcaForm,
          broker_id: "binance",
          market_type: "spot",
          buy_amount_usd: parseFloat(dcaForm.buy_amount_usd),
          interval_minutes: parseInt(String(dcaForm.interval_minutes)),
          max_buys: parseInt(String(dcaForm.max_buys)),
          take_profit_pct: parseFloat(String(dcaForm.take_profit_pct)),
        }),
      });
      setShowCreate(false);
      setDcaForm({ name: "", symbol: "BTC/USDT", buy_amount_usd: "100", interval_minutes: 1440, max_buys: 0, take_profit_pct: 0 });
      loadData();
    } catch (e: any) {
      alert(e.message || "Error creando DCA bot");
    }
  };

  const startBot = async (type: "grid" | "dca", id: number) => {
    try {
      await api(`/api/bots/${type}/${id}/start`, { method: "POST" });
      loadData();
    } catch (e: any) {
      alert(e.message || "Error iniciando bot");
    }
  };

  const stopBot = async (type: "grid" | "dca", id: number) => {
    try {
      await api(`/api/bots/${type}/${id}/stop`, { method: "POST" });
      loadData();
    } catch (e: any) {
      alert(e.message || "Error deteniendo bot");
    }
  };

  const deleteBot = async (type: "grid" | "dca", id: number) => {
    if (!confirm("¿Eliminar este bot?")) return;
    try {
      await api(`/api/bots/${type}/${id}`, { method: "DELETE" });
      loadData();
    } catch (e: any) {
      alert(e.message || "Error eliminando bot");
    }
  };

  if (loading) {
    return <div className="p-6 text-[var(--color-text-muted)]">Cargando bots...</div>;
  }

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Trading Bots</h1>
          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
            Grid y DCA bots automatizados — no requieren IA
          </p>
        </div>
        <div className="flex items-center gap-2">
          {scheduler && (
            <div className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[10px] font-bold",
              scheduler.is_running
                ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            )}>
              <Activity size={12} />
              {scheduler.is_running ? "Scheduler activo" : "Scheduler detenido"}
              <span className="text-[var(--color-text-muted)] ml-1">
                ({scheduler.active_grid_bots + scheduler.active_dca_bots} bots)
              </span>
            </div>
          )}
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] bg-[var(--color-primary)] text-white text-[11px] font-bold hover:opacity-90"
          >
            <Plus size={14} /> Nuevo Bot
          </button>
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3">
          <div className="flex gap-2">
            <button
              onClick={() => setTab("grid")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
                tab === "grid" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}
            >
              <Grid3x3 size={14} /> Grid Bot
            </button>
            <button
              onClick={() => setTab("dca")}
              className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
                tab === "dca" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}
            >
              <DollarSign size={14} /> DCA Bot
            </button>
          </div>

          {tab === "grid" ? (
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="Nombre (ej: BTC Grid 60k-70k)" value={gridForm.name}
                onChange={e => setGridForm({...gridForm, name: e.target.value})}
                className="col-span-2 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Símbolo (BTC/USDT)" value={gridForm.symbol}
                onChange={e => setGridForm({...gridForm, symbol: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Inversión USD" value={gridForm.investment_usd} type="number"
                onChange={e => setGridForm({...gridForm, investment_usd: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Precio inferior" value={gridForm.lower_price} type="number"
                onChange={e => setGridForm({...gridForm, lower_price: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Precio superior" value={gridForm.upper_price} type="number"
                onChange={e => setGridForm({...gridForm, upper_price: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <div className="col-span-2 flex items-center gap-2">
                <label className="text-[10px] text-[var(--color-text-muted)]">Niveles (grid):</label>
                <input type="number" value={gridForm.grid_count} min={2} max={50}
                  onChange={e => setGridForm({...gridForm, grid_count: parseInt(e.target.value) || 10})}
                  className="w-20 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)]">
                  Profit por nivel = {(parseFloat(gridForm.upper_price || "0") - parseFloat(gridForm.lower_price || "0")) / (gridForm.grid_count || 1) || 0} USD
                </span>
              </div>
              <button onClick={createGridBot}
                className="col-span-2 rounded-[8px] bg-[var(--color-success)] text-white text-[11px] font-bold py-2 hover:opacity-90">
                Crear Grid Bot
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="Nombre (ej: BTC DCA Diario)" value={dcaForm.name}
                onChange={e => setDcaForm({...dcaForm, name: e.target.value})}
                className="col-span-2 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Símbolo (BTC/USDT)" value={dcaForm.symbol}
                onChange={e => setDcaForm({...dcaForm, symbol: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <input placeholder="Compra USD" value={dcaForm.buy_amount_usd} type="number"
                onChange={e => setDcaForm({...dcaForm, buy_amount_usd: e.target.value})}
                className="rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)]">Intervalo (minutos)</label>
                <input type="number" value={dcaForm.interval_minutes} min={1}
                  onChange={e => setDcaForm({...dcaForm, interval_minutes: parseInt(e.target.value) || 1440})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)]">1440 = diario, 60 = cada hora</span>
              </div>
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)]">Máx compras (0 = infinito)</label>
                <input type="number" value={dcaForm.max_buys} min={0}
                  onChange={e => setDcaForm({...dcaForm, max_buys: parseInt(e.target.value) || 0})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
              </div>
              <div>
                <label className="text-[10px] text-[var(--color-text-muted)]">Take Profit % (0 = sin TP)</label>
                <input type="number" value={dcaForm.take_profit_pct} min={0} step="0.1"
                  onChange={e => setDcaForm({...dcaForm, take_profit_pct: parseFloat(e.target.value) || 0})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
              </div>
              <button onClick={createDCABot}
                className="col-span-2 rounded-[8px] bg-[var(--color-success)] text-white text-[11px] font-bold py-2 hover:opacity-90">
                Crear DCA Bot
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2">
        <button onClick={() => setTab("grid")}
          className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
            tab === "grid" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface)] text-[var(--color-text-muted)] border border-[var(--color-border)]")}>
          <Grid3x3 size={14} /> Grid Bots ({gridBots.length})
        </button>
        <button onClick={() => setTab("dca")}
          className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
            tab === "dca" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface)] text-[var(--color-text-muted)] border border-[var(--color-border)]")}>
          <DollarSign size={14} /> DCA Bots ({dcaBots.length})
        </button>
      </div>

      {/* Grid bots list */}
      {tab === "grid" && (
        <div className="space-y-2">
          {gridBots.length === 0 ? (
            <div className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
              <Grid3x3 size={32} className="mx-auto text-[var(--color-text-muted)] mb-2" />
              <p className="text-[12px] text-[var(--color-text-muted)]">No hay Grid Bots. Crea uno para empezar.</p>
            </div>
          ) : (
            gridBots.map(bot => (
              <div key={bot.id} className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Grid3x3 size={16} className="text-[var(--color-accent)]" />
                    <span className="text-[12px] font-bold text-[var(--color-text)]">{bot.name}</span>
                    <span className={cn("text-[9px] px-1.5 py-0.5 rounded font-bold",
                      bot.is_active ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}>
                      {bot.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {!bot.is_active ? (
                      <button onClick={() => startBot("grid", bot.id)}
                        className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)] text-[10px] font-bold hover:opacity-80">
                        <Play size={12} /> Iniciar
                      </button>
                    ) : (
                      <button onClick={() => stopBot("grid", bot.id)}
                        className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-[10px] font-bold hover:opacity-80">
                        <Square size={12} /> Detener
                      </button>
                    )}
                    <button onClick={() => deleteBot("grid", bot.id)}
                      className="p-1 rounded-[6px] text-[var(--color-text-muted)] hover:text-[var(--color-danger)]">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-2 text-[10px]">
                  <div>
                    <span className="text-[var(--color-text-muted)]">Símbolo</span>
                    <p className="font-bold text-[var(--color-text)]">{bot.symbol}</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">Rango</span>
                    <p className="font-bold text-[var(--color-text)]">${bot.lower_price} - ${bot.upper_price}</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">Niveles / Inversión</span>
                    <p className="font-bold text-[var(--color-text)]">{bot.grid_count} / ${bot.investment_usd}</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">PnL Realizado</span>
                    <p className={cn("font-bold", parseFloat(bot.realized_pnl) >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      ${parseFloat(bot.realized_pnl).toFixed(2)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3 mt-2 text-[9px] text-[var(--color-text-muted)]">
                  <span>Órdenes: {bot.orders_placed}</span>
                  <span>Ejecutadas: {bot.orders_filled}</span>
                  {bot.last_run_at && <span>Última ejecución: {new Date(bot.last_run_at).toLocaleTimeString()}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* DCA bots list */}
      {tab === "dca" && (
        <div className="space-y-2">
          {dcaBots.length === 0 ? (
            <div className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-8 text-center">
              <DollarSign size={32} className="mx-auto text-[var(--color-text-muted)] mb-2" />
              <p className="text-[12px] text-[var(--color-text-muted)]">No hay DCA Bots. Crea uno para empezar.</p>
            </div>
          ) : (
            dcaBots.map(bot => (
              <div key={bot.id} className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <DollarSign size={16} className="text-[var(--color-success)]" />
                    <span className="text-[12px] font-bold text-[var(--color-text)]">{bot.name}</span>
                    <span className={cn("text-[9px] px-1.5 py-0.5 rounded font-bold",
                      bot.is_active ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}>
                      {bot.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    {!bot.is_active ? (
                      <button onClick={() => startBot("dca", bot.id)}
                        className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)] text-[10px] font-bold hover:opacity-80">
                        <Play size={12} /> Iniciar
                      </button>
                    ) : (
                      <button onClick={() => stopBot("dca", bot.id)}
                        className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-[10px] font-bold hover:opacity-80">
                        <Square size={12} /> Detener
                      </button>
                    )}
                    <button onClick={() => deleteBot("dca", bot.id)}
                      className="p-1 rounded-[6px] text-[var(--color-text-muted)] hover:text-[var(--color-danger)]">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-2 text-[10px]">
                  <div>
                    <span className="text-[var(--color-text-muted)]">Símbolo</span>
                    <p className="font-bold text-[var(--color-text)]">{bot.symbol}</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">Compra / Intervalo</span>
                    <p className="font-bold text-[var(--color-text)]">${bot.buy_amount_usd} / {bot.interval_minutes}min</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">Invertido / Qty</span>
                    <p className="font-bold text-[var(--color-text)]">${parseFloat(bot.total_invested).toFixed(2)} / {parseFloat(bot.total_quantity).toFixed(6)}</p>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">Avg Entry / PnL</span>
                    <p className="font-bold text-[var(--color-text)]">${parseFloat(bot.avg_entry_price).toFixed(4)}</p>
                    <p className={cn("font-bold", parseFloat(bot.realized_pnl) >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                      ${parseFloat(bot.realized_pnl).toFixed(2)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-3 mt-2 text-[9px] text-[var(--color-text-muted)]">
                  <span>Compras: {bot.buys_executed}{bot.max_buys > 0 ? `/${bot.max_buys}` : ""}</span>
                  {bot.take_profit_pct !== "0" && <span>TP: {bot.take_profit_pct}%</span>}
                  {bot.last_buy_at && <span>Última compra: {new Date(bot.last_buy_at).toLocaleString()}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
