import { RefreshCw, Trash2, Ban, Link2, ShieldCheck } from "lucide-react";
import { useBrokerContext } from "../context/BrokerContext";
import { BrokerStatusBadge } from "../components/brokers/BrokerStatusBadge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/common/EmptyState";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { isBrokerConnected } from "../lib/brokerTypes";
import { fmtDate } from "../lib/utils";

export function ConnectionsPage() {
  const { connectedAccounts, supportedBrokers, isLoading, sync, disconnect, revoke, refresh } = useBrokerContext();

  if (isLoading) {
    return (
      <div className="p-5 max-w-[800px] mx-auto">
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  return (
    <div className="p-5 space-y-4 max-w-[800px] mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Conexiones de Brokers</h2>
        <Button variant="default" size="sm" onClick={refresh}>
          <RefreshCw size={13} />
          Actualizar
        </Button>
      </div>

      {connectedAccounts.length === 0 ? (
        <EmptyState
          icon={<Link2 size={28} />}
          title="Sin brokers conectados"
          description="Conecta tu primer broker para comenzar a operar."
        />
      ) : (
        <div className="space-y-3">
          {connectedAccounts.map((account) => {
            const broker = supportedBrokers.find((b) => b.brokerId === account.brokerId);
            const connected = isBrokerConnected(account.status);
            return (
              <div
                key={account.id}
                className="rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-[10px] bg-[var(--color-surface-2)] flex items-center justify-center text-[16px] font-extrabold text-[var(--color-text)]">
                    {broker?.displayName[0] || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[14px] font-bold text-[var(--color-text)]">
                      {broker?.displayName || account.brokerId}
                    </p>
                    <p className="text-[11px] text-[var(--color-text-muted)]">
                      {account.displayName || "Cuenta"} — {account.apiKeyPreview}
                    </p>
                  </div>
                  <BrokerStatusBadge status={account.status} />
                </div>

                <div className="flex items-center gap-4 mt-3 text-[11px] text-[var(--color-text-muted)]">
                  <span>Entorno: <span className="font-bold text-[var(--color-text)]">{account.environment}</span></span>
                  <span>Permisos: <span className="font-bold text-[var(--color-text)]">
                    {account.permissions.read ? "Lectura" : ""}{account.permissions.trade ? " + Trading" : ""}
                  </span></span>
                  {account.lastSyncAt && (
                    <span>Última sync: {fmtDate(account.lastSyncAt)}</span>
                  )}
                </div>

                <div className="flex items-center gap-2 mt-3">
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => sync(account.id)}
                    disabled={!connected}
                  >
                    <RefreshCw size={13} />
                    Sincronizar
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => revoke(account.id)}
                  >
                    <Ban size={13} />
                    Revocar
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => disconnect(account.id)}
                  >
                    <Trash2 size={13} />
                    Eliminar
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3 flex items-start gap-3">
        <ShieldCheck size={16} className="text-[var(--color-success)] flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-[var(--color-text-muted)]">
          Las credenciales se cifran con Fernet en el backend. La IA nunca recibe tus API Keys.
          No se permiten credenciales con permiso de retiro.
        </p>
      </div>
    </div>
  );
}
