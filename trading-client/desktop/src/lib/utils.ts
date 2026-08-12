import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(n: number | string | null | undefined): string {
  if (n == null) return "-";
  const v = Number(n);
  if (isNaN(v)) return "-";
  if (v === 0) return "0";
  // Show full precision, no rounding
  return String(v);
}

/**
 * Parse a timestamp string from the backend as UTC and return a Date object.
 * Backend DB timestamps (from .isoformat()) often lack timezone info,
 * so JS would interpret them as local time. This appends "Z" if needed.
 */
export function parseDate(d: string | null | undefined): Date | null {
  if (!d) return null;
  const s = String(d).trim();
  // Check if timezone info is present: "Z", "+00:00", "-05:00" suffix
  const hasTz = /[Zz]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s);
  // If no timezone, assume UTC by appending "Z"
  // Also handle space-separated timestamps: "2026-08-08 06:06:32" -> "2026-08-08T06:06:32Z"
  const normalized = s.replace(" ", "T");
  const withTz = hasTz ? normalized : normalized + "Z";
  const date = new Date(withTz);
  return isNaN(date.getTime()) ? null : date;
}

export function fmtDate(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "-";
  return date.toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Format date as short date + time (e.g. "12/08 22:08") */
export function fmtDateTime(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "-";
  return date.toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format time only (e.g. "22:08:56") */
export function fmtTime(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "";
  return date.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Format date only (e.g. "12/08/2026") */
export function fmtDateOnly(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "-";
  return date.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Format short date (e.g. "12 ago") */
export function fmtDateShort(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "-";
  return date.toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

/** Relative time ago (e.g. "hace 5m", "hace 2h") */
export function fmtTimeAgo(d: string | null | undefined): string {
  const date = parseDate(d);
  if (!date) return "";
  const diff = Date.now() - date.getTime();
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor(diff / 60000);
  if (hours > 0) return `hace ${hours}h ${mins % 60}m`;
  if (mins > 0) return `hace ${mins}m`;
  return "ahora";
}

export function fmtVol(v: number | string | null | undefined): string {
  const n = Number(v);
  if (isNaN(n)) return "--";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(2) + "K";
  return n.toFixed(2);
}

export function nowTime(): string {
  return new Date().toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
