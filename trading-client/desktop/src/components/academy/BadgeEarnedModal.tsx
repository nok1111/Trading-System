import { useEffect } from "react";
import { X } from "lucide-react";
import type { Badge } from "../../data/tutorials";
import { Confetti } from "./Confetti";

interface BadgeEarnedModalProps {
  badge: Badge | null;
  show: boolean;
  onClose: () => void;
}

export function BadgeEarnedModal({
  badge,
  show,
  onClose,
}: BadgeEarnedModalProps) {
  useEffect(() => {
    if (!show) return;
    const timer = setTimeout(() => {
      onClose();
    }, 5000);
    return () => clearTimeout(timer);
  }, [show, onClose]);

  if (!show || !badge) return null;

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
            boxShadow:
              "0 0 40px color-mix(in srgb, var(--color-primary) 30%, transparent)",
          }}
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1.5 rounded-lg hover:bg-[var(--color-surface-2)] transition-colors"
          >
            <X size={16} />
          </button>

          {/* Badge icon with animation */}
          <div
            className="flex items-center justify-center w-24 h-24 mx-auto mb-4 rounded-full text-[48px]"
            style={{
              background:
                "color-mix(in srgb, var(--color-primary) 15%, transparent)",
              border: "3px solid var(--color-primary)",
              animation: "badge-pop 0.6s ease-out",
            }}
          >
            <style>{`
              @keyframes badge-pop {
                0% { transform: scale(0) rotate(-180deg); opacity: 0; }
                60% { transform: scale(1.2) rotate(10deg); opacity: 1; }
                100% { transform: scale(1) rotate(0deg); opacity: 1; }
              }
            `}</style>
            {badge.icon}
          </div>

          {/* Message */}
          <div className="text-[11px] font-bold text-[var(--color-primary)] uppercase tracking-wider mb-1">
            ¡Badge Desbloqueado!
          </div>
          <div className="text-[20px] font-extrabold text-[var(--color-text)] mb-2">
            {badge.name}
          </div>
          <div className="text-[13px] text-[var(--color-text-muted)] mb-6">
            {badge.description}
          </div>

          {/* Continue button */}
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] text-white text-[14px] font-bold hover:bg-[var(--color-primary)]/90 transition-colors"
          >
            ¡Genial!
          </button>
        </div>
      </div>
    </>
  );
}
