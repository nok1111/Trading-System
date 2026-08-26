import { useState, useEffect, useCallback } from "react";
import { Shield, Lock, EyeOff, Ban, Smartphone, Monitor, Trash2, AlertTriangle, Key, Copy, Check } from "lucide-react";
import { authApi } from "../lib/api";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { toast } from "../components/ui/Toast";

interface Session {
  id: number;
  device_name: string;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  last_active_at: string;
  expires_at: string;
}

interface TwoFASetupResponse {
  secret: string;
  qr_uri: string;
  issuer: string;
  account: string;
}

interface TwoFAVerifyResponse {
  enabled: boolean;
  backup_codes: string[];
}

interface TwoFAStatus {
  enabled: boolean;
  has_secret: boolean;
}

export function SecurityPage() {
  const [totpStatus, setTotpStatus] = useState<TwoFAStatus | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  // 2FA setup flow state
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [setupData, setSetupData] = useState<TwoFASetupResponse | null>(null);
  const [setupPassword, setSetupPassword] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [copiedCodes, setCopiedCodes] = useState(false);
  const [setupLoading, setSetupLoading] = useState(false);

  // Disable 2FA state
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableLoading, setDisableLoading] = useState(false);

  const fetchSecurityData = useCallback(async () => {
    setLoading(true);
    try {
      const [status, sess] = await Promise.all([
        authApi<TwoFAStatus>("/api/auth/2fa/status"),
        authApi<Session[]>("/api/auth/sessions"),
      ]);
      setTotpStatus(status);
      setSessions(sess);
    } catch (err) {
      console.error("Failed to fetch security data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  const handleSetup2FA = async () => {
    if (!setupPassword) {
      toast("Ingresa tu contraseña");
      return;
    }
    setSetupLoading(true);
    try {
      const data = await authApi<TwoFASetupResponse>("/api/auth/2fa/setup", {
        method: "POST",
        body: JSON.stringify({ password: setupPassword }),
      });
      setSetupData(data);
    } catch (err: any) {
      toast(err.message || "Error al configurar 2FA");
    } finally {
      setSetupLoading(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      toast("Ingresa el código de 6 dígitos");
      return;
    }
    setSetupLoading(true);
    try {
      const data = await authApi<TwoFAVerifyResponse>("/api/auth/2fa/verify", {
        method: "POST",
        body: JSON.stringify({ code: verifyCode }),
      });
      if (data.enabled) {
        setBackupCodes(data.backup_codes);
        toast("2FA activado correctamente");
        await fetchSecurityData();
      }
    } catch (err: any) {
      toast(err.message || "Código inválido");
    } finally {
      setSetupLoading(false);
    }
  };

  const handleDisable2FA = async () => {
    if (!disablePassword || !disableCode) {
      toast("Ingresa contraseña y código 2FA");
      return;
    }
    setDisableLoading(true);
    try {
      await authApi("/api/auth/2fa/disable", {
        method: "POST",
        body: JSON.stringify({ password: disablePassword, code: disableCode }),
      });
      toast("2FA desactivado");
      setShowDisableModal(false);
      setDisablePassword("");
      setDisableCode("");
      await fetchSecurityData();
    } catch (err: any) {
      toast(err.message || "Error al desactivar 2FA");
    } finally {
      setDisableLoading(false);
    }
  };

  const handleRevokeSession = async (sessionId: number) => {
    try {
      await authApi(`/api/auth/sessions/${sessionId}`, { method: "DELETE" });
      toast("Sesión revocada");
      await fetchSecurityData();
    } catch (err: any) {
      toast(err.message || "Error al revocar sesión");
    }
  };

  const handleRevokeAllOthers = async () => {
    try {
      const data = await authApi<{ revoked_count: number }>("/api/auth/sessions/revoke-all-others", {
        method: "POST",
      });
      toast(`${data.revoked_count} sesiones revocadas`);
      await fetchSecurityData();
    } catch (err: any) {
      toast(err.message || "Error al revocar sesiones");
    }
  };

  const copyBackupCodes = () => {
    if (backupCodes) {
      navigator.clipboard.writeText(backupCodes.join("\n"));
      setCopiedCodes(true);
      setTimeout(() => setCopiedCodes(false), 2000);
    }
  };

  const closeSetupModal = () => {
    setShowSetupModal(false);
    setSetupData(null);
    setSetupPassword("");
    setVerifyCode("");
    setBackupCodes(null);
  };

  const formatDate = (iso: string) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-5 space-y-4 max-w-[700px] mx-auto">
      <h2 className="text-[16px] font-extrabold text-[var(--color-text)]">Seguridad</h2>

      {/* 2FA Section */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Smartphone size={18} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Autenticación de Dos Factores (2FA)</h3>
          {totpStatus?.enabled && (
            <span className="ml-auto text-[11px] px-2 py-0.5 rounded-full bg-[var(--color-success)]/15 text-[var(--color-success)] font-semibold">
              ACTIVO
            </span>
          )}
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">
          Protege tu cuenta con una capa adicional de seguridad. Al activar 2FA, necesitarás un código
          de tu app autenticadora (Google Authenticator, Authy, etc.) además de tu contraseña.
        </p>
        {totpStatus?.enabled ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-[12px] text-[var(--color-success)]">
              <Check size={14} />
              <span>2FA está activado. Tu cuenta está protegida.</span>
            </div>
            <Button
              variant="danger"
              className="text-[12px]"
              onClick={() => setShowDisableModal(true)}
            >
              Desactivar 2FA
            </Button>
          </div>
        ) : (
          <Button
            variant="primary"
            className="text-[12px]"
            onClick={() => setShowSetupModal(true)}
          >
            Activar 2FA
          </Button>
        )}
      </div>

      {/* Sessions Section */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Monitor size={18} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Sesiones Activas</h3>
          {sessions.length > 1 && (
            <Button
              variant="ghost"
              className="ml-auto text-[11px] text-[var(--color-danger)]"
              onClick={handleRevokeAllOthers}
            >
              Revocar otras
            </Button>
          )}
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">
          Estas son las dispositivos con sesiones activas. Puedes revocar cualquier sesión para
          cerrarla remotamente.
        </p>
        {loading ? (
          <div className="text-[12px] text-[var(--color-text-muted)]">Cargando sesiones...</div>
        ) : sessions.length === 0 ? (
          <div className="text-[12px] text-[var(--color-text-muted)]">No hay sesiones activas.</div>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="flex items-center gap-3 p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]"
              >
                <Monitor size={16} className="text-[var(--color-text-muted)] flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-semibold text-[var(--color-text)]">
                    {s.device_name}
                  </div>
                  <div className="text-[11px] text-[var(--color-text-muted)]">
                    {s.ip_address && <span>IP: {s.ip_address} · </span>}
                    Última actividad: {formatDate(s.last_active_at)}
                  </div>
                </div>
                <button
                  onClick={() => handleRevokeSession(s.id)}
                  className="text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 p-1.5 rounded"
                  title="Revocar sesión"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Existing security panels */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Shield size={18} className="text-[var(--color-success)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Cifrado de Credenciales</h3>
        </div>
        <p className="text-[12px] text-[var(--color-text-muted)]">
          Todas las API Keys se cifran con Fernet (AES-128-CBC) antes de almacenarse en la base de datos local.
          Las credenciales nunca se envían al AI Server ni se exponen en el frontend.
        </p>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Lock size={18} className="text-[var(--color-primary)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Restricciones de Permisos</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>Solo se permiten API Keys con permisos de lectura y trading</li>
          <li className="text-[var(--color-danger)] font-semibold">Está prohibido conectar credenciales con permiso de retiro</li>
          <li>La conexión puede comenzar en modo READ_ONLY por seguridad</li>
          <li>El permiso de trading se habilita manualmente desde la configuración del broker</li>
        </ul>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <EyeOff size={18} className="text-[var(--color-warning)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Privacidad de Datos</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>Las API Keys no se almacenan en el frontend (localStorage, sessionStorage, cookies)</li>
          <li>Después de guardar, las credenciales no se muestran nuevamente</li>
          <li>Los logs nunca contienen secretos ni credenciales</li>
          <li>El AI Server recibe únicamente datos de mercado anonimizados</li>
        </ul>
      </div>

      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Ban size={18} className="text-[var(--color-danger)]" />
          <h3 className="text-[14px] font-bold text-[var(--color-text)]">Acciones Prohibidas</h3>
        </div>
        <ul className="text-[12px] text-[var(--color-text-muted)] space-y-1.5 list-disc ml-5">
          <li>No se simulan conexiones falsas de brokers</li>
          <li>No se ejecutan trades directamente desde respuestas del AI Server</li>
          <li>No se envían API Keys ni secrets al AI Server</li>
          <li>No se muestran API Secrets después de guardar</li>
        </ul>
      </div>

      {/* 2FA Setup Modal */}
      {showSetupModal && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={closeSetupModal}
        >
          <div
            className="w-[460px] max-w-[90vw] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <Key size={18} className="text-[var(--color-primary)]" />
              <h3 className="text-[16px] font-bold text-[var(--color-text)]">Configurar 2FA</h3>
            </div>

            {!setupData && !backupCodes && (
              <>
                <p className="text-[12px] text-[var(--color-text-muted)]">
                  Verifica tu contraseña para empezar la configuración de 2FA.
                </p>
                <div>
                  <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                    Contraseña actual
                  </label>
                  <Input
                    type="password"
                    value={setupPassword}
                    onChange={(e) => setSetupPassword(e.target.value)}
                    placeholder="********"
                    className="w-full"
                  />
                </div>
                <Button
                  variant="primary"
                  className="w-full"
                  disabled={setupLoading}
                  onClick={handleSetup2FA}
                >
                  {setupLoading ? "Verificando..." : "Continuar"}
                </Button>
              </>
            )}

            {setupData && !backupCodes && (
              <>
                <p className="text-[12px] text-[var(--color-text-muted)]">
                  Escanea este código QR con tu app autenticadora (Google Authenticator, Authy, etc.)
                  o ingresa el secreto manualmente.
                </p>
                <div className="flex justify-center p-4 bg-white rounded-lg">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(setupData.qr_uri)}`}
                    alt="QR Code"
                    className="w-[200px] h-[200px]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-1">
                    O ingresa manualmente:
                  </label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 p-2 rounded bg-[var(--color-surface-2)] text-[11px] font-mono text-[var(--color-text)] break-all">
                      {setupData.secret}
                    </code>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(setupData.secret);
                        toast("Copiado");
                      }}
                      className="p-2 rounded hover:bg-[var(--color-surface-2)]"
                    >
                      <Copy size={14} />
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                    Código de verificación
                  </label>
                  <Input
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="123456"
                    className="w-full text-center text-xl tracking-[0.3em] font-mono"
                    inputMode="numeric"
                    maxLength={6}
                  />
                </div>
                <Button
                  variant="primary"
                  className="w-full"
                  disabled={setupLoading || verifyCode.length !== 6}
                  onClick={handleVerify2FA}
                >
                  {setupLoading ? "Verificando..." : "Verificar y Activar"}
                </Button>
              </>
            )}

            {backupCodes && (
              <>
                <div className="flex items-center gap-2">
                  <Check size={18} className="text-[var(--color-success)]" />
                  <h4 className="text-[14px] font-bold text-[var(--color-success)]">2FA Activado</h4>
                </div>
                <div className="flex items-start gap-2 p-3 rounded-lg bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30">
                  <AlertTriangle size={16} className="text-[var(--color-warning)] flex-shrink-0 mt-0.5" />
                  <p className="text-[12px] text-[var(--color-text)]">
                    Guarda estos códigos de respaldo en un lugar seguro. Cada código se puede usar
                    una sola vez si pierdes acceso a tu app autenticadora.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]">
                  {backupCodes.map((code, i) => (
                    <code
                      key={i}
                      className="text-[14px] font-mono text-[var(--color-text)] text-center py-1"
                    >
                      {code}
                    </code>
                  ))}
                </div>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={copyBackupCodes}
                >
                  {copiedCodes ? <Check size={14} /> : <Copy size={14} />}
                  {copiedCodes ? "Copiado" : "Copiar códigos"}
                </Button>
                <Button variant="primary" className="w-full" onClick={closeSetupModal}>
                  Listo
                </Button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Disable 2FA Modal */}
      {showDisableModal && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setShowDisableModal(false)}
        >
          <div
            className="w-[460px] max-w-[90vw] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-[var(--color-danger)]" />
              <h3 className="text-[16px] font-bold text-[var(--color-text)]">Desactivar 2FA</h3>
            </div>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              Esto reducirá la seguridad de tu cuenta. Necesitas tu contraseña y un código 2FA válido.
            </p>
            <div>
              <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                Contraseña
              </label>
              <Input
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                placeholder="********"
                className="w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                Código 2FA
              </label>
              <Input
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                className="w-full text-center text-xl tracking-[0.3em] font-mono"
                inputMode="numeric"
                maxLength={6}
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                className="flex-1"
                onClick={() => setShowDisableModal(false)}
              >
                Cancelar
              </Button>
              <Button
                variant="danger"
                className="flex-1"
                disabled={disableLoading || !disablePassword || disableCode.length !== 6}
                onClick={handleDisable2FA}
              >
                {disableLoading ? "Desactivando..." : "Desactivar 2FA"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
