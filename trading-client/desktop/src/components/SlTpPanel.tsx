import { useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";
import { toast } from "./ui/Toast";
import { cn } from "../lib/utils";
import * as binanceProxy from "../lib/binanceProxy";

interface SlTpPanelProps {
  positionId: number;
  symbol: string;
  currentPrice: number;
  entryPrice: number;
  existingSl: number | null;
  existingTp: number | null;
  quantity: number;
  isLive: boolean;
  isFutures?: boolean;
  side?: string;
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
  isFutures = false,
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
        // Live mode: place OCO via VPS proxy, then update DB
        const brokerSymbol = symbol.toUpperCase().replace(/[-_/]/g, "");
        const closeSide = side === "short" ? "BUY" : "SELL";

        // Fetch exchange info to get LOT_SIZE and PRICE filters
        let stepSize = "0.00000001";
        let tickSize = "0.00000001";
        let minQty = "0";
        let minNotional = "0";
        let exchangeInfoOk = false;
        const exInfoUrl = isFutures
          ? `https://fapi.binance.com/fapi/v1/exchangeInfo?symbol=${brokerSymbol}`
          : `https://api.binance.com/api/v3/exchangeInfo?symbol=${brokerSymbol}`;
        try {
          let exInfo: any = null;
          try {
            exInfo = isFutures
              ? await binanceProxy.getFuturesExchangeInfo(brokerSymbol)
              : await binanceProxy.getExchangeInfo(brokerSymbol);
          } catch {
            const directResp = await fetch(exInfoUrl);
            if (directResp.ok) exInfo = await directResp.json();
          }
          const filters = exInfo?.symbols?.[0]?.filters || [];
          for (const f of filters) {
            if (f.filterType === "LOT_SIZE") {
              stepSize = f.stepSize || stepSize;
              minQty = f.minQty || minQty;
            } else if (f.filterType === "PRICE_FILTER") {
              tickSize = f.tickSize || tickSize;
            } else if (f.filterType === "MIN_NOTIONAL" || f.filterType === "NOTIONAL") {
              minNotional = f.minNotional || f.notional || minNotional;
            }
          }
          exchangeInfoOk = true;
        } catch (err) {
          console.warn("Could not fetch exchangeInfo", err);
        }

        // Helper: round to step size (robust against floating point errors)
        const roundToStep = (value: number, step: string): string => {
          const stepNum = parseFloat(step);
          if (stepNum <= 0 || isNaN(stepNum)) return String(value);
          const stepStr = step.replace(/0+$/, "").replace(/\.$/, "");
          const decimals = (stepStr.split(".")[1] || "").length;
          const quotient = Math.floor(value / stepNum);
          const rounded = quotient * stepNum;
          let result = rounded.toFixed(Math.max(decimals, 0));
          result = result.replace(/0+$/, "").replace(/\.$/, "");
          if (result === "" || result === "-0" || parseFloat(result) === 0) return "0";
          return result;
        };

        let formattedQty = roundToStep(quantity, stepSize);
        const formattedTp = roundToStep(tp, tickSize);
        const formattedSl = roundToStep(sl, tickSize);

        // If rounding to step makes qty 0 but original qty > 0, use original qty
        if (parseFloat(formattedQty) === 0 && quantity > 0) {
          formattedQty = String(quantity);
        }

        // Validate quantity against minQty
        const minQtyNum = parseFloat(minQty);
        const qtyNum = parseFloat(formattedQty);
        if (qtyNum <= 0) {
          toast(`Cantidad inválida (${formattedQty}) para ${symbol}. Verifica la posición.`, false);
          setLoading(false);
          return;
        }
        if (minQtyNum > 0 && qtyNum < minQtyNum) {
          const marketLabel = isFutures ? "Futuros" : "Spot";
          const suggestion = isFutures
            ? "Verifica la cantidad de tu posición en futuros."
            : `Binance Spot requiere mínimo ${minQty} ${symbol.replace("USDT", "")}. Tienes ${formattedQty}. Considera comprar más o mover la posición a Futuros (mínimo 0.001).`;
          toast(`Cantidad insuficiente para ${marketLabel}: ${formattedQty} < mínimo ${minQty}. ${suggestion}`, false);
          setLoading(false);
          return;
        }
        // Validate minNotional (qty * price >= minNotional)
        const minNotionalNum = parseFloat(minNotional);
        if (minNotionalNum > 0 && qtyNum * tp < minNotionalNum) {
          toast(`Valor de la orden (${(qtyNum * tp).toFixed(2)} USDT) es menor al mínimo de Binance (${minNotional} USDT) para ${symbol}.`, false);
          setLoading(false);
          return;
        }
        if (!exchangeInfoOk) {
          toast(`Aviso: No se pudo obtener exchangeInfo. Usando step size por defecto.`, false);
        }

        let orderIds: string[] = [];

        if (isFutures) {
          // Futures: cancel existing orders, then place STOP_MARKET + TAKE_PROFIT_MARKET
          try {
            const openOrders = await binanceProxy.getFuturesOpenOrders(brokerSymbol);
            for (const o of openOrders) {
              const otype = o.type || "";
              if (["STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP", "TAKE_PROFIT"].includes(otype)) {
                try { await binanceProxy.cancelFuturesOrder(brokerSymbol, String(o.orderId)); } catch {}
              }
            }
          } catch {}

          // Place TAKE_PROFIT_MARKET
          const tpResp = await binanceProxy.placeFuturesOrder({
            symbol: brokerSymbol,
            side: closeSide,
            type: "TAKE_PROFIT_MARKET",
            stopPrice: formattedTp,
            quantity: formattedQty,
            reduceOnly: true,
            workingType: "MARK_PRICE",
          });
          orderIds.push(String(tpResp.orderId));

          // Place STOP_MARKET
          const slResp = await binanceProxy.placeFuturesOrder({
            symbol: brokerSymbol,
            side: closeSide,
            type: "STOP_MARKET",
            stopPrice: formattedSl,
            quantity: formattedQty,
            reduceOnly: true,
            workingType: "MARK_PRICE",
          });
          orderIds.push(String(slResp.orderId));
        } else {
          // Spot: cancel existing orders, then place OCO
          try {
            const openOrders = await binanceProxy.getOpenOrders(brokerSymbol);
            for (const o of openOrders) {
              const otype = o.type || "";
              if (["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT", "STOP_MARKET", "TAKE_PROFIT_MARKET"].includes(otype)) {
                try { await binanceProxy.cancelOrder(brokerSymbol, String(o.orderId)); } catch {}
              }
            }
          } catch {}

          const ocoResp = await binanceProxy.placeOCO({
            symbol: brokerSymbol,
            side: closeSide,
            quantity: formattedQty,
            price: formattedTp,
            stopPrice: formattedSl,
            stopLimitPrice: formattedSl,
            stopLimitTimeInForce: "GTC",
          });
          orderIds.push(String(ocoResp.orderListId));
        }

        // Update DB via backend
        const res = await api<any>(`/api/intelligence/positions/${positionId}/update-oco`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ oco_order_id: orderIds.join(","), stop_loss: sl, take_profit: tp }),
        });

        const label = isFutures ? "Futuros SL/TP" : "OCO Spot";
        if (res?.status === "placed" || res?.status === "ok") {
          toast(`${label} colocado en Binance para ${symbol} (IDs: ${orderIds.join(", ")})`, true);
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
          toast(`OCO colocado en Binance para ${symbol} (ID: ${res.oco_order_id})`, true);
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
          {isLive ? "Colocar OCO en Binance" : "Configurar SL/TP (Paper)"}
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
        {loading ? "Procesando..." : isLive ? "Confirmar OCO en Binance" : "Confirmar Monitoreo"}
      </button>
    </div>
  );
}
