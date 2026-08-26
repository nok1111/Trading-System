import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check, Plug, Building2 } from "lucide-react";
import { useBrokerContext } from "../../context/BrokerContext";
import { isBrokerConnected, type BrokerAccount } from "../../lib/brokerTypes";

interface BrokerPickerProps {
  selectedAccountId: string | null;
  onSelect: (accountId: string | null) => void;
}

export function BrokerPicker({ selectedAccountId, onSelect }: BrokerPickerProps) {
  const { connectedAccounts, supportedBrokers } = useBrokerContext();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const connected = connectedAccounts.filter((a) => isBrokerConnected(a.status));
  const selected = connected.find((a) => a.id === selectedAccountId) || connected[0] || null;

  // Get broker display info
  const getBrokerInfo = (brokerId: string) => {
    return supportedBrokers.find((b) => b.brokerId === brokerId);
  };

  if (connected.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface-2)] text-[12px] text-[var(--color-text-muted)]">
        <Plug size={14} />
        <span>Sin broker conectado</span>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-hover)] text-[12px] font-semibold text-[var(--color-text)] transition-colors"
      >
        <Building2 size={14} className="text-[var(--color-primary)]" />
        <span className="truncate max-w-[120px]">
          {selected?.displayName || "Seleccionar broker"}
        </span>
        <ChevronDown size={12} className={`text-[var(--color-text-muted)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-50 top-full left-0 mt-1 min-w-[200px] panel p-1.5 shadow-xl">
          {connected.map((account: BrokerAccount) => {
            const broker = getBrokerInfo(account.brokerId);
            const isSelected = account.id === selected?.id;

            return (
              <button
                key={account.id}
                onClick={() => {
                  onSelect(account.id);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors ${
                  isSelected
                    ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
                    : "text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
                }`}
              >
                <span className="text-[14px] font-extrabold w-5 text-center">
                  {(broker?.displayName || account.brokerId)[0]}
                </span>
                <div className="flex-1 text-left min-w-0">
                  <div className="truncate">{account.displayName || broker?.displayName}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)] capitalize">
                    {account.environment}
                  </div>
                </div>
                {isSelected && <Check size={14} />}
              </button>
            );
          })}

          {/* All brokers option */}
          <div className="border-t border-[var(--color-border)] mt-1 pt-1">
            <button
              onClick={() => {
                onSelect(null);
                setOpen(false);
              }}
              className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors ${
                !selectedAccountId
                  ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
                  : "text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
              }`}
            >
              <Building2 size={14} />
              <span>Todos los brokers</span>
              {!selectedAccountId && <Check size={14} className="ml-auto" />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
