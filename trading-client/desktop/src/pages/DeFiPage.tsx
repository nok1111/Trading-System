import { useEffect, useState, useCallback } from "react";
import { Wallet as WalletIcon, Coins, Loader2 } from "lucide-react";
import { WalletConnect } from "../components/defi/WalletConnect";
import { DefiPositions } from "../components/defi/DefiPositions";
import { DexSwapPanel } from "../components/defi/DexSwapPanel";
import { OnChainAnalytics } from "../components/defi/OnChainAnalytics";
import { Table, Th, Td, Tr } from "../components/ui/Table";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { fmtVol } from "../lib/utils";
import {
  getWalletBalances,
  getDefiPositions,
  type WalletBalance,
  type DefiPositionsResponse,
} from "../lib/defiApi";

export function DeFiPage() {
  const [walletAddress, setWalletAddress] = useState<string | null>(null);
  const [balances, setBalances] = useState<WalletBalance | null>(null);
  const [positions, setPositions] = useState<DefiPositionsResponse | null>(null);
  const [loadingBalances, setLoadingBalances] = useState(false);
  const [loadingPositions, setLoadingPositions] = useState(false);

  const loadWalletData = useCallback(async (address: string) => {
    setLoadingBalances(true);
    setLoadingPositions(true);
    try {
      const [balRes, posRes] = await Promise.allSettled([
        getWalletBalances(address),
        getDefiPositions(address),
      ]);
      if (balRes.status === "fulfilled") setBalances(balRes.value);
      if (posRes.status === "fulfilled") setPositions(posRes.value);
    } finally {
      setLoadingBalances(false);
      setLoadingPositions(false);
    }
  }, []);

  useEffect(() => {
    if (walletAddress) {
      loadWalletData(walletAddress);
    }
  }, [walletAddress, loadWalletData]);

  return (
    <div className="p-5 max-w-[1400px] mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <WalletIcon size={20} className="text-[var(--color-primary)]" />
        <h1 className="text-[18px] font-bold text-[var(--color-text)]">DeFi / On-Chain</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left column: Wallet + Balances + Positions */}
        <div className="lg:col-span-2 space-y-4">
          {/* Wallet Connection */}
          <WalletConnect
            onConnected={(addr) => setWalletAddress(addr)}
            onBalancesLoaded={(bal) => setBalances(bal)}
          />

          {/* Balances Table */}
          {walletAddress && (
            <div className="panel p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Coins size={16} className="text-[var(--color-primary)]" />
                  <h3 className="text-[14px] font-bold text-[var(--color-text)]">Balances</h3>
                </div>
                {balances && !balances.error && (
                  <span className="text-[16px] font-bold text-[var(--color-success)]">
                    ${fmtVol(balances.total_usd)}
                  </span>
                )}
              </div>

              {loadingBalances ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 size={18} className="animate-spin text-[var(--color-primary)]" />
                </div>
              ) : balances?.error ? (
                <div className="text-[12px] text-[var(--color-danger)]">{balances.error}</div>
              ) : balances ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>Token</Th>
                      <Th>Balance</Th>
                      <Th>Price</Th>
                      <Th>USD</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Native ETH */}
                    {balances.native && !balances.native.error && (
                      <Tr>
                        <Td>
                          <div className="flex items-center gap-2">
                            <Badge variant="primary">ETH</Badge>
                            <span className="text-[11px] text-[var(--color-text-muted)]">Native</span>
                          </div>
                        </Td>
                        <Td className="num">{balances.native.balance.toFixed(6)}</Td>
                        <Td className="num">${balances.native.price_usd.toFixed(2)}</Td>
                        <Td className="num font-semibold text-[var(--color-success)]">
                          ${fmtVol(balances.native.usd_value)}
                        </Td>
                      </Tr>
                    )}
                    {/* ERC-20 tokens */}
                    {balances.tokens.map((token, i) => (
                      <Tr key={i}>
                        <Td>
                          <div className="flex items-center gap-2">
                            <Badge variant="default">{token.symbol}</Badge>
                            <span className="text-[11px] text-[var(--color-text-muted)] truncate max-w-[100px]">
                              {token.name}
                            </span>
                          </div>
                        </Td>
                        <Td className="num">{token.balance.toFixed(6)}</Td>
                        <Td className="num">${token.price_usd.toFixed(2)}</Td>
                        <Td className="num font-semibold text-[var(--color-success)]">
                          ${fmtVol(token.usd_value)}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState
                  icon={<Coins size={28} />}
                  title="Sin balances"
                  description="Conecta una wallet para ver tus balances."
                />
              )}
            </div>
          )}

          {/* DeFi Positions */}
          {walletAddress && (
            <DefiPositions data={positions} loading={loadingPositions} />
          )}
        </div>

        {/* Right column: DEX Swap + On-Chain Analytics */}
        <div className="space-y-4">
          <DexSwapPanel />
          <OnChainAnalytics />
        </div>
      </div>
    </div>
  );
}
