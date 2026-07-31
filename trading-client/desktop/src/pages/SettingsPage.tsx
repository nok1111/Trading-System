import { useEffect, useState, useCallback } from "react";
import { api, authApi, getAuthServerUrl } from "../lib/api";
import { useAuthContext } from "../context/AuthContext";
import { Card, CardLabel, CardValue } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { toast } from "../components/ui/Toast";
import { getProxyConfig, setProxyConfig, testProxyConnection } from "../lib/binanceProxy";

export function SettingsPage() {
  const { user } = useAuthContext();
  const [license, setLicense] = useState<any>(null);
  const [apiKeyStatus, setApiKeyStatus] = useState<string>("");
  const [authServerConnected, setAuthServerConnected] = useState<boolean | null>(null);

  // Binance keys
  const [binanceKey, setBinanceKey] = useState("");
  const [binanceSecret, setBinanceSecret] = useState("");
  const [binanceKeyPreview, setBinanceKeyPreview] = useState("");
  const [binanceKeySet, setBinanceKeySet] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);

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

  const loadKeys = useCallback(async () => {
    try {
      const r = await api<any>("/api/settings/keys");
      setBinanceKeySet(r.binance_api_key_set);
      setBinanceKeyPreview(r.binance_api_key_preview || "");
    } catch {
      // ignore
    }
  }, []);

  const checkAuthServer = useCallback(async () => {
    try {
      const resp = await fetch(`${getAuthServerUrl()}/health`, { timeout: 5000 } as any);
      setAuthServerConnected(resp.ok);
    } catch {
      setAuthServerConnected(false);
    }
  }, []);

  const [proxyUrl, setProxyUrl] = useState("");
  const [proxyToken, setProxyToken] = useState("");
  const [proxyStatus, setProxyStatus] = useState<string>("");

  const loadProxyConfig = useCallback(() => {
    const cfg = getProxyConfig();
    setProxyUrl(cfg.url);
    setProxyToken(cfg.token);
  }, []);

  const saveProxyConfig = async () => {
    setProxyConfig(proxyUrl, proxyToken);
    toast("Configuración del proxy guardada");
    const ok = await testProxyConnection();
    setProxyStatus(ok ? "✓ Proxy conectado" : "✗ Proxy no responde");
  };

  const testProxy = async () => {
    setProxyStatus("Probando...");
    const ok = await testProxyConnection();
    setProxyStatus(ok ? "✓ Proxy conectado" : "✗ Proxy no responde");
  };

  useEffect(() => {
    loadLicense();
    checkApiKeys();
    loadKeys();
    checkAuthServer();
    loadProxyConfig();
  }, [loadLicense, checkApiKeys, loadKeys, checkAuthServer, loadProxyConfig]);

  const saveBinanceKeys = async () => {
    if (!binanceKey || !binanceSecret) {
      toast("API Key y Secret son requeridos", false);
      return;
    }
    setSavingKeys(true);
    try {
      await api<any>("/api/settings/binance-keys", {
        method: "POST",
        body: JSON.stringify({ binance_api_key: binanceKey, binance_api_secret: binanceSecret }),
      });
      toast("Binance API Keys guardadas");
      setBinanceKey("");
      setBinanceSecret("");
      loadKeys();
      checkApiKeys();
    } catch (e: any) {
      const msg = typeof e === "string" ? e : e?.message || JSON.stringify(e);
      toast("Error guardando keys: " + msg, false);
    } finally {
      setSavingKeys(false);
    }
  };

  const deleteBinanceKeys = async () => {
    try {
      await api<any>("/api/settings/binance-keys", { method: "DELETE" });
      toast("Binance API Keys eliminadas");
      setBinanceKeySet(false);
      setBinanceKeyPreview("");
      checkApiKeys();
    } catch (e: any) {
      toast("Error: " + e.message, false);
    }
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

      {/* Auth Server status */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Auth Server
        </h3>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${
              authServerConnected ? "bg-[var(--color-success)]" : "bg-[var(--color-danger)]"
            }`}
          />
          <span className="text-sm text-[var(--color-text)]">
            {authServerConnected ? "Conectado" : "Sin conexión"}
          </span>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] mt-2">
          Estado de la conexión con el servidor de autenticación.
        </p>
      </Card>

      {/* Binance API Keys */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Binance API Keys
        </h3>

        {binanceKeySet && (
          <div className="flex items-center gap-2 mb-4 p-3 rounded-lg bg-[var(--color-success)]/10">
            <span className="text-[var(--color-success)]">✓</span>
            <span className="text-sm text-[var(--color-text)]">
              Keys configuradas: <code className="text-xs text-[var(--color-text-muted)]">{binanceKeyPreview}</code>
            </span>
            <Button variant="danger" size="sm" className="ml-auto" onClick={deleteBinanceKeys}>
              Eliminar
            </Button>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-1">
              API Key
            </label>
            <Input
              type="password"
              value={binanceKey}
              onChange={(e) => setBinanceKey(e.target.value)}
              placeholder="Tu Binance API Key"
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-1">
              API Secret
            </label>
            <Input
              type="password"
              value={binanceSecret}
              onChange={(e) => setBinanceSecret(e.target.value)}
              placeholder="Tu Binance API Secret"
              className="w-full"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="primary" size="sm" onClick={saveBinanceKeys} disabled={savingKeys}>
              {savingKeys ? "Guardando..." : "Guardar Keys"}
            </Button>
            <Button variant="default" size="sm" onClick={checkApiKeys}>
              Probar conexión
            </Button>
          </div>
          <div className="text-sm">{apiKeyStatus}</div>
        </div>

        <p className="text-xs text-[var(--color-text-muted)] mt-3">
          Las keys se guardan encriptadas localmente. Nunca se envían al cloud.
          Si no configuras keys aquí, se usarán las del archivo .env.
        </p>
      </Card>

      {/* VPS Proxy Configuration */}
      <Card>
        <h3 className="text-sm font-semibold text-[var(--color-primary)] mb-4">
          Configuración del Proxy VPS (Binance)
        </h3>
        <div className="space-y-3">
          <div>
            <CardLabel>Proxy URL</CardLabel>
            <Input
              value={proxyUrl}
              onChange={(e: any) => setProxyUrl(e.target.value)}
              placeholder="http://76.13.180.80:9100"
              className="mt-1"
            />
          </div>
          <div>
            <CardLabel>Proxy Token</CardLabel>
            <Input
              type="password"
              value={proxyToken}
              onChange={(e: any) => setProxyToken(e.target.value)}
              placeholder="Token secreto del proxy"
              className="mt-1"
            />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="default" size="sm" onClick={saveProxyConfig}>
              Guardar
            </Button>
            <Button variant="default" size="sm" onClick={testProxy}>
              Probar conexión
            </Button>
          </div>
          {proxyStatus && <div className="text-sm">{proxyStatus}</div>}
        </div>
        <p className="text-xs text-[var(--color-text-muted)] mt-3">
          El proxy enruta tus órdenes a Binance desde una IP fija.
          Agrega la IP del proxy a tu whitelist en Binance API Management.
        </p>
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
