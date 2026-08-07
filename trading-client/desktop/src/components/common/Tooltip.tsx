import { useState, type ReactNode } from "react";
import { Info } from "lucide-react";
import { cn } from "../../lib/utils";

interface TooltipProps {
  text: string;
  children?: ReactNode;
  icon?: boolean;
  className?: string;
}

/** Lightweight CSS-only tooltip — no portal needed, works inside panels. */
export function Tooltip({ text, children, icon = false, className }: TooltipProps) {
  const [show, setShow] = useState(false);
  return (
    <span
      className={cn("relative inline-flex items-center", className)}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {icon && (
        <Info size={13} className="text-[var(--color-text-muted)] ml-1 cursor-help" />
      )}
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-max max-w-[280px] rounded-[6px] bg-[var(--color-surface)] border border-[var(--color-border)] px-3 py-2 text-[10px] font-medium text-[var(--color-text)] shadow-xl pointer-events-none whitespace-normal">
          {text}
        </span>
      )}
    </span>
  );
}

interface InfoPanelProps {
  title: string;
  children: ReactNode;
  className?: string;
}

/** Collapsible info panel that explains what a page/section does and how to use it. */
export function InfoPanel({ title, children, className }: InfoPanelProps) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cn("rounded-[10px] bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/15", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left"
      >
        <Info size={14} className="text-[var(--color-primary)] flex-shrink-0" />
        <span className="text-[12px] font-bold text-[var(--color-primary)] flex-1">{title}</span>
        <span className="text-[10px] text-[var(--color-text-muted)]">{open ? "Ocultar" : "Ayuda"}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 text-[11px] text-[var(--color-text-muted)] leading-relaxed space-y-1.5">
          {children}
        </div>
      )}
    </div>
  );
}
