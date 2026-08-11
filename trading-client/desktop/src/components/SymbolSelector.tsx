/** Reusable symbol selector dropdown with search.
 *
 * Fetches trading symbols from /api/bots/symbols (CCXT/Binance public data).
 * Supports filtering by quote asset (USDT, BTC, ETH, etc.).
 *
 * Used by: BotsPage (grid/DCA bots), SocialPage (publish signal).
 */

import { useCallback, useEffect, useState } from "react";
import { Info } from "lucide-react";
import { cn } from "../lib/utils";
import { api } from "../lib/api";
import { Tooltip } from "./common/Tooltip";

export interface TradingSymbol {
  symbol: string;
  base: string;
  quote: string;
  volume: number;
  last_price: number;
  change_pct: number;
}

export function SymbolSelector({
  value,
  onChange,
  quoteAsset: initialQuote = "USDT",
  label = "Símbolo",
  tooltip = "Selecciona el par de trading. Puedes buscar por nombre (BTC, ETH, SOL, etc.).",
}: {
  value: string;
  onChange: (symbol: string) => void;
  quoteAsset?: string;
  label?: string;
  tooltip?: string;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [symbols, setSymbols] = useState<TradingSymbol[]>([]);
  const [loading, setLoading] = useState(false);
  const [quoteAsset, setQuoteAsset] = useState(initialQuote);
  const [quoteAssets, setQuoteAssets] = useState<string[]>([]);

  const loadSymbols = useCallback(async (quote: string) => {
    setLoading(true);
    try {
      const r = await api<any>(`/api/bots/symbols?quote=${quote}&limit=300`);
      if (r.status === "ok") {
        setSymbols(r.symbols || []);
        setQuoteAssets(r.quote_assets || []);
      }
    } catch {
      // silent fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && symbols.length === 0) {
      loadSymbols(quoteAsset);
    }
  }, [open]);

  useEffect(() => {
    if (open) loadSymbols(quoteAsset);
  }, [quoteAsset, open]);

  const filtered = symbols
    .filter(
      (s) =>
        s.symbol.toLowerCase().includes(search.toLowerCase()) ||
        s.base.toLowerCase().includes(search.toLowerCase())
    )
    .slice(0, 50);

  return (
    <div className="relative">
      <label className="text-[10px] font-bold text-[var(--color-text-muted)] uppercase mb-1 flex items-center gap-1">
        {label}
        <Tooltip text={tooltip}>
          <Info size={13} className="text-[var(--color-text-muted)] cursor-help" />
        </Tooltip>
      </label>

      {/* Quote asset selector */}
      <div className="flex gap-1 mb-1.5 flex-wrap">
        {(quoteAssets.length > 0
          ? quoteAssets.slice(0, 8)
          : ["USDT", "BTC", "ETH", "FDUSD", "BNB"]
        ).map((q) => (
          <button
            key={q}
            onClick={() => setQuoteAsset(q)}
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
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between rounded-[8px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2.5 text-[11px] hover:border-[var(--color-primary)]"
      >
        <span className="font-bold text-[var(--color-text)]">{value || "Seleccionar..."}</span>
        <span className="text-[var(--color-text-muted)]">{loading ? "Cargando..." : "▼"}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <>
          {/* Click-outside overlay */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute z-50 mt-1 w-full rounded-[8px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-xl max-h-[280px] flex flex-col">
            {/* Search input */}
            <input
              autoFocus
              placeholder="Buscar (BTC, ETH, SOL...)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-t-[8px] bg-[var(--color-surface-2)] border-b border-[var(--color-border)] p-2 text-[11px] outline-none"
            />

            {/* Results */}
            <div className="overflow-y-auto flex-1">
              {loading && (
                <div className="p-3 text-center text-[10px] text-[var(--color-text-muted)]">
                  Cargando símbolos...
                </div>
              )}
              {!loading && filtered.length === 0 && (
                <div className="p-3 text-center text-[10px] text-[var(--color-text-muted)]">
                  No se encontraron símbolos
                </div>
              )}
              {!loading &&
                filtered.map((s) => (
                  <button
                    key={s.symbol}
                    type="button"
                    onClick={() => {
                      // Convert CCXT format (BTC/USDT) to broker format (BTCUSDT)
                      onChange(s.symbol.replace("/", ""));
                      setOpen(false);
                      setSearch("");
                    }}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 text-[11px] hover:bg-[var(--color-surface-2)] transition-colors text-left",
                      s.symbol.replace("/", "") === value && "bg-[var(--color-primary)]/10"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-[var(--color-text)]">{s.base}</span>
                      <span className="text-[var(--color-text-muted)] text-[9px]">/{s.quote}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[9px] text-[var(--color-text-muted)]">
                      {s.last_price > 0 && (
                        <span>
                          ${s.last_price < 1 ? s.last_price.toFixed(6) : s.last_price.toLocaleString()}
                        </span>
                      )}
                      {s.change_pct !== 0 && (
                        <span
                          className={
                            s.change_pct >= 0
                              ? "text-[var(--color-success)]"
                              : "text-[var(--color-danger)]"
                          }
                        >
                          {s.change_pct >= 0 ? "+" : ""}
                          {s.change_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </button>
                ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
