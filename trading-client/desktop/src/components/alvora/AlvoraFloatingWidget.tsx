import { useState, useEffect } from "react";
import { Sparkles, X } from "lucide-react";
import { cn } from "../../lib/utils";
import { AlvoraChat } from "./AlvoraChat";
import { alvoraGetStatus, type AlvoraStatus } from "../../lib/alvoraApi";

export function AlvoraFloatingWidget() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<AlvoraStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const s = await alvoraGetStatus();
        if (alive) setStatus(s);
      } catch {}
    };
    load();
    const id = setInterval(load, 60000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-50 flex items-center gap-2 h-12 pl-3 pr-4 rounded-full bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] text-white shadow-lg shadow-[var(--color-primary)]/30 hover:shadow-xl hover:shadow-[var(--color-primary)]/40 hover:scale-105 transition-all"
          title="Hablar con Alvora"
        >
          <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
            <Sparkles size={16} className="text-white" />
          </div>
          <span className="text-[13px] font-extrabold">Alvora</span>
          {status && (
            <span
              className={cn(
                "w-2 h-2 rounded-full flex-shrink-0",
                status.available ? "bg-[var(--color-success)]" : "bg-white/40"
              )}
            />
          )}
        </button>
      )}

      {/* Chat overlay */}
      {open && (
        <>
          {/* Backdrop (mobile only) */}
          <div
            className="fixed inset-0 bg-black/30 z-40 md:hidden"
            onClick={() => setOpen(false)}
          />
          <div
            className={cn(
              "fixed z-50 bg-[var(--color-bg)] shadow-2xl",
              "bottom-5 right-5",
              "w-[calc(100vw-2.5rem)] h-[calc(100vh-2.5rem)]",
              "md:w-[400px] md:h-[560px]",
              "rounded-[16px] overflow-hidden border border-[var(--color-border)]",
              "flex flex-col"
            )}
          >
            {/* Close bar */}
            <div className="flex items-center justify-between px-3 py-2 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex-shrink-0">
              <span className="text-[11px] text-[var(--color-text-muted)] font-semibold">
                Asesor de trading
              </span>
              <button
                onClick={() => setOpen(false)}
                className="flex items-center justify-center w-7 h-7 rounded-[8px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            {/* Chat (fills remaining space) */}
            <div className="flex-1 min-h-0">
              <AlvoraChat compact className="h-full border-0 rounded-none" />
            </div>
          </div>
        </>
      )}
    </>
  );
}
