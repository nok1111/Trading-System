import { type HTMLAttributes, type ReactNode, forwardRef } from "react";
import { cn } from "../../lib/utils";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-[16px] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-card)] transition-shadow hover:shadow-[var(--shadow-card-hover)]",
          className
        )}
        {...props}
      />
    );
  }
);
Card.displayName = "Card";

export function CardLabel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "text-[11px] leading-[14px] uppercase tracking-[0.06em] text-[var(--color-text-muted)] font-semibold",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardValue({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "num text-[22px] leading-tight font-bold mt-1.5 text-[var(--color-text)]",
        className
      )}
    >
      {children}
    </div>
  );
}

type Tone = "primary" | "success" | "danger" | "warning" | "accent" | "cyan";

const toneVar: Record<Tone, string> = {
  primary: "var(--color-primary)",
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  cyan: "var(--color-cyan)",
};

export function IconChip({
  children,
  tone = "primary",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  const c = toneVar[tone];
  return (
    <span
      className={cn("icon-chip", className)}
      style={{ background: `color-mix(in srgb, ${c} 14%, transparent)`, color: c }}
    >
      {children}
    </span>
  );
}

/** Compact KPI tile: icon + label + value + optional delta/footer. */
export function StatCard({
  icon,
  label,
  value,
  tone = "primary",
  delta,
  footer,
  className,
}: {
  icon?: ReactNode;
  label: string;
  value: ReactNode;
  tone?: Tone;
  delta?: { value: string; positive?: boolean };
  footer?: ReactNode;
  className?: string;
}) {
  const c = toneVar[tone];
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[16px] bg-[var(--color-surface)] pl-[18px] pr-4 py-3.5 shadow-[var(--shadow-card)] transition-all hover:shadow-[var(--shadow-card-hover)] hover:-translate-y-px",
        className
      )}
    >
      <span
        className="absolute left-0 top-0 h-full w-[3px]"
        style={{ background: c }}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <CardLabel>{label}</CardLabel>
          <div className="num text-[22px] leading-tight font-bold mt-1.5 text-[var(--color-text)] truncate">
            {value}
          </div>
        </div>
        {icon && <IconChip tone={tone}>{icon}</IconChip>}
      </div>
      {(delta || footer) && (
        <div className="flex items-center gap-2 mt-2.5">
          {delta && (
            <span
              className="text-[11px] font-bold px-1.5 py-0.5 rounded-md"
              style={{
                background: `color-mix(in srgb, ${
                  delta.positive
                    ? "var(--color-success)"
                    : "var(--color-danger)"
                } 14%, transparent)`,
                color: delta.positive
                  ? "var(--color-success)"
                  : "var(--color-danger)",
              }}
            >
              {delta.value}
            </span>
          )}
          {footer && (
            <span className="text-[11px] text-[var(--color-text-muted)] truncate">
              {footer}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/** Section panel with a titled header row and flush body. */
export function Panel({
  title,
  icon,
  tone = "primary",
  actions,
  children,
  bodyClassName,
  className,
}: {
  title: string;
  icon?: ReactNode;
  tone?: Tone;
  actions?: ReactNode;
  children: ReactNode;
  bodyClassName?: string;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex flex-col rounded-[16px] bg-[var(--color-surface)] shadow-[var(--shadow-card)] overflow-hidden",
        className
      )}
    >
      <header className="flex items-center justify-between gap-3 px-4 pt-3.5 pb-2.5">
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && (
            <IconChip tone={tone} className="!w-7 !h-7 !rounded-lg">
              {icon}
            </IconChip>
          )}
          <h3 className="text-[13.5px] font-bold text-[var(--color-text)] tracking-tight truncate">
            {title}
          </h3>
        </div>
        {actions && (
          <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>
        )}
      </header>
      <div className={cn("px-4 pb-4 flex-1 min-h-0", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}
