import { useState, useMemo } from "react";
import { Link2, ChevronRight, ShieldCheck, Clock, ExternalLink, Key, Search } from "lucide-react";
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
  onSkip?: () => void;
}

type OnboardingPhase = "select" | "tutorial" | "credentials";

export function BrokerOnboarding({ onConnected, onSkip }: BrokerOnboardingProps) {
  const { supportedBrokers, validate, connect } = useBrokerContext();
  const [selectedBroker, setSelectedBroker] = useState<SupportedBroker | null>(null);
  const [phase, setPhase] = useState<OnboardingPhase>("select");
  const [validationResult, setValidationResult] = useState<CredentialValidationResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRequest, setPendingRequest] = useState<CredentialValidationRequest | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const implementedBrokers = useMemo(
    () => supportedBrokers.filter((b) => b.implemented),
    [supportedBrokers]
  );
  const upcomingBrokers = useMemo(
    () => supportedBrokers.filter((b) => !b.implemented),
    [supportedBrokers]
  );
  const filteredBrokers = useMemo(
    () => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return implementedBrokers;
      return implementedBrokers.filter(
        (b) =>
          b.displayName.toLowerCase().includes(q) ||
          b.brokerId.toLowerCase().includes(q)
      );
    },
    [implementedBrokers, searchQuery]
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

  const handleSelectBroker = (broker: SupportedBroker) => {
    setSelectedBroker(broker);
    setValidationResult(null);
    setError(null);
    setPhase("tutorial");
  };

  const handleBackToBrokers = () => {
    setSelectedBroker(null);
    setValidationResult(null);
    setError(null);
    setPendingRequest(null);
    setPhase("select");
  };

  const handleBackToTutorial = () => {
    setValidationResult(null);
    setError(null);
    setPendingRequest(null);
    setPhase("tutorial");
  };

  return (
    <div className="h-screen overflow-y-auto flex flex-col items-center bg-[var(--color-bg)] p-4 sm:p-6">
      <div className={`w-full ${phase === "tutorial" && selectedBroker?.brokerId === "binance" ? "max-w-[1100px]" : "max-w-[640px]"}`}>
        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-[14px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/25 mx-auto mb-3">
            <Link2 size={24} className="text-white" />
          </div>
          <h1 className="text-[20px] font-extrabold text-[var(--color-text)] tracking-tight">
            Conecta tu primer broker
          </h1>
          <p className="text-[13px] text-[var(--color-text-muted)] mt-1">
            Importa tu API Key para comenzar a usar Alvora
          </p>
        </div>

        {phase === "select" && (
          /* Broker selection */
          <div className="space-y-4">
            {/* Search box — solo visible si hay muchos brokers */}
            {implementedBrokers.length > 6 && (
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Buscar exchange..."
                  className="w-full pl-9 pr-3 py-2.5 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] text-[13px] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-colors"
                />
              </div>
            )}

            <div className="space-y-2">
              <p className="text-[12px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
                Brokers disponibles {filteredBrokers.length !== implementedBrokers.length && `(${filteredBrokers.length})`}
              </p>
              {filteredBrokers.map((broker) => (
                <button
                  key={broker.brokerId}
                  onClick={() => handleSelectBroker(broker)}
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
              {filteredBrokers.length === 0 && searchQuery && (
                <div className="text-center py-6 text-[12px] text-[var(--color-text-muted)]">
                  No se encontraron exchanges para "{searchQuery}"
                </div>
              )}
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

            {onSkip && (
              <button
                onClick={onSkip}
                className="w-full text-center text-[12px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] py-2 transition-colors"
              >
                Saltar por ahora — lo configuraré más tarde
              </button>
            )}
          </div>
        )}

        {phase === "tutorial" && selectedBroker && (
          /* Tutorial: cómo obtener tu API Key */
          <div className="space-y-3">
            <button
              onClick={handleBackToBrokers}
              className="text-[11px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] flex items-center gap-1"
            >
              ← Volver a brokers
            </button>

            <div className="flex items-center gap-2.5 p-2.5 rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)]">
              <div className="w-8 h-8 rounded-[8px] bg-[var(--color-surface-2)] flex items-center justify-center text-[13px] font-extrabold text-[var(--color-text)]">
                {selectedBroker.displayName[0]}
              </div>
              <div>
                <p className="text-[13px] font-bold text-[var(--color-text)]">
                  {selectedBroker.displayName}
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)]">
                  {selectedBroker.supportedMarkets.join(", ")}
                </p>
              </div>
            </div>

            {selectedBroker.brokerId === "binance" ? (
              <div className="flex gap-4">
                {/* Left sidebar — Visual reference */}
                <div className="hidden lg:flex flex-col gap-3 w-[280px] shrink-0">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)] px-1">Referencia visual</p>

                  {/* Video tutorial */}
                  <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 space-y-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[16px]">🎥</span>
                      <p className="text-[11px] font-bold text-[var(--color-text)]">Video tutorial oficial</p>
                    </div>
                    <p className="text-[10px] text-[var(--color-text-muted)]">Binance tiene un video paso a paso en su guía oficial:</p>
                    <a href="https://www.binance.com/es/support/faq/detail/360002502072" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5">Ver guía oficial con video <ExternalLink size={9} /></a>
                  </div>

                  {/* Visual flow */}
                  <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 space-y-2">
                    <p className="text-[11px] font-bold text-[var(--color-text)]">Flujo visual</p>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">1</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]">Perfil → <span className="font-semibold text-[var(--color-text)]">Account</span></p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">2</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]"><span className="font-semibold text-[var(--color-text)]">API Management</span> → Create API</p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">3</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]">Tipo: <span className="font-semibold text-[var(--color-text)]">System Generated</span></p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-warning)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-warning)] shrink-0">4</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]">Verificación <span className="font-semibold text-[var(--color-text)]">2FA</span></p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">5</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]">Permisos: <span className="font-semibold text-[var(--color-text)]">Read + Trade</span></p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-danger)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-danger)] shrink-0">6</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]"><span className="font-semibold text-[var(--color-text)]">IP whitelist</span> obligatorio</p>
                      </div>
                      <div className="ml-3 border-l-2 border-[var(--color-border)] h-3" />
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-[6px] bg-[var(--color-success)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-success)] shrink-0">7</div>
                        <p className="text-[10px] text-[var(--color-text-muted)]">Copiar <span className="font-semibold text-[var(--color-text)]">API + Secret Key</span></p>
                      </div>
                    </div>
                  </div>

                  {/* Warning */}
                  <div className="rounded-[10px] bg-[var(--color-danger)]/5 border border-[var(--color-danger)]/20 p-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[14px]">⚠️</span>
                      <p className="text-[11px] font-bold text-[var(--color-text)]">Importante</p>
                    </div>
                    <p className="text-[10px] text-[var(--color-text-muted)] mt-1">La <span className="font-semibold">Secret Key</span> solo se muestra una vez. Si la pierdes, debes eliminar la API Key y crear una nueva.</p>
                  </div>
                </div>

                {/* Center — Step-by-step instructions */}
                <div className="flex-1 min-w-0">
                  <div className="rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3">
                    <div className="flex items-center gap-2 mb-0.5">
                      <Key size={14} className="text-[var(--color-primary)]" />
                      <h3 className="text-[13px] font-bold text-[var(--color-text)]">
                        Cómo obtener tu API Key de Binance
                      </h3>
                    </div>

                    <div className="space-y-3">
                      {/* Prerequisites */}
                      <div className="rounded-[8px] bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/20 p-2.5 space-y-1">
                        <p className="text-[11px] font-bold text-[var(--color-text)]">Antes de crear tu API Key necesitas:</p>
                        <ul className="text-[10px] text-[var(--color-text-muted)] space-y-0.5 ml-4 list-disc">
                          <li>Tener <span className="font-semibold">verificación de identidad (KYC)</span> completada</li>
                          <li>Tener <span className="font-semibold">2FA activado</span> (Google Authenticator recomendado)</li>
                          <li>Haber hecho un <span className="font-semibold">depósito mínimo</span> a tu Spot Wallet para activar la cuenta</li>
                        </ul>
                        <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">¿No tienes cuenta aún? <a href="https://www.binance.com/es/register" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline inline-flex items-center gap-0.5">Créala aquí <ExternalLink size={9} /></a></p>
                      </div>

                      {/* Mobile tutorial link */}
                      <div className="rounded-[8px] bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20 p-2.5">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[14px]">📱</span>
                          <p className="text-[11px] font-bold text-[var(--color-text)]">¿Prefieres crearla desde el celular?</p>
                        </div>
                        <p className="text-[10px] text-[var(--color-text-muted)] mt-1">Binance también permite crear API Keys desde su app móvil (Binance Pro). Abre la app → More → Other → API Management → Create API.</p>
                        <a href="https://www.binance.com/es/support/faq/detail/360002502072" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5 mt-1">Ver guía oficial completa (web y móvil) <ExternalLink size={9} /></a>
                      </div>

                      {/* Steps */}
                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">1</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Inicia sesión en Binance</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Ve a <a href="https://www.binance.com" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline inline-flex items-center gap-0.5">binance.com <ExternalLink size={10} /></a> e inicia sesión con tu cuenta.</p>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">2</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Ve a API Management</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Haz clic en tu perfil (esquina superior derecha) → <span className="font-semibold text-[var(--color-text)]">API Management</span> o ve directamente a <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" rel="noopener" className="text-[var(--color-accent)] underline inline-flex items-center gap-0.5">API Management <ExternalLink size={10} /></a></p>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">3</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Crea una nueva API Key</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Haz clic en <span className="font-semibold text-[var(--color-text)]">"Create API"</span> y selecciona <span className="font-semibold text-[var(--color-text)]">"System Generated"</span> (recomendado — Binance genera las claves por ti). La opción "Self-Generated" es para usuarios avanzados con claves Ed25519/RSA.</p>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">4</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Verifica tu identidad (2FA)</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Binance te pedirá verificar con tu 2FA (email, SMS y/o Google Authenticator). Esto es obligatorio y protege tu cuenta. Tómate tu tiempo para completar este paso.</p>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">5</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Configura los permisos correctamente</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-1">Por defecto, Binance solo activa <span className="font-semibold">Enable Reading</span>. Para habilitar trading necesitas agregar restricción de IP (paso 6).</p>
                          <div className="mt-1 space-y-0.5">
                            <p className="text-[11px] text-[var(--color-text-muted)]">✅ <span className="font-semibold text-[var(--color-success)]">Enable Reading</span> — Necesario para ver tu portfolio</p>
                            <p className="text-[11px] text-[var(--color-text-muted)]">✅ <span className="font-semibold text-[var(--color-success)]">Enable Spot & Margin Trading</span> — Solo si quieres operar</p>
                            <p className="text-[11px] text-[var(--color-text-muted)]">✅ <span className="font-semibold text-[var(--color-success)]">Enable Futures</span> — Solo si operas futuros</p>
                            <p className="text-[11px] text-[var(--color-text-muted)]">🚫 <span className="font-semibold text-[var(--color-danger)]">Enable Withdrawals</span> — NUNCA lo habilites</p>
                            <p className="text-[11px] text-[var(--color-text-muted)]">🚫 <span className="font-semibold text-[var(--color-danger)]">Enable Internal Transfer</span> — No es necesario</p>
                            <p className="text-[11px] text-[var(--color-text-muted)]">🚫 <span className="font-semibold text-[var(--color-danger)]">Enable Universal Transfer</span> — No es necesario</p>
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">6</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Restringe el acceso por IP (obligatorio para trading)</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Desde enero 2023, Binance requiere que las API Keys con permisos beyond Reading tengan restricción de IP. Selecciona <span className="font-semibold text-[var(--color-text)]">"Restrict access to trusted IPs only"</span> y agrega la IP de tu servidor. Si solo vas a usar lectura, puedes dejarlo sin restricción.</p>
                        </div>
                      </div>

                      <div className="flex gap-2.5">
                        <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">7</div>
                        <div className="flex-1">
                          <p className="text-[12px] font-bold text-[var(--color-text)]">Copia tu API Key y Secret Key</p>
                          <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Binance te mostrará dos claves: <span className="font-semibold text-[var(--color-text)]">API Key</span> y <span className="font-semibold text-[var(--color-text)]">Secret Key</span>. <span className="font-semibold text-[var(--color-warning)]">La Secret Key solo se muestra una vez</span> — guárdala inmediatamente en un lugar seguro (gestor de contraseñas, archivo cifrado). Si la pierdes, tendrás que crear una nueva API Key.</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Trust & patience message */}
                  <div className="mt-3 rounded-[10px] bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20 p-3 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-[var(--color-success)]" />
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Tus credenciales están seguras</p>
                    </div>
                    <ul className="text-[11px] text-[var(--color-text-muted)] space-y-0.5 ml-4 list-disc">
                      <li>Las credenciales se cifran con Fernet (AES-256) antes de guardarse</li>
                      <li>La IA nunca tiene acceso a tus API Keys</li>
                      <li>Puedes empezar en modo solo lectura (READ_ONLY)</li>
                      <li>Elimina la API Key en Binance cuando quieras para cortar el acceso</li>
                    </ul>
                  </div>

                  {/* Patience note */}
                  <div className="mt-3 rounded-[10px] bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/20 p-3 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <Clock size={14} className="text-[var(--color-warning)]" />
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Paciencia con las verificaciones de Binance</p>
                    </div>
                    <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
                      Binance puede pedir verificaciones adicionales (email, SMS, Google Authenticator) al crear tu API Key. Esto es normal y forma parte de su sistema de seguridad para proteger tus fondos.
                    </p>
                  </div>

                  {/* Continue button */}
                  <button
                    onClick={() => setPhase("credentials")}
                    className="mt-3 w-full flex items-center justify-center gap-2 px-4 h-10 rounded-[10px] text-[12px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
                  >
                    Ya tengo mis claves, continuar
                    <ChevronRight size={14} />
                  </button>
                </div>

                {/* Right sidebar — Quick reference & mobile */}
                <div className="hidden lg:flex flex-col gap-3 w-[240px] shrink-0 sticky top-0 self-start">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)] px-1">Referencia rápida</p>

                  {/* Mobile guide */}
                  <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 space-y-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[16px]">📱</span>
                      <p className="text-[11px] font-bold text-[var(--color-text)]">Crear API desde el celular</p>
                    </div>
                    <ol className="text-[10px] text-[var(--color-text-muted)] space-y-1 ml-4 list-decimal">
                      <li>Abre la app de Binance (modo Pro)</li>
                      <li>Ve a <span className="font-semibold">More</span> → <span className="font-semibold">Other</span></li>
                      <li>Toca <span className="font-semibold">API Management</span></li>
                      <li>Toca <span className="font-semibold">Create API</span></li>
                      <li>Selecciona el tipo de API Key</li>
                      <li>Verifica con 2FA</li>
                      <li>Copia tus claves</li>
                    </ol>
                    <a href="https://www.binance.com/es/support/faq/detail/360002502072" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5">Guía oficial completa <ExternalLink size={9} /></a>
                  </div>

                  {/* Security tips */}
                  <div className="rounded-[10px] bg-[var(--color-success)]/5 border border-[var(--color-success)]/20 p-3 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-[var(--color-success)]" />
                      <p className="text-[11px] font-bold text-[var(--color-text)]">Seguridad</p>
                    </div>
                    <ul className="text-[10px] text-[var(--color-text-muted)] space-y-1 ml-3 list-disc">
                      <li>Nunca habilites <span className="font-semibold">Withdrawals</span></li>
                      <li>Usa <span className="font-semibold">IP whitelist</span> siempre</li>
                      <li>Guarda la Secret Key en un gestor de contraseñas</li>
                      <li>No compartas tus claves con nadie</li>
                    </ul>
                  </div>

                  {/* Direct links */}
                  <div className="rounded-[10px] bg-[var(--color-surface)] border border-[var(--color-border)] p-3 space-y-1.5">
                    <p className="text-[11px] font-bold text-[var(--color-text)]">Links directos</p>
                    <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5">API Management <ExternalLink size={9} /></a>
                    <br />
                    <a href="https://www.binance.com/es/register" target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5">Crear cuenta Binance <ExternalLink size={9} /></a>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-[12px] bg-[var(--color-surface)] border border-[var(--color-border)] p-4 space-y-3">
                <div className="flex items-center gap-2 mb-0.5">
                  <Key size={14} className="text-[var(--color-primary)]" />
                  <h3 className="text-[13px] font-bold text-[var(--color-text)]">
                    Cómo obtener tu API Key de {selectedBroker.displayName}
                  </h3>
                </div>

                {/* Prerequisites */}
                <div className="rounded-[8px] bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/20 p-2.5 space-y-1">
                  <p className="text-[11px] font-bold text-[var(--color-text)]">Antes de empezar necesitas:</p>
                  <ul className="text-[10px] text-[var(--color-text-muted)] space-y-0.5 ml-4 list-disc">
                    <li>Tener una cuenta verificada en {selectedBroker.displayName}</li>
                    <li>Tener <span className="font-semibold">2FA activado</span> (recomendado)</li>
                  </ul>
                  {selectedBroker.websiteUrl && (
                    <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">¿No tienes cuenta? <a href={selectedBroker.websiteUrl} target="_blank" rel="noopener" className="text-[var(--color-accent)] underline inline-flex items-center gap-0.5">Crear cuenta <ExternalLink size={9} /></a></p>
                  )}
                </div>

                {/* Generic steps */}
                <div className="space-y-2.5">
                  <div className="flex gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">1</div>
                    <div className="flex-1">
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Inicia sesión en {selectedBroker.displayName}</p>
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Ve a la web oficial y accede a tu cuenta con tus credenciales.</p>
                    </div>
                  </div>

                  <div className="flex gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">2</div>
                    <div className="flex-1">
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Busca la sección "API" o "API Management"</p>
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Normalmente está en <span className="font-semibold text-[var(--color-text)]">Settings</span> → <span className="font-semibold text-[var(--color-text)]">API</span> o en el menú de tu perfil.</p>
                    </div>
                  </div>

                  <div className="flex gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">3</div>
                    <div className="flex-1">
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Crea una nueva API Key</p>
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">Pulsa "Create API" o "New API Key". Es posible que necesites verificar con 2FA o email.</p>
                    </div>
                  </div>

                  <div className="flex gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">4</div>
                    <div className="flex-1">
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Selecciona permisos de <span className="font-semibold">Read</span> y <span className="font-semibold">Trade</span></p>
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5"><span className="font-semibold text-[var(--color-danger)]">Nunca habilites Withdrawals</span> — Alvora bloquea las credenciales con permiso de retiro por seguridad.</p>
                    </div>
                  </div>

                  {selectedBroker.requiresPassphrase && (
                    <div className="flex gap-2.5">
                      <div className="w-5 h-5 rounded-full bg-[var(--color-warning)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-warning)] shrink-0">5</div>
                      <div className="flex-1">
                        <p className="text-[12px] font-bold text-[var(--color-text)]">Guarda la <span className="font-semibold">Passphrase</span></p>
                        <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">{selectedBroker.displayName} genera una passphrase adicional además de la API Key y Secret. La necesitarás para conectar.</p>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-[var(--color-primary)]/15 flex items-center justify-center text-[10px] font-bold text-[var(--color-primary)] shrink-0">{selectedBroker.requiresPassphrase ? "6" : "5"}</div>
                    <div className="flex-1">
                      <p className="text-[12px] font-bold text-[var(--color-text)]">Copia tu API Key y Secret Key</p>
                      <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5"><span className="font-semibold text-[var(--color-warning)]">El Secret Key solo se muestra una vez</span> — guárdalo inmediatamente en un gestor de contraseñas.</p>
                    </div>
                  </div>
                </div>

                {/* API docs link */}
                {selectedBroker.apiDocsUrl && (
                  <div className="rounded-[8px] bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20 p-2.5">
                    <div className="flex items-center gap-1.5">
                      <ExternalLink size={12} className="text-[var(--color-accent)]" />
                      <p className="text-[11px] font-bold text-[var(--color-text)]">Documentación oficial</p>
                    </div>
                    <a href={selectedBroker.apiDocsUrl} target="_blank" rel="noopener" className="text-[10px] text-[var(--color-accent)] underline inline-flex items-center gap-0.5 mt-1">Ver docs de API de {selectedBroker.displayName} <ExternalLink size={9} /></a>
                  </div>
                )}
              </div>
            )}

            {/* Trust message for non-binance */}
            {selectedBroker.brokerId !== "binance" && (
              <>
                <div className="rounded-[10px] bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20 p-3 space-y-1.5">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck size={14} className="text-[var(--color-success)]" />
                    <p className="text-[12px] font-bold text-[var(--color-text)]">Tus credenciales están seguras</p>
                  </div>
                  <ul className="text-[11px] text-[var(--color-text-muted)] space-y-0.5 ml-4 list-disc">
                    <li>Las credenciales se cifran con Fernet (AES-256) antes de guardarse</li>
                    <li>La IA nunca tiene acceso a tus API Keys</li>
                    <li>Puedes empezar en modo solo lectura (READ_ONLY)</li>
                    <li>Elimina la API Key cuando quieras para cortar el acceso</li>
                  </ul>
                </div>

                <button
                  onClick={() => setPhase("credentials")}
                  className="w-full flex items-center justify-center gap-2 px-4 h-10 rounded-[10px] text-[12px] font-bold bg-[var(--color-primary)] text-white hover:opacity-90 transition-opacity"
                >
                  Ya tengo mis claves, continuar
                  <ChevronRight size={14} />
                </button>
              </>
            )}
          </div>
        )}

        {phase === "credentials" && selectedBroker && (
          /* Credential form */
          <div className="space-y-4">
            <button
              onClick={handleBackToTutorial}
              className="text-[12px] font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)] flex items-center gap-1"
            >
              ← Volver al tutorial
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
