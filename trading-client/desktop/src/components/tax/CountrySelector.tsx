// CountrySelector — dropdown/grid picker for tax jurisdiction.

import { Select } from "../ui/Input";
import type { CountryInfo } from "../../lib/taxApi";
import { cn } from "../../lib/utils";

interface CountrySelectorProps {
  countries: CountryInfo[];
  value: string;
  onChange: (code: string) => void;
  className?: string;
}

export function CountrySelector({
  countries,
  value,
  onChange,
  className,
}: CountrySelectorProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label className="block text-[12px] font-semibold text-[var(--color-text-muted)]">
        Country / Jurisdiction
      </label>
      <Select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full"
      >
        {countries.map((c) => (
          <option key={c.code} value={c.code}>
            {c.flag} {c.name} ({c.code})
          </option>
        ))}
      </Select>
    </div>
  );
}

/** Grid of country cards with flags — for visual selection. */
export function CountryGrid({
  countries,
  value,
  onChange,
  className,
}: CountrySelectorProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 sm:grid-cols-4 gap-2",
        className,
      )}
    >
      {countries.map((c) => {
        const active = c.code === value;
        return (
          <button
            key={c.code}
            onClick={() => onChange(c.code)}
            className={cn(
              "flex flex-col items-center gap-1 px-3 py-2.5 rounded-lg border transition-all cursor-pointer",
              active
                ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10"
                : "border-[var(--color-border)] bg-[var(--color-surface-2)] hover:border-[var(--color-primary)]/40",
            )}
          >
            <span className="text-xl leading-none">{c.flag}</span>
            <span
              className={cn(
                "text-[11px] font-bold",
                active
                  ? "text-[var(--color-primary)]"
                  : "text-[var(--color-text-muted)]",
              )}
            >
              {c.code}
            </span>
            <span className="text-[10px] text-[var(--color-text-muted)] truncate w-full text-center">
              {c.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
