// Frontend logging utility — captures errors and logs to file via backend

export type LogLevel = "info" | "warn" | "error" | "debug";

export function log(level: LogLevel, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const entry = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
  if (data) {
    const dataStr = typeof data === "string" ? data : (() => {
      try { return JSON.stringify(data); } catch { return String(data); }
    })();
    console.log(entry, dataStr);
  } else {
    console.log(entry);
  }

  // Send to backend for file logging
  try {
    fetch("http://localhost:8080/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level, message, data: data ? String(data) : undefined, timestamp }),
    }).catch(() => {});
  } catch {}
}

export const logger = {
  info: (msg: string, data?: any) => log("info", msg, data),
  warn: (msg: string, data?: any) => log("warn", msg, data),
  error: (msg: string, data?: any) => log("error", msg, data),
  debug: (msg: string, data?: any) => log("debug", msg, data),
};
