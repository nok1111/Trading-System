import { useEffect } from "react";
import { X } from "lucide-react";
import type { XPLevel } from "../../data/tutorials";
import { Confetti } from "./Confetti";

interface LevelUpModalProps {
  level: XPLevel;
  show: boolean;
  onClose: () => void;
}

export function LevelUpModal({ level, show, onClose }: LevelUpModalProps) {
  useEffect(() => {
    if (!show) return;
    const timer = setTimeout(() => {
      onClose();
    }, 5000);
    return () => clearTimeout(timer);
  }, [show, onClose]);

  if (!show) return null;

  return (
    <>
      <Confetti show={show} />
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fade-in-up"
        style={{
          background: "rgba(0, 0, 0, 0.6)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
        }}
        onClick={onClose}
      >
        <div
          className="relative panel p-8 max-w-sm w-full text-center"
          onClick={(e) => e.stopPropagation()}
          style={{
            background:
              "linear-gradient(135deg, var(--color-surface), var(--color-surface-2))",
            border: "2px solid var(--color-primary)",
            boxShadow: "0 0 40px color-mix(in srgb, var(--color-primary) 30%, transparent)",
          }}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1.5 rounded-lg hover:bg-[var(--color-surface-2)] transition-colors"
          >
            <X size={16} />
          </button>

          {/* Level icon */}
          <div
            className="flex items-center justify-center w-24 h-24 mx-auto mb-4 rounded-full text-[48px]"
            style={{
              background: "color-mix(in srgb, var(--color-primary) 15%, transparent)",
              border: "3px solid var(--color-primary)",
            }}
          >
            {level.icon}
          </div>

          {/* Message */}
          <div className="text-[18px] font-extrabold text-[var(--color-primary)] mb-1">
            ¡Nivel {level.level} desbloqueado!
          </div>
          <div className="text-[22px] font-extrabold text-[var(--color-text)] mb-2">
            {level.title}
          </div>
          <div className="text-[13px] text-[var(--color-text-muted)] mb-6">
            Has acumulado {level.minXp} XP. ¡Sigue así para alcanzar el siguiente nivel!
          </div>

          {/* Continue button */}
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white text-[14px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            Continuar
          </button>
        </div>
      </div>
    </>
  );
}
