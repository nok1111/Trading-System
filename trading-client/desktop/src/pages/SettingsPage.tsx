import { useEffect, useState, useCallback } from "react";
import { api, authApi, getAuthServerUrl, setAuthServerUrl } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { toast } from "../components/ui/Toast";

export function SettingsPage() {
  const { user } = useAuth();
  const [license, setLicense] = useState<any>(null);
  const [apiKeyStatus, setApiKeyStatus] = useState<string>("");
  const [authUrl, setAuthUrl] = useState(getAuthServerUrl());

  const loadLicense = useCallback(async () => {
    try {
      const l = await authApi<any>("/api/license/check");
      setLicense(l);
    } catch (e: any) {
      toast("No se pudo validar la licencia: " + e.message, false);
    }
  }, []);

  const checkApiKeys = useCallback(async () => {
    try {
      const r = await api<any>("/api/binance/balance");
      if (r?.balances?.length > 0) {
        setApiKeyStatus("✓ API Keys del .env funcionando");
      } else {
        setApiKeyStatus("⚠ Sin balances. Verifica tus API keys en .env");
      }
    } catch {
      setApiKeyStatus("✗ API Keys no configuradas en .env");
    }
  }, []);

  useEffect(() => {
    loadLicense();
    checkApiKeys();
  }, [loadLicense, checkApiKeys]);

  const saveAuthUrl = () => {
    setAuthServerUrl(authUrl);
    toast("Auth Server URL guardado");
  };

  const planLimits = license?.plan_limits || {};
  const features = planLimits.features || [];

  const featureLabels: Record<string, string> = {
    paper_trading: "Paper Trading",
    ai_agent_analysis: "Análisis IA",
    ai_agent_autotrade: "Auto-trade IA",
    telegram_notifications: "Notificaciones Telegram",
    ai_provider_keys: "API Keys IA Propias",
    ai_premium_providers: "Providers IA Premium",
    priority_support: "Soporte Prioritario",
    custom_strategies: "Estrategias Custom",
  };

  return (
    <div className="p-5 space-y-4 max-w-6xl">
      {/* Local mode banner */}
      <Card className="border-l-4 border-l-[var(--color-primary)]">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">🔒</span>
          <span className="font-semibold text-[var(--color-primary)]">
            Modo Cliente Local
          </span>
        </div>
        <p className="text-sm text-[var(--color-text-muted)]">
          Tus API keys (Binance, IA) se configuran en el archivo{" "}
          <b className="text-[var(--color-primary)]">.env</b> local. Nunca se
          envían al cloud. Para cambiarlas, edita{" "}
          <b className="text-[var(--color-primary)]">.env</b> y reinicia la app.
        </p>
      </Card>

      {/* Account info */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Cuenta
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <CardLabel>Email</CardLabel>
            <CardValue className="text-sm">
              {license?.email || user?.email || "--"}
            </CardValue>
          </div>
          <div>
            <CardLabel>Usuario</CardLabel>
            <CardValue className="text-sm">
              {license?.username || user?.username || "--"}
            </CardValue>
          </div>
          <div>
            <CardLabel>Plan</CardLabel>
            <CardValue className="text-sm">
              <Badge
                variant={
                  license?.subscription === "premium"
                    ? "warning"
                    : license?.subscription === "pro"
                      ? "primary"
                      : "default"
                }
              >
                {(license?.subscription || user?.subscription || "free").toUpperCase()}
              </Badge>
            </CardValue>
          </div>
          <div>
            <CardLabel>Miembro desde</CardLabel>
            <CardValue className="text-sm">
              {user?.created_at
                ? new Date(user.created_at).toLocaleDateString("es-ES")
                : "--"}
            </CardValue>
          </div>
        </div>
      </Card>

      {/* Auth Server URL */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Auth Server
        </h3>
        <div className="flex gap-2 items-center">
          <Input
            value={authUrl}
            onChange={(e) => setAuthUrl(e.target.value)}
            placeholder="http://localhost:8000"
            className="w-80"
          />
          <Button variant="primary" size="sm" onClick={saveAuthUrl}>
            Guardar
          </Button>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] mt-2">
          URL del servidor de autenticación. Cambia esto si el Auth Server está
          en otro host.
        </p>
      </Card>

      {/* Binance API Keys status */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Binance API Keys
        </h3>
        <p className="text-sm text-[var(--color-text-muted)] mb-3">
          Configura tus API keys en el archivo{" "}
          <b className="text-[var(--color-primary)]">.env</b> (BROKER_API_KEY,
          BROKER_API_SECRET). Reinicia la app para aplicar cambios.
        </p>
        <div className="text-sm mb-3">{apiKeyStatus}</div>
        <Button variant="default" size="sm" onClick={checkApiKeys}>
          Probar conexión
        </Button>
      </Card>

      {/* AI Keys info */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          AI Provider Keys
        </h3>
        <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
          <p className="text-sm text-[var(--color-primary)] font-semibold mb-1">
            Las API keys se configuran en tu archivo .env local
          </p>
          <p className="text-xs text-[var(--color-text-muted)]">
            Edita .env y reinicia la app para aplicar cambios.
            <br />
            GROQ_API_KEY, GEMINI_API_KEY, etc.
          </p>
        </div>
      </Card>

      {/* Plan limits */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Límites del Plan
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <CardLabel>Pares permitidos</CardLabel>
            <CardValue className="text-sm">
              {planLimits.max_pairs >= 999
                ? "Ilimitados"
                : planLimits.max_pairs ?? "--"}
            </CardValue>
          </div>
          <div>
            <CardLabel>Posiciones máx</CardLabel>
            <CardValue className="text-sm">
              {planLimits.max_positions >= 999
                ? "Ilimitadas"
                : planLimits.max_positions ?? "--"}
            </CardValue>
          </div>
          <div>
            <CardLabel>IA requests/día</CardLabel>
            <CardValue className="text-sm">
              {planLimits.max_ai_requests_per_day >= 99999
                ? "Ilimitados"
                : planLimits.max_ai_requests_per_day ?? "--"}
            </CardValue>
          </div>
        </div>

        {/* Features */}
        {features.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {features.map((f: string) => (
              <span
                key={f}
                className="inline-block px-2.5 py-1 rounded-md bg-[var(--color-success)]/15 text-[var(--color-success)] text-xs font-semibold"
              >
                ✓ {featureLabels[f] || f}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* Upgrade button */}
      {license?.subscription !== "premium" && (
        <Card>
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-warning)]">
                Mejorar Plan
              </h3>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                Desbloquea más pares, posiciones y features con Binance Pay.
              </p>
            </div>
            <Button
              variant="primary"
              onClick={() =>
                window.open(getAuthServerUrl(), "_blank")
              }
            >
              Mejorar
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
