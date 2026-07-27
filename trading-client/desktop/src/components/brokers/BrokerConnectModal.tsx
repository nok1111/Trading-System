import { useState } from "react";
import { X, Link2 } from "lucide-react";
import { CredentialForm } from "./CredentialForm";
import { ValidationResult } from "./ValidationResult";
import { useBrokerContext } from "../../context/BrokerContext";
import type {
  SupportedBroker,
  CredentialValidationRequest,
  CredentialValidationResponse,
  CreateBrokerAccountRequest,
} from "../../lib/brokerTypes";

interface BrokerConnectModalProps {
  broker: SupportedBroker;
  onClose: () => void;
  onConnected?: () => void;
}

export function BrokerConnectModal({
  broker,
  onClose,
  onConnected,
}: BrokerConnectModalProps) {
  const { validate, connect } = useBrokerContext();
  const [validationResult, setValidationResult] = useState<CredentialValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRequest, setPendingRequest] = useState<CredentialValidationRequest | null>(null);

  const handleValidate = async (req: CredentialValidationRequest): Promise<CredentialValidationResponse> => {
    setIsValidating(true);
    setError(null);
    setValidationResult(null);
    setPendingRequest(req);
    try {
      const result = await validate(req);
      setValidationResult(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al validar");
      throw err;
    } finally {
      setIsValidating(false);
    }
  };

  const handleConnect = async () => {
    if (!pendingRequest || !validationResult?.valid) return;
    setError(null);
    try {
      const req: CreateBrokerAccountRequest = {
        brokerId: pendingRequest.brokerId,
        apiKey: pendingRequest.apiKey,
        apiSecret: pendingRequest.apiSecret,
        passphrase: pendingRequest.passphrase,
        environment: pendingRequest.environment,
      };
      await connect(req);
      onConnected?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al conectar");
    }
  };

  if (!broker.implemented) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
        <div
          className="w-full max-w-[420px] rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl p-6"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-[8px] bg-[var(--color-surface-2)] flex items-center justify-center text-[14px] font-extrabold text-[var(--color-text-muted)]">
                {broker.displayName[0]}
              </div>
              <p className="text-[15px] font-bold text-[var(--color-text)]">{broker.displayName}</p>
            </div>
            <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
              <X size={18} />
            </button>
          </div>
          <div className="py-8 text-center">
            <Link2 size={28} className="mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
            <p className="text-[14px] font-bold text-[var(--color-text)]">Próximamente disponible</p>
            <p className="text-[12px] text-[var(--color-text-muted)] mt-1">
              {broker.displayName} aún no está implementado. Pronto podrás conectar tu cuenta.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-[480px] max-h-[90vh] overflow-y-auto rounded-[16px] bg-[var(--color-surface)] border border-[var(--color-border)] shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-[8px] bg-[var(--color-surface-2)] flex items-center justify-center text-[14px] font-extrabold text-[var(--color-text)]">
              {broker.displayName[0]}
            </div>
            <div>
              <p className="text-[15px] font-bold text-[var(--color-text)]">{broker.displayName}</p>
              <p className="text-[11px] text-[var(--color-text-muted)]">Conectar cuenta</p>
            </div>
          </div>
          <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={18} />
          </button>
        </div>

        <CredentialForm
          broker={broker}
          onValidate={handleValidate}
          onConnect={handleConnect}
          validationResult={validationResult}
          isValidating={isValidating}
        />

        {validationResult && <div className="mt-4"><ValidationResult result={validationResult} /></div>}

        {error && (
          <div className="mt-3 rounded-[10px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 p-3 text-[12px] text-[var(--color-danger)]">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
