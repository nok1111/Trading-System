import { Component, ErrorInfo, ReactNode } from "react";
import { logger } from "../lib/logger";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logger.error("React crash", error.message + " | Stack: " + (error.stack || "") + " | ComponentStack: " + (errorInfo.componentStack || ""));
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-screen bg-[var(--color-bg)] p-8">
          <div className="max-w-lg w-full rounded-2xl border border-[var(--color-danger)] bg-[var(--color-surface)] p-8">
            <h2 className="text-xl font-bold text-[var(--color-danger)] mb-4">
              Error en la aplicación
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              {this.state.error?.message || "Error desconocido"}
            </p>
            <pre className="text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] rounded-lg p-3 overflow-auto max-h-48 mb-4">
              {this.state.error?.stack}
            </pre>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white font-semibold text-sm hover:opacity-90"
            >
              Recargar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
