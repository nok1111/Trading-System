import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { AlvoraChat } from "../alvora/AlvoraChat";
import { alvoraGetStatus, type AlvoraStatus } from "../../lib/alvoraApi";

export function AlvoraSection() {
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
    const id = setInterval(load, 30000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-[10px] bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] flex items-center justify-center shadow-lg shadow-[var(--color-primary)]/20">
            <Sparkles size={16} className="text-white" />
          </div>
          <div>
            <h3 className="text-[14px] font-extrabold text-[var(--color-text)] leading-none">Alvora</h3>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">Tu asesor de trading personal</p>
          </div>
        </div>
        {status && (
          <div className="flex items-center gap-1.5 px-2 h-6 rounded-full bg-[var(--color-surface-2)] border border-[var(--color-border)]">
            <span
              className={`w-1.5 h-1.5 rounded-full ${status.available ? "bg-[var(--color-success)]" : "bg-[var(--color-text-muted)]"}`}
            />
            <span className="text-[10px] font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
              {status.available ? "Disponible" : "Sin configurar"}
            </span>
          </div>
        )}
      </div>
      <AlvoraChat className="h-[480px]" />
    </div>
  );
}
