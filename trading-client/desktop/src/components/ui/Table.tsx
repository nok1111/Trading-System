import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

interface TableProps extends HTMLAttributes<HTMLTableElement> {}

export function Table({ className, children, ...props }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn("w-full text-[13px] border-collapse", className)}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={cn(
        "text-left px-3 py-2.5 sticky top-0 bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-bold text-[11px] uppercase tracking-[0.06em] border-b border-[var(--color-border)] whitespace-nowrap",
        className
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <td
      className={cn(
        "px-3 py-2.5 border-b border-[var(--color-border)] text-[var(--color-text)] whitespace-nowrap",
        className
      )}
    >
      {children}
    </td>
  );
}

export function Tr({
  children,
  className,
  onClick,
}: {
  children?: React.ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <tr
      className={cn(
        "transition-colors hover:bg-[var(--color-surface-hover)]",
        onClick && "cursor-pointer",
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  );
}
