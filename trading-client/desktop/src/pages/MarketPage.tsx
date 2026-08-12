import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "../lib/api";
import { useLivePrices } from "../hooks/useLivePrices";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { toast } from "../components/ui/Toast";
import { fmt, fmtVol, fmtTime } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";

export function MarketPage() {
  const [movers, setMovers] = useState<{
    gainers: any[];
    losers: any[];
  } | null>(null);
  const [marketType, setMarketType] = useState("spot");

  // Real-time prices via WebSocket
  const { prices: wsPrices, connected: wsConnected, lastUpdate } = useLivePrices([], 10000);
  const livePrices = useMemo(() => {
    return Object.entries(wsPrices).map(([symbol, price]) => ({ symbol, price }));
  }, [wsPrices]);

  const loadMovers = useCallback(async () => {
    try {
      const r = await api<any>(`/api/market/movers?type=${marketType}`);
      setMovers(r);
    } catch {}
  }, [marketType]);

  useEffect(() => {
    loadMovers();
  }, [loadMovers]);

  const importSignal = async (
    symbol: string,
    type: string,
    price?: number
  ) => {
    try {
      await api("/api/signals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, signal_type: type, price }),
      });
      toast(`Señal ${type} importada para ${symbol}`);
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  return (
    <div className="p-5 space-y-4">
      {/* Controls */}
      <div className="flex gap-2 items-center">
        <Select
          value={marketType}
          onChange={(e) => setMarketType(e.target.value)}
        >
          <option value="spot">Spot (USDT)</option>
          <option value="futures">Futuros USD (USDT)</option>
        </Select>
        <Button variant="primary" size="sm" onClick={loadMovers}>
          Actualizar
        </Button>
      </div>

      {/* Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-success)] mb-3">
            Top Ganadores 24h
          </h3>
          <Table>
            <thead>
              <Tr>
                <Th>Símbolo</Th>
                <Th>Precio</Th>
                <Th>Cambio %</Th>
                <Th>Vol</Th>
                <Th>Acción</Th>
              </Tr>
            </thead>
            <tbody>
              {movers?.gainers?.slice(0, 15).map((m) => (
                <Tr key={m.symbol}>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      <CryptoIcon symbol={m.symbol} size={18} />
                      {m.symbol}
                    </div>
                  </Td>
                  <Td>${fmt(m.price)}</Td>
                  <Td className="text-[var(--color-success)] font-semibold">
                    +{fmt(m.change_pct)}%
                  </Td>
                  <Td>{fmtVol(m.volume)}</Td>
                  <Td>
                    <div className="flex gap-1">
                      <Button
                        variant="success"
                        size="sm"
                        onClick={() => importSignal(m.symbol, "BUY", m.price)}
                      >
                        BUY
                      </Button>
                    </div>
                  </Td>
                </Tr>
              )) || (
                <Tr>
                  <Td className="text-center text-[var(--color-text-muted)]">
                    Cargando...
                  </Td>
                </Tr>
              )}
            </tbody>
          </Table>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-[var(--color-danger)] mb-3">
            Top Perdedores 24h
          </h3>
          <Table>
            <thead>
              <Tr>
                <Th>Símbolo</Th>
                <Th>Precio</Th>
                <Th>Cambio %</Th>
                <Th>Vol</Th>
                <Th>Acción</Th>
              </Tr>
            </thead>
            <tbody>
              {movers?.losers?.slice(0, 15).map((m) => (
                <Tr key={m.symbol}>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      <CryptoIcon symbol={m.symbol} size={18} />
                      {m.symbol}
                    </div>
                  </Td>
                  <Td>${fmt(m.price)}</Td>
                  <Td className="text-[var(--color-danger)] font-semibold">
                    {fmt(m.change_pct)}%
                  </Td>
                  <Td>{fmtVol(m.volume)}</Td>
                  <Td>
                    <div className="flex gap-1">
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => importSignal(m.symbol, "SELL", m.price)}
                      >
                        SELL
                      </Button>
                    </div>
                  </Td>
                </Tr>
              )) || (
                <Tr>
                  <Td className="text-center text-[var(--color-text-muted)]">
                    Cargando...
                  </Td>
                </Tr>
              )}
            </tbody>
          </Table>
        </Card>
      </div>

      {/* Live prices */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[var(--color-primary)]">
            Precios en Tiempo Real
          </h3>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-[var(--color-success)]" : "bg-[var(--color-danger)]"} animate-pulse`} />
            <span className="text-[10px] font-bold text-[var(--color-text-muted)]">
              {wsConnected ? "WebSocket LIVE" : "Polling..."}
            </span>
          </div>
        </div>
        <Table>
          <thead>
            <Tr>
              <Th>Símbolo</Th>
              <Th>Precio</Th>
              <Th>Última actualización</Th>
            </Tr>
          </thead>
          <tbody>
            {livePrices.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  Conectando...
                </Td>
              </Tr>
            ) : (
              livePrices.map((p) => (
                <Tr key={p.symbol}>
                  <Td className="font-semibold">
                    <div className="flex items-center gap-1.5">
                      <CryptoIcon symbol={p.symbol} size={18} />
                      {p.symbol}
                    </div>
                  </Td>
                  <Td>${fmt(p.price)}</Td>
                  <Td className="text-[var(--color-text-muted)]">
                    {lastUpdate > 0
                      ? fmtTime(new Date(lastUpdate).toISOString())
                      : "--"}
                  </Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
