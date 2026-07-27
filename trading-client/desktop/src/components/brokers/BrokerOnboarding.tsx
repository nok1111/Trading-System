import { useState, useMemo } from "react";
import { Link2, ChevronRight } from "lucide-react";
import { CredentialForm } from "./CredentialForm";
import { ValidationResult } from "./ValidationResult";
import { useBrokerContext } from "../../context/BrokerContext";
import type {
  SupportedBroker,
  CredentialValidationRequest,
  CredentialValidationResponse,
  CreateBrokerAccountRequest,
} from "../../lib/brokerTypes";

interface BrokerOnboardingProps {
  onConnected: () => void;
}

export function BrokerOnboarding({ onConnected }: BrokerOnboardingProps) {
  const { supportedBrokers, validate, connect } = useBrokerContext();
  const [selectedBroker, setSelectedBroker] = useState<SupportedBroker | null>(null);
  const [validationResult, setValidationResult] = useState<CredentialValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRequest, setPendingRequest] = useState<CredentialValidationRequest | null>(null);

  const implementedBrokers = useMemo(
    () => supportedBrokers.filter((b) => b.implemented),
    [supportedBrokers]
  );
  const upcomingBrokers = useMemo(
    () => supportedBrokers.filter((b) => !b.implemented),
    [supportedBrokers]
  );

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
      const msg = err instanceof Error ? err.message : "Error al validar";
      setError(msg);
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
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al conectar");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] p-6">
      <div className="w-full max-w-[640px]">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-[16px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/25 mx-auto mb-4">
            <Link2 size={28} className="text-white" />
          </div>
          <h1 className="text-[24px] font-extrabold text-[var(--color-text)] tracking-tight">
            Conecta tu primer broker
          </h1>
          <p className="text-[14px] text-[var(--color-text-muted)] mt-2">
            Importa tu API Key para comenzar a usar Alvora
          </p>
        </div>

        {!selectedBroker ? (
          /* Broker selection */
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-[12px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                Brokers disponibles
              </p>
              {implementedBrokers.map((broker) => (
                <button
                  key={broker.brokerId}
                  onClick={() => {
                    setSelectedBroker(broker);
                    setValidationResult(null);
                    setError(null);
                  }}
                  className="w-full flex items-center gap-3 p-4 rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-surface-hover)] transition-all text-left"
                >
                  <div className="w-10 h-10 rounded-[10px] bg-[var(--color-surface-2)] flex items-center justify-center text-[16px] font-extrabold text-[var(--color-text)]">
                    {broker.displayName[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[14px] font-bold text-[var(--color-text)]">
                      {broker.displayName}
                    </p>
                    <p className="text-[11px] text-[var(--color-text-muted)]">
                      {broker.supportedMarkets.join(", ")}
                    </p>
                  </div>
                  <ChevronRight size={18} className="text-[var(--color-text-muted)]" />
                </button>
              ))}
            </div>

            {upcomingBrokers.length > 0 && (
              <div className="space-y-2">
                <p className="text-[12px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                  Próximamente
                </p>
                {upcomingBrokers.map((broker) => (
                  <div
                    key={broker.brokerId}
                    className="w-full flex items-center gap-3 p-4 rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] opacity-50"
                  >
                    <div className="w-10 h-10 rounded-[10px] bg-[var(--color-surface-2)] flex items-center justify-center text-[16px] font-extrabold text-[var(--color-text-muted)]">
                      {broker.displayName[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-bold text-[var(--color-text-muted)]">
                        {broker.displayName}
                      </p>
                      <p className="text-[11px] text-[var(--color-text-muted)]">
                        Próximamente disponible
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Credential form */
          <div className="space-y-4">
            <button
              onClick={() => {
                setSelectedBroker(null);
                setValidationResult(null);
                setError(null);
                setPendingRequest(null);
              }}
              className="text-[12px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] flex items-center gap-1"
            >
              ← Volver a brokers
            </button>

            <div className="flex items-center gap-3 p-3 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)]">
              <div className="w-9 h-9 rounded-[8px] bg-[var(--color-surface-2)] flex items-center justify-center text-[14px] font-extrabold text-[var(--color-text)]">
                {selectedBroker.displayName[0]}
              </div>
              <div>
                <p className="text-[14px] font-bold text-[var(--color-text)]">
                  {selectedBroker.displayName}
                </p>
                <p className="text-[11px] text-[var(--color-text-muted)]">
                  {selectedBroker.supportedMarkets.join(", ")}
                </p>
              </div>
            </div>

            <CredentialForm
              broker={selectedBroker}
              onValidate={handleValidate}
              onConnect={handleConnect}
              validationResult={validationResult}
              isValidating={isValidating}
            />

            {validationResult && <ValidationResult result={validationResult} />}

            {error && (
              <div className="rounded-[10px] bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 p-3 text-[12px] text-[var(--color-danger)]">
                {error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
