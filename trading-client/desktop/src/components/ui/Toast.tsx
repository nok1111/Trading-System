import { useEffect, useState } from "react";
import { cn } from "../../lib/utils";

export function Toast() {
  const [toast, setToast] = useState<{
    msg: string;
    ok: boolean;
  } | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setToast({ msg: detail.msg, ok: detail.ok });
      setTimeout(() => setToast(null), 3000);
    };
    window.addEventListener("app-toast", handler);
    return () => window.removeEventListener("app-toast", handler);
  }, []);

  if (!toast) return null;

  return (
    <div
      className={cn(
        "fixed bottom-6 right-6 px-5 py-3 rounded-lg text-sm font-medium z-50 transition-opacity shadow-lg",
        toast.ok
          ? "bg-[var(--color-success)] text-white"
          : "bg-[var(--color-danger)] text-white"
      )}
    >
      {toast.msg}
    </div>
  );
}

export function toast(msg: string, ok: boolean = true) {
  window.dispatchEvent(
    new CustomEvent("app-toast", { detail: { msg, ok } })
  );
}
