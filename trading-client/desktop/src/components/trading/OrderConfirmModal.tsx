import { useEffect } from "react";
import { AlertTriangle, X, Check } from "lucide-react";
import { cn } from "../../lib/utils";

interface OrderConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  order: {
    symbol: string;
    side: "buy" | "sell";
    orderType: "market" | "limit";
    quantity: number;
    price: string | null;
    orderValue: number;
    fee: number;
    netValue: number;
    quoteCurrency: string;
    baseAsset: string;
    sellPnl: number | null;
    sellPnlPct: number | null;
    stopLossPrice: string;
    takeProfitPrice: string;
  };
}

export function OrderConfirmModal({ open, onClose, onConfirm, order }: OrderConfirmModalProps) {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const isBuy = order.side === "buy";
  const isLimit = order.orderType === "limit";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-order-title"
    >
      <div
        className="w-full max-w-[420px] mx-4 rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={cn(
          "flex items-center justify-between px-5 h-14 border-b border-[var(--color-border)]",
          isBuy ? "bg-[var(--color-success)]/10" : "bg-[var(--color-danger)]/10"
        )}>
          <div className="flex items-center gap-2.5">
            <AlertTriangle size={18} className={isBuy ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"} />
            <h2 id="confirm-order-title" className="text-[15px] font-extrabold text-[var(--color-text)]">
              Confirmar orden
            </h2>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center w-8 h-8 rounded-[8px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
            aria-label="Cerrar"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Order summary */}
          <div className="rounded-[10px] bg-[var(--color-surface-2)] p-4 space-y-2.5 text-[13px]">
            <div className="flex justify-between items-center">
              <span className="text-[var(--color-text-muted)]">Operación</span>
              <span className={cn(
                "font-extrabold text-[14px]",
                isBuy ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
              )}>
                {isBuy ? "COMPRAR" : "VENDER"} {order.symbol}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Tipo de orden</span>
              <span className="font-bold text-[var(--color-text)]">{isLimit ? "Límite" : "Mercado"}</span>
            </div>
            {isLimit && order.price && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Precio límite</span>
                <span className="font-bold text-[var(--color-text)]">${parseFloat(order.price).toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Cantidad</span>
              <span className="font-bold text-[var(--color-text)]">{order.quantity.toFixed(6)} {order.baseAsset}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Valor de la orden</span>
              <span className="font-bold text-[var(--color-text)]">${order.orderValue.toFixed(2)} {order.quoteCurrency}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Comisión estimada</span>
              <span className="font-bold text-yellow-400">−${order.fee.toFixed(4)} {order.quoteCurrency}</span>
            </div>
            <div className="flex justify-between border-t border-[var(--color-border)] pt-2.5">
              <span className="text-[var(--color-text-muted)] font-bold">{isBuy ? "Costo total" : "Recibes"}</span>
              <span className="font-extrabold text-[var(--color-text)] text-[15px]">
                ${order.netValue.toFixed(2)} {order.quoteCurrency}
              </span>
            </div>
          </div>

          {/* P&L for SELL */}
          {order.side === "sell" && order.sellPnl !== null && (
            <div className={cn(
              "rounded-[10px] px-4 py-3 border",
              order.sellPnl >= 0
                ? "bg-green-500/10 border-green-500/30"
                : "bg-red-500/10 border-red-500/30"
            )}>
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-bold uppercase text-[var(--color-text-muted)]">
                  {order.sellPnl >= 0 ? "Ganancia estimada" : "Pérdida estimada"}
                </span>
                <span className={cn(
                  "text-[16px] font-extrabold",
                  order.sellPnl >= 0 ? "text-green-400" : "text-red-400"
                )}>
                  {order.sellPnl >= 0 ? "+" : ""}{order.sellPnl.toFixed(2)} {order.quoteCurrency}
                </span>
              </div>
              {order.sellPnlPct !== null && (
                <div className="flex justify-end mt-0.5">
                  <span className={cn(
                    "text-[12px] font-bold",
                    order.sellPnlPct >= 0 ? "text-green-400" : "text-red-400"
                  )}>
                    {order.sellPnlPct >= 0 ? "+" : ""}{order.sellPnlPct.toFixed(2)}%
                  </span>
                </div>
              )}
            </div>
          )}

          {/* SL/TP */}
          {(order.stopLossPrice || order.takeProfitPrice) && (
            <div className="flex gap-2">
              {order.stopLossPrice && (
                <div className="flex-1 rounded-[8px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 px-3 py-2">
                  <div className="text-[10px] font-bold uppercase text-[var(--color-danger)]">Stop-Loss</div>
                  <div className="text-[13px] font-bold text-[var(--color-danger)]">${parseFloat(order.stopLossPrice).toLocaleString("en-US")}</div>
                </div>
              )}
              {order.takeProfitPrice && (
                <div className="flex-1 rounded-[8px] bg-[var(--color-success)]/10 border border-[var(--color-success)]/30 px-3 py-2">
                  <div className="text-[10px] font-bold uppercase text-[var(--color-success)]">Take-Profit</div>
                  <div className="text-[13px] font-bold text-[var(--color-success)]">${parseFloat(order.takeProfitPrice).toLocaleString("en-US")}</div>
                </div>
              )}
            </div>
          )}

          {/* Warning */}
          <div className="flex items-start gap-2 text-[11px] text-[var(--color-text-muted)]">
            <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />
            <span>
              {isLimit
                ? "Tu orden límite se ejecutará cuando el precio alcance el nivel especificado."
                : "Las órdenes de mercado se ejecutan inmediatamente al mejor precio disponible."}
              {" "}La comisión real puede variar según el exchange.
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3 px-5 pb-5">
          <button
            onClick={onClose}
            className="flex-1 h-11 rounded-[10px] text-[14px] font-bold text-[var(--color-text-muted)] bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:text-[var(--color-text)] hover:border-[var(--color-border-strong)] transition-all"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            autoFocus
            className={cn(
              "flex-1 h-11 rounded-[10px] text-[14px] font-extrabold text-white transition-all flex items-center justify-center gap-2",
              isBuy
                ? "bg-[var(--color-success)] hover:opacity-90"
                : "bg-[var(--color-danger)] hover:opacity-90"
            )}
          >
            <Check size={16} />
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}
