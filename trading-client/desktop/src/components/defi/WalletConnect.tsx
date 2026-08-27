import { useState } from "react";
import { Wallet, Loader2, CheckCircle } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { toast } from "../ui/Toast";
import { connectWallet, type WalletBalance } from "../../lib/defiApi";

export function WalletConnect({
  onConnected,
  onBalancesLoaded,
}: {
  onConnected?: (address: string) => void;
  onBalancesLoaded?: (balances: WalletBalance) => void;
}) {
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectedAddress, setConnectedAddress] = useState<string | null>(null);
  const [loadingBalances, setLoadingBalances] = useState(false);

  const handleConnect = async () => {
    if (!address || !address.startsWith("0x") || address.length !== 42) {
      toast("Direccion de wallet invalida", false);
      return;
    }
    setConnecting(true);
    try {
      const result = await connectWallet(address, label);
      if (result.error) {
        toast(result.error, false);
      } else {
        toast("Wallet conectada", true);
        setConnectedAddress(address);
        onConnected?.(address);
        // Load balances immediately
        setLoadingBalances(true);
        try {
          const balances = await import("../../lib/defiApi").then((m) => m.getWalletBalances(address));
          onBalancesLoaded?.(balances);
        } catch {
          // silent — balances will be loaded by parent
        } finally {
          setLoadingBalances(false);
        }
      }
    } catch (e: any) {
      toast("Error: " + e.message, false);
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Wallet size={16} className="text-[var(--color-primary)]" />
        <h3 className="text-[14px] font-bold text-[var(--color-text)]">Conectar Wallet</h3>
      </div>

      {connectedAddress ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-success)]/10 border border-[var(--color-success)]/20">
            <CheckCircle size={14} className="text-[var(--color-success)]" />
            <span className="text-[12px] font-semibold text-[var(--color-success)] truncate">
              {connectedAddress}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setConnectedAddress(null);
              setAddress("");
              setLabel("");
            }}
          >
            Desconectar
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">
              Direccion Ethereum
            </label>
            <Input
              placeholder="0x..."
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full font-mono text-[12px]"
            />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-[var(--color-text-muted)] mb-1 block">
              Etiqueta (opcional)
            </label>
            <Input
              placeholder="Mi wallet principal"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full"
            />
          </div>
          <Button
            variant="primary"
            size="md"
            onClick={handleConnect}
            disabled={connecting || !address}
            className="w-full"
          >
            {connecting || loadingBalances ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Wallet size={14} />
            )}
            {connecting ? "Conectando..." : "Conectar"}
          </Button>
          <p className="text-[10px] text-[var(--color-text-muted)]">
            Solo lectura — no se ejecutan transacciones. Se consultan balances y posiciones on-chain.
          </p>
        </div>
      )}
    </div>
  );
}
