import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { toast } from "./ui/Toast";
import { cn } from "../lib/utils";
import * as brokerApi from "../lib/brokerApi";

interface SlTpPanelProps {
  positionId: number;
  symbol: string;
  currentPrice: number;
  entryPrice: number;
  existingSl: number | null;
  existingTp: number | null;
  quantity: number;
  isLive: boolean;
  side?: string;
  brokerId?: string;
  onSuccess?: () => void;
}

export function SlTpPanel({
  positionId,
  symbol,
  currentPrice,
  entryPrice,
  existingSl,
  existingTp,
  quantity,
  isLive,
  brokerId = "binance",
  side = "long",
  onSuccess,
}: SlTpPanelProps) {
  const [slPrice, setSlPrice] = useState<string>("");
  const [tpPrice, setTpPrice] = useState<string>("");
  const [slPct, setSlPct] = useState<string>("");
  const [tpPct, setTpPct] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [marketInfo, setMarketInfo] = useState<{ minQty: number; minNotional: number; stepSize: number } | null>(null);
  const [dustMode, setDustMode] = useState(false);

  // Fetch market info on mount to detect dust early
  useEffect(() => {
    if (!isLive || !brokerId) return;
    brokerApi.getMarketInfo(brokerId, symbol).then((info) => {
      const mi = {
        minQty: info.min_quantity || 0,
        minNotional: info.min_notional || 0,
        stepSize: info.step_size || 0,
      };
      setMarketInfo(mi);
      // Check if position is dust (quantity below min notional or min qty)
      if (mi.minQty > 0 && quantity < mi.minQty) {
        setDustMode(true);
      } else if (mi.minNotional > 0 && quantity * currentPrice < mi.minNotional) {
        setDustMode(true);
      }
    }).catch(() => {});
  }, [isLive, brokerId, symbol, quantity, currentPrice]);

  const initValues = useCallback(() => {
    const sl = existingSl ?? (currentPrice > 0 ? currentPrice * 0.97 : 0);
    const tp = existingTp ?? (currentPrice > 0 ? currentPrice * 1.06 : 0);
    setSlPrice(sl > 0 ? String(sl) : "");
    setTpPrice(tp > 0 ? String(tp) : "");
    const sPct = currentPrice > 0 ? ((currentPrice - sl) / currentPrice) * 100 : 0;
    const tPct = currentPrice > 0 ? ((tp - currentPrice) / currentPrice) * 100 : 0;
    setSlPct(sPct.toFixed(2));
    setTpPct(tPct.toFixed(2));
  }, [existingSl, existingTp, currentPrice]);

  useEffect(() => {
    initValues();
  }, [initValues]);

  // When SL price changes, update SL percentage
  const handleSlPriceChange = (val: string) => {
    setSlPrice(val);
    const price = parseFloat(val);
    if (currentPrice > 0 && !isNaN(price)) {
      const pct = ((currentPrice - price) / currentPrice) * 100;
      setSlPct(pct.toFixed(2));
    }
  };

  // When SL percentage changes, update SL price
  const handleSlPctChange = (val: string) => {
    setSlPct(val);
    const pct = parseFloat(val);
    if (currentPrice > 0 && !isNaN(pct)) {
      const price = currentPrice * (1 - pct / 100);
      setSlPrice(String(price));
    }
  };

  // When TP price changes, update TP percentage
  const handleTpPriceChange = (val: string) => {
    setTpPrice(val);
    const price = parseFloat(val);
    if (currentPrice > 0 && !isNaN(price)) {
      const pct = ((price - currentPrice) / currentPrice) * 100;
      setTpPct(pct.toFixed(2));
    }
  };

  // When TP percentage changes, update TP price
  const handleTpPctChange = (val: string) => {
    setTpPct(val);
    const pct = parseFloat(val);
    if (currentPrice > 0 && !isNaN(pct)) {
      const price = currentPrice * (1 + pct / 100);
      setTpPrice(String(price));
    }
  };

  const handleDustTransfer = async () => {
    const baseAsset = symbol.includes("/") ? symbol.split("/")[0] : symbol.replace("USDT", "");
    setLoading(true);
    try {
      const res = await brokerApi.dustTransfer(brokerId, [baseAsset]);
      if (res.status === "ok") {
        const msg = brokerId === "binance"
          ? `Convertido ${baseAsset} a ${res.total_bnb || "BNB"}`
          : `Vendido ${baseAsset} a mercado`;
        toast(msg, true);
        if (onSuccess) onSuccess();
      } else {
        toast(`Error dust transfer: ${res.error}`, false);
      }
    } catch (err: any) {
      toast(`Error: ${err?.message || err}`, false);
    }
    setLoading(false);
  };

  const handleCloseInDb = async () => {
    setLoading(true);
    try {
      const res = await api<any>(`/api/intelligence/positions/${positionId}/stop-monitoring`, {
        method: "POST",
      });
      if (res?.status === "ok" || res?.status === "closed") {
        toast(`Posición ${symbol} cerrada en DB`, true);
        if (onSuccess) onSuccess();
      } else {
        toast(res?.error || "Error al cerrar", false);
      }
    } catch (err: any) {
      toast(`Error: ${err?.message || err}`, false);
    }
    setLoading(false);
  };

  const handleConfirm = async () => {
    const sl = parseFloat(slPrice);
    const tp = parseFloat(tpPrice);
    if (isNaN(sl) || sl <= 0 || isNaN(tp) || tp <= 0) {
      toast("SL y TP deben ser valores positivos", false);
      return;
    }
    if (sl >= tp) {
      toast("SL debe ser menor que TP", false);
      return;
    }

    setLoading(true);
    try {
      if (isLive) {
        // Live mode: place real OCO order via broker API
        const closeSide = side === "short" ? "buy" : "sell";

        // Use cached market info or fetch if not available
        let stepSize = marketInfo?.stepSize || 0;
        let minQty = marketInfo?.minQty || 0;
        let minNotional = marketInfo?.minNotional || 0;
        if (!marketInfo) {
          try {
            const info = await brokerApi.getMarketInfo(brokerId, symbol);
            if (info.step_size) stepSize = info.step_size;
            if (info.min_quantity) minQty = info.min_quantity;
            if (info.min_notional) minNotional = info.min_notional;
          } catch (err) {
            console.warn("Could not fetch market info", err);
          }
        }

        // Helper: round to step size
        const roundToStep = (value: number, step: number): number => {
          if (step <= 0 || isNaN(step)) return value;
          const quotient = Math.floor(value / step);
          return quotient * step;
        };

        let formattedQty = roundToStep(quantity, stepSize);
        if (formattedQty === 0 && quantity > 0) formattedQty = quantity;

        // Validate quantity
        if (formattedQty <= 0) {
          toast(`Cantidad inválida (${formattedQty}) para ${symbol}. Verifica la posición.`, false);
          setLoading(false);
          return;
        }
        if (minQty > 0 && formattedQty < minQty) {
          toast(`Cantidad insuficiente: ${formattedQty} < mínimo ${minQty} para ${symbol}.`, false);
          setLoading(false);
          return;
        }
        if (minNotional > 0 && formattedQty * tp < minNotional) {
          toast(`Valor de la orden (${(formattedQty * tp).toFixed(2)}) menor al mínimo (${minNotional}) para ${symbol}.`, false);
          setLoading(false);
          return;
        }

        // Place real OCO order (TP limit + SL stop-limit, one cancels other)
        const ocoResp = await brokerApi.placeOcoOrder(brokerId, {
          symbol,
          side: closeSide,
          quantity: formattedQty,
          take_profit_price: tp,
          stop_loss_price: sl,
        });

        if (ocoResp.error || ocoResp.status === "error") {
          toast(`Error OCO: ${ocoResp.error}`, false);
          setLoading(false);
          return;
        }

        const ocoId = ocoResp.oco_order_id || "";

        // Update DB via backend
        const res = await api<any>(`/api/intelligence/positions/${positionId}/update-oco`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            oco_order_id: ocoId,
            stop_loss: sl,
            take_profit: tp,
            symbol,
            quantity: formattedQty,
            entry_price: entryPrice,
          }),
        });

        if (res?.status === "placed" || res?.status === "ok") {
          toast(`OCO colocado en ${brokerId} para ${symbol} (ID: ${ocoId})`, true);
        } else {
          toast(res?.error || "Error al actualizar DB tras OCO", false);
        }
      } else {
        // Paper mode: use backend endpoint (simulated monitoring)
        const res = await api<any>(`/api/intelligence/paper-positions/${positionId}/place-oco`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stop_loss: sl, take_profit: tp }),
        });
        if (res?.status === "placed") {
          toast(`SL/TP colocado para ${symbol} (ID: ${res.oco_order_id})`, true);
        } else if (res?.status === "monitoring") {
          toast(`Monitoreo activado para ${symbol} (SL: ${res.sl}, TP: ${res.tp})`, true);
        } else {
          toast(res?.error || res?.reason || "Error al colocar SL/TP", false);
        }
      }
      if (onSuccess) onSuccess();
    } catch (err: any) {
      const msg = err?.message || err?.error || JSON.stringify(err);
      toast(`Error SL/TP: ${msg}`, false);
      console.error("SlTpPanel OCO error:", err);
    }
    setLoading(false);
  };

  const inputCls =
    "w-full h-8 px-2 rounded-[6px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[12px] num font-bold text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";

  return (
    <div className="mt-3 p-3 rounded-[8px] bg-[var(--color-surface-1)] border border-[var(--color-border)] space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-[var(--color-text)] uppercase">
          {isLive ? `Colocar SL/TP en ${brokerId}` : "Configurar SL/TP (Paper)"}
        </span>
        <span className="text-[10px] text-[var(--color-text-muted)]">{symbol}</span>
      </div>

      {/* Dust warning */}
      {isLive && dustMode && (
        <div className="p-2.5 rounded-[6px] bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 space-y-2">
          <div className="text-[11px] font-bold text-[var(--color-warning)]">
            ⚠ Posición dust (polvo)
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            Tienes {quantity} {symbol.includes("/") ? symbol.split("/")[0] : symbol} (~${(quantity * currentPrice).toFixed(2)}).
            El mínimo de {brokerId} es {marketInfo?.minQty || "?"} unidades.
            No se puede colocar SL/TP porque la cantidad es insuficiente.
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleDustTransfer}
              disabled={loading}
              className="flex-1 h-7 rounded-[6px] text-[10px] font-bold text-white bg-[var(--color-warning)] hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "Procesando..." : brokerId === "binance" ? "Convertir a BNB" : "Vender (market)"}
            </button>
            <button
              onClick={handleCloseInDb}
              disabled={loading}
              className="flex-1 h-7 rounded-[6px] text-[10px] font-bold text-[var(--color-text)] bg-[var(--color-surface-3)] hover:opacity-90 disabled:opacity-50"
            >
              Cerrar en DB
            </button>
          </div>
        </div>
      )}

      {/* Normal SL/TP form (hidden in dust mode) */}
      {!dustMode && (
        <>
          {/* Current price reference */}
          <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
            <span>Precio actual: <span className="num font-bold text-[var(--color-text)]">{currentPrice}</span></span>
            <span>|</span>
            <span>Entry: <span className="num font-bold text-[var(--color-text)]">{entryPrice}</span></span>
          </div>

          {/* SL row */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-bold text-[var(--color-danger)] uppercase mb-1 block">SL Precio</label>
              <input
                type="number"
                step="any"
                value={slPrice}
                onChange={(e) => handleSlPriceChange(e.target.value)}
                className={cn(inputCls, "text-[var(--color-danger)]")}
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold text-[var(--color-danger)] uppercase mb-1 block">SL %</label>
              <input
                type="number"
                step="any"
                value={slPct}
                onChange={(e) => handleSlPctChange(e.target.value)}
                className={cn(inputCls, "text-[var(--color-danger)]")}
                placeholder="3.00"
              />
            </div>
          </div>

          {/* TP row */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] font-bold text-[var(--color-success)] uppercase mb-1 block">TP Precio</label>
              <input
                type="number"
                step="any"
                value={tpPrice}
                onChange={(e) => handleTpPriceChange(e.target.value)}
                className={cn(inputCls, "text-[var(--color-success)]")}
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="text-[10px] font-bold text-[var(--color-success)] uppercase mb-1 block">TP %</label>
              <input
                type="number"
                step="any"
                value={tpPct}
                onChange={(e) => handleTpPctChange(e.target.value)}
                className={cn(inputCls, "text-[var(--color-success)]")}
                placeholder="6.00"
              />
            </div>
          </div>

          {/* Confirm button */}
          <button
            onClick={handleConfirm}
            disabled={loading}
            className={cn(
              "w-full h-8 rounded-[8px] text-[12px] font-bold text-white transition-opacity",
              loading ? "opacity-50 cursor-not-allowed" : "hover:opacity-90",
              isLive ? "bg-[var(--color-success)]" : "bg-[var(--color-info)]"
            )}
          >
            {loading ? "Procesando..." : isLive ? `Confirmar SL/TP en ${brokerId}` : "Confirmar Monitoreo"}
          </button>
        </>
      )}
    </div>
  );
}
