import { useState, useEffect, useCallback } from "react";

interface UpdateState {
  checking: boolean;
  available: boolean;
  version: string | null;
  body: string | null;
  downloading: boolean;
  downloaded: boolean;
  error: string | null;
}

interface UpdateStateReturn extends UpdateState {
  checkForUpdates: () => Promise<void>;
  downloadAndInstall: () => Promise<void>;
}

/**
 * Hook that checks for app updates on mount and provides
 * downloadAndInstall to apply the update.
 *
 * Uses the Tauri updater plugin which checks the endpoint
 * configured in tauri.conf.json (GitHub releases latest.json).
 *
 * In dev mode or non-Tauri environments, this is a no-op.
 */
export function useUpdater(autoCheck: boolean = true): UpdateStateReturn {
  const [state, setState] = useState<UpdateState>({
    checking: false,
    available: false,
    version: null,
    body: null,
    downloading: false,
    downloaded: false,
    error: null,
  });

  const checkForUpdates = useCallback(async () => {
    // Only run in Tauri environment
    if (!(window as any).__TAURI_INTERNALS__) return;

    setState((s) => ({ ...s, checking: true, error: null }));
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (update) {
        setState((s) => ({
          ...s,
          checking: false,
          available: true,
          version: update.version,
          body: update.body || null,
        }));
      } else {
        setState((s) => ({
          ...s,
          checking: false,
          available: false,
        }));
      }
    } catch (err: any) {
      setState((s) => ({
        ...s,
        checking: false,
        error: err?.message || String(err),
      }));
    }
  }, []);

  const downloadAndInstall = useCallback(async () => {
    if (!(window as any).__TAURI_INTERNALS__) return;

    setState((s) => ({ ...s, downloading: true, error: null }));
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (!update) {
        setState((s) => ({ ...s, downloading: false }));
        return;
      }
      await update.downloadAndInstall();
      setState((s) => ({ ...s, downloading: false, downloaded: true }));
      // Relaunch the app after install
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (err: any) {
      setState((s) => ({
        ...s,
        downloading: false,
        error: err?.message || String(err),
      }));
    }
  }, []);

  useEffect(() => {
    if (autoCheck) {
      // Delay check slightly so app loads first
      const timer = setTimeout(() => checkForUpdates(), 2000);
      return () => clearTimeout(timer);
    }
  }, [autoCheck, checkForUpdates]);

  return { ...state, checkForUpdates, downloadAndInstall };
}
