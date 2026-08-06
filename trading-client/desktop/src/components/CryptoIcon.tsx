import { useState } from "react";

const ICON_BASE = "https://assets.coincap.io/assets/icons";

function normalizeSymbol(symbol: string): string {
  return symbol
    .replace(/(USDT|USDC|FDUSD|TUSD|BUSD|USD|EUR|BTC|ETH|BNB|TRY|BRL|MXN|JPY|GBP|AUD)$/i, "")
    .replace(/\//g, "")
    .toLowerCase();
}

interface CryptoIconProps {
  symbol: string;
  size?: number;
  className?: string;
}

export function CryptoIcon({ symbol, size = 24, className = "" }: CryptoIconProps) {
  const [error, setError] = useState(false);
  const base = normalizeSymbol(symbol);
  const url = `${ICON_BASE}/${base}@2x.png`;

  if (error) {
    return (
      <span
        className={`rounded-full flex items-center justify-center font-bold flex-shrink-0 bg-[var(--color-surface-3)] text-[var(--color-text-muted)] ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.36 }}
      >
        {base.slice(0, 3).toUpperCase()}
      </span>
    );
  }

  return (
    <img
      src={url}
      alt={base.toUpperCase()}
      width={size}
      height={size}
      className={`rounded-full object-cover flex-shrink-0 ${className}`}
      style={{ width: size, height: size }}
      onError={() => setError(true)}
      loading="lazy"
    />
  );
}
