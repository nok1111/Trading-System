import { useState, useEffect, useCallback } from "react";
import { Star, X, Plus, Search } from "lucide-react";
import { watchlistApi, type WatchlistItem } from "../../lib/watchlistApi";
import { toast } from "../ui/Toast";
import { CryptoIcon } from "../CryptoIcon";

interface WatchlistProps {
  onSymbolClick?: (symbol: string) => void;
}

export function Watchlist({ onSymbolClick }: WatchlistProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [prices, setPrices] = useState<Record<string, number | null>>({});
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ symbol: string; base: string }[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  const loadWatchlist = useCallback(async () => {
    try {
      const data = await watchlistApi.get();
      setItems(data || []);
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  // Fetch prices for watchlist symbols
  useEffect(() => {
    if (items.length === 0) return;
    const fetchPrices = async () => {
      const newPrices: Record<string, number | null> = {};
      await Promise.all(
        items.map(async (item) => {
          try {
            const token = localStorage.getItem("jwt") || "";
            const resp = await fetch(
              `/api/binance/price?symbol=${encodeURIComponent(item.symbol)}`,
              { headers: { Authorization: `Bearer ${token}` } }
            );
            if (resp.ok) {
              const data = await resp.json();
              newPrices[item.symbol] = data.price || null;
            }
          } catch {
            newPrices[item.symbol] = null;
          }
        })
      );
      setPrices(newPrices);
    };
    fetchPrices();
    const interval = setInterval(fetchPrices, 10000);
    return () => clearInterval(interval);
  }, [items]);

  // Search symbols
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const token = localStorage.getItem("jwt") || "";
        const resp = await fetch(
          `/api/binance/price?search=${encodeURIComponent(searchQuery)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (resp.ok) {
          const data = await resp.json();
          if (Array.isArray(data)) {
            setSearchResults(data.slice(0, 10).map((s: any) => ({
              symbol: s.symbol || s,
              base: (s.symbol || s).replace("USDT", "").replace("USD", ""),
            })));
          }
        }
      } catch {
        // Silent
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleAdd = async (symbol: string) => {
    try {
      await watchlistApi.add(symbol);
      setShowAdd(false);
      setSearchQuery("");
      toast(`${symbol} añadido a watchlist`, true);
      loadWatchlist();
    } catch (e: any) {
      toast(e.message || "Error al añadir", false);
    }
  };

  const handleRemove = async (symbol: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await watchlistApi.remove(symbol);
      toast(`${symbol} removido`, true);
      loadWatchlist();
    } catch (e: any) {
      toast(e.message || "Error al remover", false);
    }
  };

  const handleDragStart = (index: number) => setDraggedIndex(index);
  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    const newItems = [...items];
    [newItems[draggedIndex], newItems[index]] = [newItems[index], newItems[draggedIndex]];
    setItems(newItems);
    setDraggedIndex(index);
  };
  const handleDragEnd = async () => {
    setDraggedIndex(null);
    try {
      await watchlistApi.reorder(items.map((i) => i.symbol));
    } catch {
      // Silent — reorder failed
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-[12px] text-[var(--color-text-muted)]">
        Cargando watchlist...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Star size={16} className="text-yellow-400" />
          <h2 className="text-[14px] font-extrabold text-[var(--color-text)]">Watchlist</h2>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1 px-2.5 h-7 rounded-[8px] text-[11px] font-bold bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
        >
          <Plus size={13} />
          Añadir
        </button>
      </div>

      {showAdd && (
        <div className="relative rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-2">
          <div className="flex items-center gap-2">
            <Search size={14} className="text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar símbolo..."
              autoFocus
              className="flex-1 bg-transparent text-[12px] text-[var(--color-text)] outline-none"
            />
          </div>
          {searchResults.length > 0 && (
            <div className="mt-2 space-y-0.5 max-h-[200px] overflow-y-auto">
              {searchResults.map((r) => (
                <button
                  key={r.symbol}
                  onClick={() => handleAdd(r.symbol)}
                  className="flex items-center gap-2 w-full px-2 py-1.5 rounded-[6px] hover:bg-[var(--color-surface-hover)] text-left"
                >
                  <CryptoIcon symbol={r.base} size={18} />
                  <span className="text-[12px] font-bold text-[var(--color-text)]">{r.symbol}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <div className="text-center py-8 text-[12px] text-[var(--color-text-muted)]">
          <Star size={32} className="mx-auto mb-2 opacity-30" />
          Sin símbolos en watchlist
          <div className="mt-1 text-[11px]">Añade símbolos para seguirlos</div>
        </div>
      ) : (
        <div className="space-y-0.5">
          {items.map((item, index) => {
            const base = item.symbol.replace("USDT", "").replace("USD", "");
            const price = prices[item.symbol];
            return (
              <div
                key={item.symbol}
                draggable
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                onClick={() => onSymbolClick?.(item.symbol)}
                className="group flex items-center gap-2 px-2.5 py-2 rounded-[8px] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors"
              >
                <CryptoIcon symbol={base} size={20} />
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-bold text-[var(--color-text)]">{item.symbol}</div>
                  {price !== null && price !== undefined && (
                    <div className="text-[11px] text-[var(--color-text-muted)]">
                      ${price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => handleRemove(item.symbol, e)}
                  className="opacity-0 group-hover:opacity-100 flex items-center justify-center w-6 h-6 rounded-[6px] text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-all"
                >
                  <X size={13} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
