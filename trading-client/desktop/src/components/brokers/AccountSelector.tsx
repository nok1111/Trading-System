import { ChevronDown, Wallet } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { cn } from "../../lib/utils";
import { useBrokerContext } from "../../context/BrokerContext";

interface AccountSelectorProps {
  className?: string;
}

export function AccountSelector({ className }: AccountSelectorProps) {
  const { connectedAccounts, selectedBrokerAccountId, selectAccount, supportedBrokers } = useBrokerContext();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  if (connectedAccounts.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 px-3 h-9 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)]",
          className
        )}
      >
        <Wallet size={15} className="text-[var(--color-text-muted)]" />
        <span className="text-[12px] font-semibold text-[var(--color-text-muted)]">Sin cuenta</span>
      </div>
    );
  }

  const selected = connectedAccounts.find((a) => a.id === selectedBrokerAccountId);
  const selectedBroker = supportedBrokers.find((b) => b.brokerId === selected?.brokerId);

  return (
    <div className={cn("relative", className)} ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 h-9 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] transition-colors"
      >
        <Wallet size={15} className="text-[var(--color-text-muted)]" />
        <span className="text-[12px] font-semibold text-[var(--color-text)] truncate max-w-[140px]">
          {selected
            ? `${selectedBroker?.displayName || selected.brokerId} — ${selected.displayName || "Cuenta"}`
            : "Todas las cuentas"}
        </span>
        <ChevronDown size={14} className="text-[var(--color-text-muted)]" />
      </button>

      {open && (
        <div className="absolute z-30 top-11 right-0 w-[260px] panel overflow-hidden">
          <div className="px-3 py-2 border-b border-[var(--color-border)] text-[12px] font-bold text-[var(--color-text)]">
            Seleccionar cuenta
          </div>
          <div className="max-h-[280px] overflow-y-auto">
            <button
              onClick={() => {
                selectAccount(null);
                setOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-hover)] text-left",
                !selectedBrokerAccountId && "bg-[var(--color-primary)]/8"
              )}
            >
              <span className="text-[12px] font-semibold text-[var(--color-text)]">Todas las cuentas</span>
            </button>
            {connectedAccounts.map((account) => {
              const broker = supportedBrokers.find((b) => b.brokerId === account.brokerId);
              return (
                <button
                  key={account.id}
                  onClick={() => {
                    selectAccount(account.id);
                    setOpen(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-2 px-3 py-2 hover:bg-[var(--color-surface-hover)] text-left",
                    selectedBrokerAccountId === account.id && "bg-[var(--color-primary)]/8"
                  )}
                >
                  <span className="text-[14px] font-extrabold text-[var(--color-text-muted)]">
                    {broker?.displayName[0] || "?"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-bold text-[var(--color-text)] truncate">
                      {broker?.displayName || account.brokerId}
                    </p>
                    <p className="text-[10px] text-[var(--color-text-muted)] truncate">
                      {account.displayName || "Cuenta"}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
