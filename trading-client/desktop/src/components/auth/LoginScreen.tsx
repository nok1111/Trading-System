import { useState } from "react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { toast } from "../ui/Toast";
import alvoraLogo from "../../assets/alvora-logo.png";

interface LoginScreenProps {
  onLogin: (email: string, password: string, totpCode?: string) => Promise<any>;
  onRegister: (email: string, username: string, password: string) => Promise<any>;
}

export function LoginScreen({ onLogin, onRegister }: LoginScreenProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [totpRequired, setTotpRequired] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Email y password requeridos");
      return;
    }
    if (mode === "register" && !username) {
      setError("Username requerido");
      return;
    }
    if (mode === "register" && password.length < 6) {
      setError("Password mínimo 6 caracteres");
      return;
    }
    if (totpRequired && !totpCode) {
      setError("Código 2FA requerido");
      return;
    }
    setLoading(true);
    try {
      if (mode === "login") {
        await onLogin(email, password, totpCode || undefined);
        toast("Sesión iniciada");
      } else {
        await onRegister(email, username, password);
        toast("Cuenta creada");
      }
    } catch (e: any) {
      // Check if the error indicates 2FA is required
      const msg = e.message || "";
      if (msg.includes("2FA") || msg.includes("totp") || msg.includes("código 2FA")) {
        setTotpRequired(true);
        setError("Esta cuenta tiene 2FA activado. Ingresa tu código.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: "login" | "register") => {
    setMode(newMode);
    setError("");
    setTotpRequired(false);
    setTotpCode("");
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
      <div className="w-[460px] max-w-[90vw] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-10 shadow-2xl">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-xl bg-[var(--color-surface-2)] flex items-center justify-center overflow-hidden">
            <img src={alvoraLogo} alt="Alvora" className="w-full h-full object-contain" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)]">Alvora</h1>
            <p className="text-sm text-[var(--color-text-muted)]">AI Trading System</p>
          </div>
        </div>

        <p className="text-base text-[var(--color-text-muted)] mb-8">
          {mode === "login"
            ? "Inicia sesión para acceder al dashboard"
            : "Crea tu cuenta para empezar"}
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
              Email
            </label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com"
              className="w-full"
              disabled={totpRequired}
            />
          </div>

          {mode === "register" && (
            <div>
              <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                Usuario
              </label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="tu_usuario"
                className="w-full"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
              Password
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
              className="w-full"
              disabled={totpRequired}
            />
          </div>

          {totpRequired && (
            <div>
              <label className="block text-sm font-semibold text-[var(--color-text-muted)] mb-2">
                Código 2FA (Google Authenticator / Authy)
              </label>
              <Input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                className="w-full text-center text-2xl tracking-[0.5em] font-mono"
                autoFocus
                inputMode="numeric"
                maxLength={6}
              />
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                Ingresa el código de 6 dígitos de tu app autenticadora
              </p>
            </div>
          )}

          {error && (
            <div className="text-base text-[var(--color-danger)] bg-[var(--color-danger)]/10 rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={loading}
          >
            {loading
              ? "Conectando..."
              : mode === "login"
                ? "Iniciar Sesión"
                : "Crear Cuenta"}
          </Button>
        </form>

        <div className="text-center mt-6 text-base text-[var(--color-text-muted)]">
          {mode === "login" ? (
            <>
              No tienes cuenta?{" "}
              <button
                onClick={() => switchMode("register")}
                className="text-[var(--color-primary)] font-semibold hover:underline"
              >
                Registrarse
              </button>
            </>
          ) : (
            <>
              Ya tienes cuenta?{" "}
              <button
                onClick={() => switchMode("login")}
                className="text-[var(--color-primary)] font-semibold hover:underline"
              >
                Iniciar Sesión
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
