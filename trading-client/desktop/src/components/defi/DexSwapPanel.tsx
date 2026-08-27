import { useState } from "react";
import { ArrowLeftRight, Loader2, Zap } from "lucide-react";
import { Button } from "../ui/Button";
import { Input, Select } from "../ui/Input";
import { Badge } from "../ui/Badge";
import { toast } from "../ui/Toast";
import { getSwapQuote, prepareSwap, type SwapQuote, type SwapTxData } from "../../lib/defiApi";

const COMMON_TOKENS = ["ETH", "WETH", "USDT", "USDC", "DAI", "WBTC", "LINK", "UNI"];

export function DexSwapPanel() {
  const [tokenIn, setTokenIn] = useState("ETH");
  const [tokenOut, setTokenOut] = useState("USDC");
  const [amount, setAmount] = useState("1");
  const [slippage, setSlippage] = useState("1");
  const [quoting, setQuoting] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [quote, setQuote] = useState<SwapQuote | null>(null);
  const [txData, setTxData] = useState<SwapTxData | null>(null);

  const handleQuote = async () => {
    if (!tokenIn || !tokenOut || !amount) {
      toast("Completa todos los campos", false);
      return;
    }
    setQuoting(true);
    setQuote(null);
    setTxData(null);
    try {
      // Convert amount to base units (simplified — assumes 18 decimals)
      const baseAmount = (parseFloat(amount) * 1e18).toString();
      const result = await getSwapQuote(tokenIn, tokenOut, baseAmount);
      if (result.error) {
        toast(result.error, false);
      } else {
        setQuote(result);
        toast("Quote obtenido", true);
      }
    } catch (e: any) {
      toast("Error: " + e.message, false);
    } finally {
      setQuoting(false);
    }
  };

  const handlePrepare = async () => {
    if (!tokenIn || !tokenOut || !amount) {
      toast("Completa todos los campos", false);
      return;
    }
    setPreparing(true);
    setTxData(null);
    try {
      const baseAmount = (parseFloat(amount) * 1e18).toString();
      const slip = parseFloat(slippage) / 100;
      const result = await prepareSwap(tokenIn, tokenOut, baseAmount, slip);
      if (result.error) {
        toast(result.error, false);
      } else {
        setTxData(result);
        toast("Transaccion preparada", true);
      }
    } catch (e: any) {
      toast("Error: " + e.message, false);
    } finally {
      setPreparing(false);
    }
  };

  const swapTokens = () => {
    const tmp = tokenIn;
    setTokenIn(tokenOut);
    setTokenOut(tmp);
    setQuote(null);
    setTxData(null);
  };

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <ArrowLeftRight size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[14px] font-bold text-[var(--color-text)]">DEX Swap (0x API)</h3>
      </div>

      <div className="space-y-3">
        {/* Token in */}
        <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">Vender</label>
            <Input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.0"
              className="w-full"
            />
          </div>
          <Button variant="ghost" size="sm" onClick={swapTokens} className="mb-0.5">
            <ArrowLeftRight size={14} />
          </Button>
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">Token</label>
            <Select value={tokenIn} onChange={(e) => setTokenIn(e.target.value)} className="w-full">
              {COMMON_TOKENS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </Select>
          </div>
        </div>

        {/* Token out */}
        <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">Comprar</label>
            <Input
              value={quote ? (parseInt(quote.buy_amount) / 1e6).toFixed(6) : "—"}
              readOnly
              placeholder="—"
              className="w-full"
            />
          </div>
          <div className="w-[32px]" />
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">Token</label>
            <Select value={tokenOut} onChange={(e) => setTokenOut(e.target.value)} className="w-full">
              {COMMON_TOKENS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </Select>
          </div>
        </div>

        {/* Slippage */}
        <div>
          <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">
            Slippage (%)
          </label>
          <Input
            type="number"
            value={slippage}
            onChange={(e) => setSlippage(e.target.value)}
            className="w-24"
          />
        </div>

        {/* Buttons */}
        <div className="flex gap-2">
          <Button variant="default" size="md" onClick={handleQuote} disabled={quoting} className="flex-1">
            {quoting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Cotizar
          </Button>
          <Button variant="primary" size="md" onClick={handlePrepare} disabled={preparing} className="flex-1">
            {preparing ? <Loader2 size={14} className="animate-spin" /> : <ArrowLeftRight size={14} />}
            Preparar TX
          </Button>
        </div>

        {/* Quote result */}
        {quote && (
          <div className="rounded-lg bg-[var(--color-surface-2)] p-3 space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-[var(--color-text-muted)]">Precio</span>
              <span className="font-semibold">{quote.price}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[var(--color-text-muted)]">Gas estimado</span>
              <span className="font-semibold">{quote.estimated_gas}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[var(--color-text-muted)]">Gas price</span>
              <span className="font-semibold">{quote.gas_price}</span>
            </div>
            {quote.sources && quote.sources.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {quote.sources.slice(0, 3).map((s, i) => (
                  <Badge key={i} variant="default">{s.name}</Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TX data result */}
        {txData && (
          <div className="rounded-lg bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/20 p-3 space-y-1.5">
            <div className="text-[11px] font-bold text-[var(--color-primary)] mb-1">Transaccion preparada</div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[var(--color-text-muted)]">To</span>
              <span className="font-mono text-[10px] truncate max-w-[200px]">{txData.to}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[var(--color-text-muted)]">Gas</span>
              <span className="font-semibold">{txData.gas}</span>
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] pt-1">{txData.note}</div>
          </div>
        )}
      </div>
    </div>
  );
}
