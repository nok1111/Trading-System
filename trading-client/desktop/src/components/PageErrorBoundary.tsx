import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { logger } from "../lib/logger";

interface Props {
  children: ReactNode;
  pageName: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Page-level error boundary with recovery UI.
 * Wraps individual pages to prevent a single page crash from taking down the entire app.
 */
export class PageErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logger.error(
      `Page error [${this.props.pageName}]`,
      error.message + " | Stack: " + (error.stack || "") + " | ComponentStack: " + (errorInfo.componentStack || "")
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    this.setState({ hasError: false, error: null });
    // Dispatch a custom event that App.tsx can listen to for navigation
    window.dispatchEvent(new CustomEvent("navigate", { detail: "dashboard" }));
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-[60vh] p-8">
          <div className="max-w-md w-full rounded-[16px] border border-[var(--color-danger)]/30 bg-[var(--color-surface)] p-8 text-center">
            <div className="w-14 h-14 rounded-full bg-[var(--color-danger)]/10 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={26} className="text-[var(--color-danger)]" />
            </div>
            <h2 className="text-[16px] font-extrabold text-[var(--color-text)] mb-2">
              Error en esta página
            </h2>
            <p className="text-[13px] text-[var(--color-text-muted)] mb-6">
              Algo salió mal al cargar esta sección. Puedes reintentar, recargar la página o volver al dashboard.
            </p>
            <div className="flex flex-col gap-2.5">
              <button
                onClick={this.handleRetry}
                className="flex items-center justify-center gap-2 w-full h-10 rounded-[10px] bg-[var(--color-primary)] text-white font-bold text-[13px] hover:opacity-90 transition-opacity"
              >
                <RotateCcw size={15} />
                Reintentar
              </button>
              <button
                onClick={this.handleReload}
                className="w-full h-10 rounded-[10px] bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[var(--color-text)] font-bold text-[13px] hover:border-[var(--color-border-strong)] transition-colors"
              >
                Recargar página
              </button>
              <button
                onClick={this.handleGoHome}
                className="flex items-center justify-center gap-2 w-full h-10 rounded-[10px] text-[var(--color-text-muted)] font-semibold text-[13px] hover:text-[var(--color-text)] transition-colors"
              >
                <Home size={15} />
                Ir al Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
