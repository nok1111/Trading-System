import { useState } from "react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { toast } from "../ui/Toast";

interface LoginScreenProps {
  onLogin: (email: string, password: string) => Promise<any>;
  onRegister: (email: string, username: string, password: string) => Promise<any>;
}

export function LoginScreen({ onLogin, onRegister }: LoginScreenProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
    setLoading(true);
    try {
      if (mode === "login") {
        await onLogin(email, password);
        toast("Sesión iniciada");
      } else {
        await onRegister(email, username, password);
        toast("Cuenta creada");
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)]">
      <div className="w-[460px] max-w-[90vw] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-10 shadow-2xl">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center">
            <span className="text-white font-bold text-xl">A</span>
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
            />
          </div>

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
                onClick={() => {
                  setMode("register");
                  setError("");
                }}
                className="text-[var(--color-primary)] font-semibold hover:underline"
              >
                Registrarse
              </button>
            </>
          ) : (
            <>
              Ya tienes cuenta?{" "}
              <button
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
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
