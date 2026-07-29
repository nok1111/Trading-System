import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Key, ShieldCheck, Lock, Clock } from "lucide-react";
import { Button } from "../ui/Button";
import { Input, Select } from "../ui/Input";
import type {
  SupportedBroker,
  BrokerEnvironment,
  CredentialValidationRequest,
  CredentialValidationResponse,
} from "../../lib/brokerTypes";

interface CredentialFormProps {
  broker: SupportedBroker;
  onValidate: (req: CredentialValidationRequest) => Promise<CredentialValidationResponse>;
  onConnect: () => void;
  validationResult: CredentialValidationResponse | null;
  isValidating: boolean;
}

export function CredentialForm({
  broker,
  onValidate,
  onConnect,
  validationResult,
  isValidating,
}: CredentialFormProps) {
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [environment, setEnvironment] = useState<BrokerEnvironment>(
    broker.environments[broker.environments.length - 1] || "live"
  );
  const [showSecret, setShowSecret] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onValidate({
      brokerId: broker.brokerId,
      apiKey,
      apiSecret,
      passphrase: broker.requiresPassphrase ? passphrase : undefined,
      environment,
    });
  };

  const handleConnect = () => {
    onConnect();
    setApiKey("");
    setApiSecret("");
    setPassphrase("");
  };

  const isValid = validationResult?.valid === true;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Display name */}
      <div>
        <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
          Nombre de la cuenta (opcional)
        </label>
        <Input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Cuenta principal"
          className="w-full"
        />
      </div>

      {/* API Key */}
      <div>
        <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
          API Key
        </label>
        <Input
          type="text"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Tu API Key"
          required
          className="w-full"
          autoComplete="off"
        />
      </div>

      {/* API Secret */}
      <div>
        <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
          API Secret
        </label>
        <div className="relative">
          <Input
            type={showSecret ? "text" : "password"}
            value={apiSecret}
            onChange={(e) => setApiSecret(e.target.value)}
            placeholder="Tu API Secret"
            required
            className="w-full pr-10"
            autoComplete="off"
          />
          <button
            type="button"
            onClick={() => setShowSecret((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
      </div>

      {/* Passphrase (OKX only) */}
      {broker.requiresPassphrase && (
        <div>
          <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
            Passphrase
          </label>
          <Input
            type="password"
            value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)}
            placeholder="Tu passphrase"
            required
            className="w-full"
            autoComplete="off"
          />
        </div>
      )}

      {/* Environment */}
      <div>
        <label className="block text-[12px] font-semibold text-[var(--color-text-muted)] mb-1.5">
          Entorno
        </label>
        <Select
          value={environment}
          onChange={(e) => setEnvironment(e.target.value as BrokerEnvironment)}
          className="w-full"
        >
          {broker.environments.map((env) => (
            <option key={env} value={env}>
              {env === "live" ? "Live" : env === "testnet" ? "Testnet" : "Sandbox"}
            </option>
          ))}
        </Select>
      </div>

      {/* Security instructions */}
      <div className="rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3 space-y-1.5">
        <div className="flex items-center gap-1.5 text-[12px] font-bold text-[var(--color-text)]">
          <ShieldCheck size={14} className="text-[var(--color-success)]" />
          Seguridad
        </div>
        <ul className="text-[11px] text-[var(--color-text-muted)] space-y-1 ml-5 list-disc">
          <li>Crea tu API Key con permisos de lectura</li>
          <li>Habilita trading únicamente cuando lo decidas</li>
          <li className="text-[var(--color-danger)] font-semibold">
            NUNCA habilites retiros
          </li>
          <li>Las credenciales serán cifradas con Fernet</li>
          <li>La IA nunca recibirá tus API Keys</li>
          <li>La conexión puede comenzar en modo READ_ONLY</li>
        </ul>
      </div>

      {/* Actions */}
      <div className="flex gap-2.5">
        <Button
          type="submit"
          variant="default"
          size="lg"
          disabled={isValidating || !apiKey || !apiSecret}
          className="flex-1"
        >
          <Key size={15} />
          {isValidating ? "Validando..." : "Validar"}
        </Button>
        <Button
          type="button"
          variant="primary"
          size="lg"
          disabled={!isValid}
          onClick={handleConnect}
          className="flex-1"
        >
          <Lock size={15} />
          Conectar
        </Button>
      </div>

      {isValidating && (
        <div className="rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] p-3 flex items-start gap-2">
          <Clock size={14} className="text-[var(--color-text-muted)] mt-0.5 shrink-0 animate-spin" style={{ animationDuration: "2s" }} />
          <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
            Estamos verificando tus credenciales con {broker.displayName}. Esto puede tomar unos segundos mientras validamos los permisos y la conexión. Gracias por tu paciencia.
          </p>
        </div>
      )}
    </form>
  );
}
