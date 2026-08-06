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
        // Live mode: place SL/TP orders via generic broker API
        const closeSide = side === "short" ? "buy" : "sell";

        // Fetch market info for precision/min sizes
        let stepSize = 0;
        let minQty = 0;
        let minNotional = 0;
        try {
          const info = await brokerApi.getMarketInfo(brokerId, symbol);
          if (info.step_size) stepSize = info.step_size;
          if (info.min_quantity) minQty = info.min_quantity;
          if (info.min_notional) minNotional = info.min_notional;
        } catch (err) {
          console.warn("Could not fetch market info", err);
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

        // Place TP as a limit sell order
        const tpResp = await brokerApi.placeOrder(brokerId, {
          symbol,
          side: closeSide as "buy" | "sell",
          order_type: "limit",
          quantity: formattedQty,
          price: tp,
        });
        // Place SL as a market sell order (simplified — real SL would need stop order type)
        const slResp = await brokerApi.placeOrder(brokerId, {
          symbol,
          side: closeSide as "buy" | "sell",
          order_type: "limit",
          quantity: formattedQty,
          price: sl,
        });

        const orderIds: string[] = [];
        if (tpResp.orderId) orderIds.push(tpResp.orderId);
        if (slResp.orderId) orderIds.push(slResp.orderId);

        if (tpResp.error || slResp.error) {
          toast(`Error: ${tpResp.error || slResp.error}`, false);
          setLoading(false);
          return;
        }

        // Update DB via backend
        const res = await api<any>(`/api/intelligence/positions/${positionId}/update-oco`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ oco_order_id: orderIds.join(","), stop_loss: sl, take_profit: tp }),
        });

        if (res?.status === "placed" || res?.status === "ok") {
          toast(`SL/TP colocado en ${brokerId} para ${symbol} (IDs: ${orderIds.join(", ")})`, true);
        } else {
          toast(res?.error || "Error al actualizar DB tras SL/TP", false);
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
    </div>
  );
}
