import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { cn, fmtDate, fmtTime } from "../lib/utils";
import { Tooltip, InfoPanel } from "../components/common/Tooltip";
import { Play, Square, Trash2, Plus, Grid3x3, DollarSign, Activity, TrendingUp, Clock, Target, Info } from "lucide-react";

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

interface TradingSymbol {
  symbol: string;
  base: string;
  quote: string;
  volume: number;
  last_price: number;
  change_pct: number;
}

// ─── Symbol Selector (CCXT dropdown with search) ───

function SymbolSelector({
  value, onChange, symbols, loading, quoteAsset, onQuoteChange, quoteAssets,
}: {
  value: string;
  onChange: (symbol: string) => void;
  symbols: TradingSymbol[];
  loading: boolean;
  quoteAsset: string;
  onQuoteChange: (q: string) => void;
  quoteAssets: string[];
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = symbols.filter(s =>
    s.symbol.toLowerCase().includes(search.toLowerCase()) ||
    s.base.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 50);

  return (
    <div className="relative">
      <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
        Simbolo
        <Tooltip text="Selecciona el par de trading de los disponibles en el exchange (via CCXT). Los simbolos estan ordenados por volumen. Puedes buscar por nombre (BTC, ETH, SOL, etc.).">
          <Info size={13} className="text-[var(--color-text-muted)] cursor-help" />
        </Tooltip>
      </label>

      {/* Quote asset selector */}
      <div className="flex gap-1 mb-1.5 flex-wrap">
        {(quoteAssets.length > 0 ? quoteAssets.slice(0, 8) : ["USDT", "BTC", "ETH", "FDUSD", "BNB"]).map(q => (
          <button
            key={q}
            onClick={() => onQuoteChange(q)}
            className={cn(
              "px-2 py-0.5 rounded-[4px] text-[9px] font-bold transition-colors",
              quoteAsset === q
                ? "bg-[var(--color-primary)] text-white"
                : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            )}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Selected symbol display + dropdown trigger */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px] hover:border-[var(--color-primary)]"
      >
        <span className="font-bold text-[var(--color-text)]">{value || "Seleccionar..."}</span>
        <span className="text-[var(--color-text-muted)]">{loading ? "Cargando..." : "▼"}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-[8px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-xl max-h-[280px] flex flex-col">
          {/* Search input */}
          <input
            autoFocus
            placeholder="Buscar (BTC, ETH, SOL...)"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full rounded-t-[8px] bg-[var(--color-surface-2)] border-b border-[var(--color-border)] p-2 text-[11px] outline-none"
          />

          {/* Results */}
          <div className="overflow-y-auto flex-1">
            {loading && (
              <div className="p-3 text-center text-[10px] text-[var(--color-text-muted)]">Cargando simbolos...</div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="p-3 text-center text-[10px] text-[var(--color-text-muted)]">No se encontraron simbolos</div>
            )}
            {!loading && filtered.map(s => (
              <button
                key={s.symbol}
                onClick={() => {
                  onChange(s.symbol);
                  setOpen(false);
                  setSearch("");
                }}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 text-[11px] hover:bg-[var(--color-surface-2)] transition-colors text-left",
                  s.symbol === value && "bg-[var(--color-primary)]/10"
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[var(--color-text)]">{s.base}</span>
                  <span className="text-[var(--color-text-muted)] text-[9px]">/{s.quote}</span>
                </div>
                <div className="flex items-center gap-2 text-[9px] text-[var(--color-text-muted)]">
                  {s.last_price > 0 && (
                    <span>${s.last_price < 1 ? s.last_price.toFixed(6) : s.last_price.toLocaleString()}</span>
                  )}
                  {s.change_pct !== 0 && (
                    <span className={s.change_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
                      {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(1)}%
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Component ───

export function BotsPage() {
  const [tab, setTab] = useState<"grid" | "dca">("grid");
  const [gridBots, setGridBots] = useState<GridBot[]>([]);
  const [dcaBots, setDCABots] = useState<DCABot[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  // Symbols from CCXT
  const [symbols, setSymbols] = useState<TradingSymbol[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(false);
  const [quoteAsset, setQuoteAsset] = useState("USDT");
  const [quoteAssets, setQuoteAssets] = useState<string[]>([]);

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

  const loadSymbols = useCallback(async (quote: string = "USDT") => {
    setSymbolsLoading(true);
    try {
      const r = await api<any>(`/api/bots/symbols?quote=${quote}&limit=300`);
      if (r.status === "ok") {
        setSymbols(r.symbols || []);
        setQuoteAssets(r.quote_assets || []);
      }
    } catch (e) {
      console.error("Error loading symbols:", e);
    } finally {
      setSymbolsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Load symbols when create form opens or quote asset changes
  useEffect(() => {
    if (showCreate && symbols.length === 0) {
      loadSymbols(quoteAsset);
    }
  }, [showCreate]);

  useEffect(() => {
    if (showCreate) loadSymbols(quoteAsset);
  }, [quoteAsset]);

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
      {/* Hero Panel */}
      <div className="rounded-[16px] bg-gradient-to-br from-[var(--color-primary)]/10 via-[var(--color-surface)] to-[var(--color-surface)] border border-[var(--color-primary)]/20 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-[12px] bg-[var(--color-primary)]/15 p-3 flex-shrink-0">
              <Grid3x3 size={28} className="text-[var(--color-primary)]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[var(--color-text)]">Trading Bots Automatizados</h1>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-1 max-w-2xl">
                Estrategias automatizadas que operan 24/7 sin intervención de IA. Grid trading para mercados laterales
                y DCA para acumulación gradual. Compatible con cualquier exchange via CCXT.
              </p>
              <div className="flex flex-wrap gap-2 mt-2.5">
                <span className="flex items-center gap-1 rounded-[6px] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-bold text-[var(--color-text-muted)]">
                  <Grid3x3 size={11} /> Grid Trading
                </span>
                <span className="flex items-center gap-1 rounded-[6px] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-bold text-[var(--color-text-muted)]">
                  <DollarSign size={11} /> DCA
                </span>
                <span className="flex items-center gap-1 rounded-[6px] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-bold text-[var(--color-text-muted)]">
                  <Activity size={11} /> Loop 30s
                </span>
                <span className="flex items-center gap-1 rounded-[6px] bg-[var(--color-surface-2)] px-2 py-1 text-[10px] font-bold text-[var(--color-text-muted)]">
                  <TrendingUp size={11} /> CCXT Multi-exchange
                </span>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
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
      </div>

      {/* InfoPanel: Cómo usar los bots */}
      <InfoPanel title="Como usar los Trading Bots — guia completa" className="mb-2">
        <div className="space-y-2">
          <p><strong className="text-[var(--color-accent)]">Grid Bot — para mercados laterales (rango de precio):</strong></p>
          <p>1. Define un rango de precio (ej: BTC $60,000 - $70,000) y el numero de niveles (ej: 10).</p>
          <p>2. El bot coloca buy orders en los niveles inferiores y sell orders en los superiores.</p>
          <p>3. Cuando un buy se ejecuta, coloca automaticamente un sell en el nivel superior (profit = diferencia entre niveles).</p>
          <p>4. Cuando un sell se ejecuta, coloca un buy en el nivel inferior. El ciclo se repite mientras el precio oscile en el rango.</p>
          <p>5. Profit por nivel = (precio superior - precio inferior) / numero de niveles. Mas niveles = mas profit por nivel pero menos frecuencia.</p>
          <p className="text-[var(--color-warning)]">⚠️ Funciona mejor en mercados laterales. Si el precio sale del rango, el bot deja de operar.</p>
          <br />
          <p><strong className="text-[var(--color-success)]">DCA Bot — para acumulacion a largo plazo:</strong></p>
          <p>1. Define un monto de compra (ej: $100 USD) y un intervalo (ej: 1440 min = diario).</p>
          <p>2. El bot compra automaticamente ese monto cada intervalo, sin importar el precio.</p>
          <p>3. Reduce el impacto de la volatilidad promediando el precio de entrada a lo largo del tiempo.</p>
          <p>4. Opcional: configura Take Profit % para vender todo cuando el precio suba X%.</p>
          <p>5. Max compras (0 = ilimitado) limita cuantas compras hara el bot antes de detenerse.</p>
          <p className="text-[var(--color-warning)]">⚠️ Ideal para accumulation de BTC, ETH u otros activos a largo plazo. No es para trading activo.</p>
          <br />
          <p><strong className="text-[var(--color-text)]">Scheduler:</strong> El scheduler corre cada 30 segundos en background. Se inicia automaticamente al arrancar el primer bot. Mientras este activo, los bots ejecutaran sus ciclos sin intervencion manual.</p>
          <p><strong className="text-[var(--color-text)]">Broker:</strong> Los bots usan el broker configurado (MockBroker en paper, BinanceBroker/CCXTAdapter en live). Funciona con cualquier exchange soportado por CCXT (Binance, Bybit, OKX, Kraken, etc.).</p>
        </div>
      </InfoPanel>

      {/* Create form */}
      {showCreate && (
        <div className="rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3">
          <div className="flex gap-2">
            <Tooltip text="Grid Bot: coloca ordenes de compra y venta en niveles de precio dentro de un rango. Ideal para mercados laterales donde el precio oscila entre soporte y resistencia.">
              <button
                onClick={() => setTab("grid")}
                className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
                  tab === "grid" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}
              >
                <Grid3x3 size={14} /> Grid Bot
              </button>
            </Tooltip>
            <Tooltip text="DCA Bot: compra una cantidad fija de USD cada X intervalo. Promedia el precio de entrada a lo largo del tiempo. Ideal para acumular activos a largo plazo.">
              <button
                onClick={() => setTab("dca")}
                className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
                  tab === "dca" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}
              >
                <DollarSign size={14} /> DCA Bot
              </button>
            </Tooltip>
          </div>

          {tab === "grid" ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Nombre del bot</label>
                <input placeholder="ej: BTC Grid 60k-70k" value={gridForm.name}
                  onChange={e => setGridForm({...gridForm, name: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div>
                <SymbolSelector
                  value={gridForm.symbol}
                  onChange={sym => setGridForm({...gridForm, symbol: sym})}
                  symbols={symbols}
                  loading={symbolsLoading}
                  quoteAsset={quoteAsset}
                  onQuoteChange={setQuoteAsset}
                  quoteAssets={quoteAssets}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  Inversion USD
                  <Tooltip text="Capital total que el bot usara para colocar ordenes. Se divide entre los niveles del grid. Ej: $1000 con 10 niveles = $100 por nivel." icon />
                </label>
                <input placeholder="1000" value={gridForm.investment_usd} type="number"
                  onChange={e => setGridForm({...gridForm, investment_usd: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  Precio inferior
                  <Tooltip text="Limite inferior del rango de trading. El bot coloca buy orders cerca de este precio. Debe ser menor al precio superior." icon />
                </label>
                <input placeholder="60000" value={gridForm.lower_price} type="number"
                  onChange={e => setGridForm({...gridForm, lower_price: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  Precio superior
                  <Tooltip text="Limite superior del rango de trading. El bot coloca sell orders cerca de este precio. Debe ser mayor al precio inferior." icon />
                </label>
                <input placeholder="70000" value={gridForm.upper_price} type="number"
                  onChange={e => setGridForm({...gridForm, upper_price: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div className="col-span-2 flex items-center gap-2 flex-wrap">
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase flex items-center gap-1">
                  Niveles (grid)
                  <Tooltip text="Numero de divisiones del rango. Mas niveles = mas ordenes pero menor profit por nivel. Menos niveles = menos ordenes pero mayor profit por nivel. Recomendado: 8-15." icon />
                </label>
                <input type="number" value={gridForm.grid_count} min={2} max={50}
                  onChange={e => setGridForm({...gridForm, grid_count: parseInt(e.target.value) || 10})}
                  className="w-20 rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)] flex items-center gap-1">
                  <TrendingUp size={10} />
                  Profit por nivel = {((parseFloat(gridForm.upper_price || "0") - parseFloat(gridForm.lower_price || "0")) / (gridForm.grid_count || 1) || 0).toFixed(2)} USD
                </span>
              </div>
              <button onClick={createGridBot}
                className="col-span-2 rounded-[8px] bg-[var(--color-success)] text-white text-[11px] font-bold py-2 hover:opacity-90">
                Crear Grid Bot
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 block">Nombre del bot</label>
                <input placeholder="ej: BTC DCA Diario" value={dcaForm.name}
                  onChange={e => setDcaForm({...dcaForm, name: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div>
                <SymbolSelector
                  value={dcaForm.symbol}
                  onChange={sym => setDcaForm({...dcaForm, symbol: sym})}
                  symbols={symbols}
                  loading={symbolsLoading}
                  quoteAsset={quoteAsset}
                  onQuoteChange={setQuoteAsset}
                  quoteAssets={quoteAssets}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  Compra USD
                  <Tooltip text="Monto en USD que el bot comprara en cada ciclo. Ej: $100 = comprara $100 de BTC cada intervalo." icon />
                </label>
                <input placeholder="100" value={dcaForm.buy_amount_usd} type="number"
                  onChange={e => setDcaForm({...dcaForm, buy_amount_usd: e.target.value})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px]" />
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  <Clock size={11} /> Intervalo (minutos)
                  <Tooltip text="Tiempo entre cada compra. 1440 = diario (24h), 60 = cada hora, 10080 = semanal. El bot comprara automaticamente cada X minutos." icon />
                </label>
                <input type="number" value={dcaForm.interval_minutes} min={1}
                  onChange={e => setDcaForm({...dcaForm, interval_minutes: parseInt(e.target.value) || 1440})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)]">1440 = diario, 60 = cada hora</span>
              </div>
              <div>
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  Max compras
                  <Tooltip text="Numero maximo de compras que hara el bot. 0 = ilimitado (compra para siempre). Ej: 30 = hara 30 compras y se detendra." icon />
                </label>
                <input type="number" value={dcaForm.max_buys} min={0}
                  onChange={e => setDcaForm({...dcaForm, max_buys: parseInt(e.target.value) || 0})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)]">0 = infinito</span>
              </div>
              <div className="col-span-2">
                <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
                  <Target size={11} /> Take Profit %
                  <Tooltip text="Porcentaje de ganancia al que el bot vende toda la posicion automaticamente. 0 = sin take profit (acumula para siempre). Ej: 20% = vende todo cuando el precio suba 20% sobre el avg entry." icon />
                </label>
                <input type="number" value={dcaForm.take_profit_pct} min={0} step="0.1"
                  onChange={e => setDcaForm({...dcaForm, take_profit_pct: parseFloat(e.target.value) || 0})}
                  className="w-full rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2 text-[11px]" />
                <span className="text-[9px] text-[var(--color-text-muted)]">0 = sin TP (acumula para siempre)</span>
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
        <Tooltip text="Grid Bots: estrategia de grid trading que coloca ordenes en niveles de precio dentro de un rango. Ideal para mercados laterales.">
          <button onClick={() => setTab("grid")}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
              tab === "grid" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface)] text-[var(--color-text-muted)] border border-[var(--color-border)]")}>
            <Grid3x3 size={14} /> Grid Bots ({gridBots.length})
          </button>
        </Tooltip>
        <Tooltip text="DCA Bots: Dollar Cost Averaging — compra periodica de un monto fijo. Ideal para acumular activos a largo plazo.">
          <button onClick={() => setTab("dca")}
            className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-[11px] font-bold",
              tab === "dca" ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface)] text-[var(--color-text-muted)] border border-[var(--color-border)]")}>
            <DollarSign size={14} /> DCA Bots ({dcaBots.length})
          </button>
        </Tooltip>
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
                    <Tooltip text={bot.is_active
                      ? "El bot esta corriendo. El scheduler ejecuta check_and_rebalance cada 30 segundos."
                      : "El bot esta detenido. No coloca ni cierra ordenes. Click Iniciar para activarlo."}>
                      <span className={cn("text-[9px] px-1.5 py-0.5 rounded font-bold cursor-help",
                        bot.is_active ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}>
                        {bot.status}
                      </span>
                    </Tooltip>
                  </div>
                  <div className="flex items-center gap-1">
                    {!bot.is_active ? (
                      <Tooltip text="Inicia el bot: coloca las ordenes iniciales del grid y activa el scheduler.">
                        <button onClick={() => startBot("grid", bot.id)}
                          className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)] text-[10px] font-bold hover:opacity-80">
                          <Play size={12} /> Iniciar
                        </button>
                      </Tooltip>
                    ) : (
                      <Tooltip text="Detiene el bot: cancela las ordenes abiertas y desactiva el scheduler para este bot.">
                        <button onClick={() => stopBot("grid", bot.id)}
                          className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-[10px] font-bold hover:opacity-80">
                          <Square size={12} /> Detener
                        </button>
                      </Tooltip>
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
                  {bot.last_run_at && <span>Última ejecución: {fmtTime(bot.last_run_at)}</span>}
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
                    <Tooltip text={bot.is_active
                      ? "El bot esta corriendo. Compra automaticamente cada intervalo configurado."
                      : "El bot esta detenido. No hace compras. Click Iniciar para activarlo."}>
                      <span className={cn("text-[9px] px-1.5 py-0.5 rounded font-bold cursor-help",
                        bot.is_active ? "bg-[var(--color-success)]/10 text-[var(--color-success)]" : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]")}>
                        {bot.status}
                      </span>
                    </Tooltip>
                  </div>
                  <div className="flex items-center gap-1">
                    {!bot.is_active ? (
                      <Tooltip text="Inicia el bot: activa las compras periodicas segun el intervalo configurado.">
                        <button onClick={() => startBot("dca", bot.id)}
                          className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-success)]/10 text-[var(--color-success)] text-[10px] font-bold hover:opacity-80">
                          <Play size={12} /> Iniciar
                        </button>
                      </Tooltip>
                    ) : (
                      <Tooltip text="Detiene el bot: cancela las compras futuras. La posicion acumulada se mantiene.">
                        <button onClick={() => stopBot("dca", bot.id)}
                          className="flex items-center gap-1 px-2 py-1 rounded-[6px] bg-[var(--color-danger)]/10 text-[var(--color-danger)] text-[10px] font-bold hover:opacity-80">
                          <Square size={12} /> Detener
                        </button>
                      </Tooltip>
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
                  {bot.last_buy_at && <span>Última compra: {fmtDate(bot.last_buy_at)}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
