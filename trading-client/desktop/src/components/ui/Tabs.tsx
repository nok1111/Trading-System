import { type ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: ReactNode;
}

export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex gap-1 border-b border-[var(--color-border)]", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "px-4 h-10 flex items-center gap-2 text-[13px] font-semibold transition-colors border-b-2 -mb-px btn-press",
            active === tab.id
              ? "text-[var(--color-text)] border-[var(--color-primary)]"
              : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
          )}
        >
          {tab.icon}
          {tab.label}
          {tab.badge}
        </button>
      ))}
    </div>
  );
}
