import { Loader2, Layers } from "lucide-react";
import { Table, Th, Td, Tr } from "../ui/Table";
import { Badge } from "../ui/Badge";
import { EmptyState } from "../ui/EmptyState";
import { fmtVol } from "../../lib/utils";
import type { DefiPositionsResponse } from "../../lib/defiApi";

export function DefiPositions({
  data,
  loading,
}: {
  data: DefiPositionsResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Layers size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Posiciones DeFi</h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-[var(--color-primary)]" />
        </div>
      </div>
    );
  }

  const defiPositions = data?.defi?.positions || [];
  const stakingPositions = data?.staking?.positions || [];
  const allPositions = [...defiPositions, ...stakingPositions];
  const totalUsd = (data?.defi?.total_usd || 0) + (data?.staking?.total_usd || 0);

  if (allPositions.length === 0) {
    return (
      <div className="panel p-4">
        <div className="flex items-center gap-2 mb-3">
          <Layers size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Posiciones DeFi</h3>
        </div>
        <EmptyState
          icon={<Layers size={28} />}
          title="Sin posiciones DeFi"
          description="Conecta una wallet para ver tus posiciones en Aave, Uniswap, Lido, etc."
        />
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Posiciones DeFi</h3>
        </div>
        <span className="text-[14px] font-bold text-[var(--color-success)]">
          ${fmtVol(totalUsd)}
        </span>
      </div>

      <Table>
        <thead>
          <tr>
            <Th>Protocolo</Th>
            <Th>Tipo</Th>
            <Th>Asset</Th>
            <Th>Balance</Th>
            <Th>USD</Th>
          </tr>
        </thead>
        <tbody>
          {defiPositions.map((pos, i) => (
            <Tr key={`defi-${i}`}>
              <Td>
                <Badge variant="primary">{pos.protocol}</Badge>
              </Td>
              <Td>
                <span className="text-[11px] text-[var(--color-text-muted)]">{pos.type}</span>
              </Td>
              <Td>
                <span className="font-semibold">{pos.asset}</span>
              </Td>
              <Td className="num">{pos.balance.toFixed(4)}</Td>
              <Td className="num font-semibold text-[var(--color-success)]">
                ${fmtVol(pos.usd_value)}
              </Td>
            </Tr>
          ))}
          {stakingPositions.map((pos, i) => (
            <Tr key={`staking-${i}`}>
              <Td>
                <Badge variant="accent">{pos.protocol}</Badge>
              </Td>
              <Td>
                <span className="text-[11px] text-[var(--color-text-muted)]">{pos.type}</span>
              </Td>
              <Td>
                <span className="font-semibold">{pos.asset}</span>
              </Td>
              <Td className="num">{pos.balance.toFixed(4)}</Td>
              <Td className="num font-semibold text-[var(--color-success)]">
                ${fmtVol(pos.usd_value)}
              </Td>
            </Tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
