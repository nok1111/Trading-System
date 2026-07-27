import { CheckCircle2, XCircle, ShieldAlert, ShieldX, Info } from "lucide-react";
import type { CredentialValidationResponse } from "../../lib/brokerTypes";
import { cn } from "../../lib/utils";

interface ValidationResultProps {
  result: CredentialValidationResponse;
}

export function ValidationResult({ result }: ValidationResultProps) {
  if (!result) return null;

  const { valid, status, permissions, errorMessage } = result;

  if (status === "SECURITY_BLOCKED") {
    return (
      <div className="rounded-[10px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 p-3.5 flex items-start gap-3">
        <ShieldX size={20} className="text-[var(--color-danger)] flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-[13px] font-bold text-[var(--color-danger)]">
            Bloqueada por seguridad
          </p>
          <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5">
            {errorMessage || "Las credenciales tienen permiso de retiro. No se permiten."}
          </p>
        </div>
      </div>
    );
  }

  if (!valid) {
    return (
      <div className="rounded-[10px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 p-3.5 flex items-start gap-3">
        <XCircle size={20} className="text-[var(--color-danger)] flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-[13px] font-bold text-[var(--color-danger)]">
            Credenciales inválidas
          </p>
          <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5">
            {errorMessage || "No se pudo validar la conexión con el broker."}
          </p>
        </div>
      </div>
    );
  }

  const isReadOnly = !permissions.trade;

  return (
    <div
      className={cn(
        "rounded-[10px] border p-3.5 flex items-start gap-3",
        isReadOnly
          ? "bg-[var(--color-success)]/10 border-[var(--color-success)]/30"
          : "bg-[var(--color-warning)]/10 border-[var(--color-warning)]/30"
      )}
    >
      <CheckCircle2
        size={20}
        className={cn(
          "flex-shrink-0 mt-0.5",
          isReadOnly
            ? "text-[var(--color-success)]"
            : "text-[var(--color-warning)]"
        )}
      />
      <div className="flex-1">
        <p
          className={cn(
            "text-[13px] font-bold",
            isReadOnly
              ? "text-[var(--color-success)]"
              : "text-[var(--color-warning)]"
          )}
        >
          {isReadOnly ? "Válida — Solo lectura" : "Válida — Trading habilitado"}
        </p>
        <div className="flex items-center gap-3 mt-1.5">
          <span className="flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
            <Info size={11} />
            Lectura: {permissions.read ? "✓" : "✗"}
          </span>
          <span className="flex items-center gap-1 text-[11px] text-[var(--color-text-muted)]">
            <Info size={11} />
            Trading: {permissions.trade ? "✓" : "✗"}
          </span>
          <span className="flex items-center gap-1 text-[11px] text-[var(--color-danger)]">
            <ShieldAlert size={11} />
            Retiros: {permissions.withdraw ? "✓" : "✗"}
          </span>
        </div>
      </div>
    </div>
  );
}
