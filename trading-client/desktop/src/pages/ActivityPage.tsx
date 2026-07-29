import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Select } from "../components/ui/Input";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { toast } from "../components/ui/Toast";
import { fmt, fmtDate } from "../lib/utils";
import { CryptoIcon } from "../components/CryptoIcon";

export function ActivityPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [backtests, setBacktests] = useState<any[]>([]);
  const [sigSymbol, setSigSymbol] = useState("");
  const [manSig, setManSig] = useState({
    symbol: "",
    type: "BUY",
    price: "",
    note: "",
  });

  const loadAll = useCallback(async () => {
    try {
      const s = await api<any[]>(
        "/api/signals" + (sigSymbol ? `?symbol=${sigSymbol}` : "")
      );
      setSignals(s);
    } catch {}
    try {
      const o = await api<any[]>("/api/orders");
      setOrders(o);
    } catch {}
    try {
      const t = await api<any[]>("/api/trades");
      setTrades(t);
    } catch {}
    try {
      const b = await api<any[]>("/api/backtests");
      setBacktests(b);
    } catch {}
  }, [sigSymbol]);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 5000);
    return () => clearInterval(id);
  }, [loadAll]);

  const addManualSignal = async () => {
    if (!manSig.symbol) {
      toast("Símbolo requerido", false);
      return;
    }
    try {
      await api("/api/signals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: manSig.symbol.toUpperCase(),
          signal_type: manSig.type,
          price: manSig.price ? parseFloat(manSig.price) : undefined,
          note: manSig.note || undefined,
        }),
      });
      toast("Señal agregada");
      setManSig({ symbol: "", type: "BUY", price: "", note: "" });
      loadAll();
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  const deleteSignal = async (id: number) => {
    try {
      await api(`/api/signals/${id}`, { method: "DELETE" });
      toast("Señal eliminada");
      loadAll();
    } catch (e: any) {
      toast(e.message, false);
    }
  };

  return (
    <div className="p-5 space-y-4">
      {/* Manual signal */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
          Importar Señal Manual
        </h3>
        <div className="flex gap-2 flex-wrap items-center">
          <Input
            placeholder="Símbolo (ej: BTCUSDT)"
            value={manSig.symbol}
            onChange={(e) =>
              setManSig({ ...manSig, symbol: e.target.value })
            }
            className="w-36"
          />
          <Select
            value={manSig.type}
            onChange={(e) => setManSig({ ...manSig, type: e.target.value })}
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
            <option value="HOLD">HOLD</option>
          </Select>
          <Input
            type="number"
            placeholder="Precio (opcional)"
            value={manSig.price}
            onChange={(e) => setManSig({ ...manSig, price: e.target.value })}
            className="w-32"
          />
          <Input
            placeholder="Nota (opcional)"
            value={manSig.note}
            onChange={(e) => setManSig({ ...manSig, note: e.target.value })}
            className="w-48"
          />
          <Button variant="success" size="sm" onClick={addManualSignal}>
            + Agregar
          </Button>
        </div>
      </Card>

      {/* Signals */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[var(--color-primary)]">
            Señales Recientes
          </h3>
          <div className="flex gap-2">
            <Input
              placeholder="Filtrar símbolo"
              value={sigSymbol}
              onChange={(e) => setSigSymbol(e.target.value)}
              className="w-36"
            />
            <Button variant="primary" size="sm" onClick={loadAll}>
              Filtrar
            </Button>
          </div>
        </div>
        <Table>
          <thead>
            <Tr>
              <Th>ID</Th>
              <Th>Fecha</Th>
              <Th>Símbolo</Th>
              <Th>Tipo</Th>
              <Th>Confianza</Th>
              <Th>Estrategia</Th>
              <Th>Estado</Th>
              <Th>Acción</Th>
            </Tr>
          </thead>
          <tbody>
            {signals.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  Sin señales
                </Td>
              </Tr>
            ) : (
              signals.slice(-20).reverse().map((s) => (
                <Tr key={s.id}>
                  <Td>{s.id}</Td>
                  <Td>{fmtDate(s.timestamp)}</Td>
                  <Td><div className="flex items-center gap-1.5"><CryptoIcon symbol={s.symbol} size={18} />{s.symbol}</div></Td>
                  <Td>
                    <span
                      className={
                        s.signal_type === "BUY"
                          ? "text-[var(--color-success)] font-semibold"
                          : s.signal_type === "SELL"
                            ? "text-[var(--color-danger)] font-semibold"
                            : "text-[var(--color-text-muted)]"
                      }
                    >
                      {s.signal_type}
                    </span>
                  </Td>
                  <Td>{fmt(s.confidence)}</Td>
                  <Td>{s.strategy || "-"}</Td>
                  <Td>{s.status || "-"}</Td>
                  <Td>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteSignal(s.id)}
                    >
                      Eliminar
                    </Button>
                  </Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </div>

      {/* Orders */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
          Órdenes Recientes
        </h3>
        <Table>
          <thead>
            <Tr>
              <Th>ID</Th>
              <Th>Fecha</Th>
              <Th>Símbolo</Th>
              <Th>Lado</Th>
              <Th>Cantidad</Th>
              <Th>Precio</Th>
              <Th>Profit</Th>
              <Th>Estado</Th>
            </Tr>
          </thead>
          <tbody>
            {orders.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  Sin órdenes
                </Td>
              </Tr>
            ) : (
              orders.slice(-20).reverse().map((o) => (
                <Tr key={o.id}>
                  <Td>{o.id}</Td>
                  <Td>{fmtDate(o.timestamp)}</Td>
                  <Td><div className="flex items-center gap-1.5"><CryptoIcon symbol={o.symbol} size={18} />{o.symbol}</div></Td>
                  <Td>{o.side}</Td>
                  <Td>{fmt(o.quantity)}</Td>
                  <Td>${fmt(o.price)}</Td>
                  <Td>${fmt(o.profit)}</Td>
                  <Td>{o.status}</Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </div>

      {/* Trades */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
          Trades Cerrados
        </h3>
        <Table>
          <thead>
            <Tr>
              <Th>ID</Th>
              <Th>Fecha</Th>
              <Th>Símbolo</Th>
              <Th>Lado</Th>
              <Th>Cantidad</Th>
              <Th>Precio</Th>
              <Th>PnL</Th>
            </Tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  Sin trades
                </Td>
              </Tr>
            ) : (
              trades.slice(-20).reverse().map((t) => (
                <Tr key={t.id}>
                  <Td>{t.id}</Td>
                  <Td>{fmtDate(t.timestamp)}</Td>
                  <Td><div className="flex items-center gap-1.5"><CryptoIcon symbol={t.symbol} size={18} />{t.symbol}</div></Td>
                  <Td>{t.side}</Td>
                  <Td>{fmt(t.quantity)}</Td>
                  <Td>${fmt(t.price)}</Td>
                  <Td
                    className={
                      (t.pnl ?? 0) >= 0
                        ? "text-[var(--color-success)]"
                        : "text-[var(--color-danger)]"
                    }
                  >
                    ${fmt(t.pnl)}
                  </Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </div>

      {/* Backtests */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-3">
          Backtests
        </h3>
        <Table>
          <thead>
            <Tr>
              <Th>ID</Th>
              <Th>Estrategia</Th>
              <Th>Símbolos</Th>
              <Th>Retorno%</Th>
              <Th>Sharpe</Th>
              <Th>MaxDD%</Th>
              <Th>Trades</Th>
            </Tr>
          </thead>
          <tbody>
            {backtests.length === 0 ? (
              <Tr>
                <Td className="text-center text-[var(--color-text-muted)]">
                  Sin backtests
                </Td>
              </Tr>
            ) : (
              backtests.slice(-10).reverse().map((b) => (
                <Tr key={b.run_id}>
                  <Td>{b.run_id}</Td>
                  <Td>{b.strategy}</Td>
                  <Td>{b.symbols}</Td>
                  <Td>{fmt(b.return_pct)}</Td>
                  <Td>{fmt(b.sharpe)}</Td>
                  <Td>{fmt(b.max_drawdown_pct)}</Td>
                  <Td>{b.total_trades}</Td>
                </Tr>
              ))
            )}
          </tbody>
        </Table>
      </div>
    </div>
  );
}
