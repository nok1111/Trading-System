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
    // Only run in Tauri production environment (not dev mode, not browser)
    if (!(window as any).__TAURI_INTERNALS__) return;
    // Skip in dev mode — updater only works in signed release builds
    if (import.meta.env.DEV) return;

    setState((s) => ({ ...s, checking: true, error: null }));
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (update) {
        console.info(`[Updater] Update available: v${update.version}`);
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
      // Silently log — don't disrupt the user experience
      console.warn("[Updater] Check failed:", err?.message || err);
      setState((s) => ({
        ...s,
        checking: false,
        error: null, // Don't surface updater errors to UI
      }));
    }
  }, []);

  const downloadAndInstall = useCallback(async () => {
    if (!(window as any).__TAURI_INTERNALS__) return;
    if (import.meta.env.DEV) return;

    setState((s) => ({ ...s, downloading: true, error: null }));
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (!update) {
        setState((s) => ({ ...s, downloading: false }));
        return;
      }
      console.info(`[Updater] Downloading v${update.version}...`);
      await update.downloadAndInstall();
      console.info("[Updater] Installed — relaunching...");
      setState((s) => ({ ...s, downloading: false, downloaded: true }));
      // Relaunch the app after install
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (err: any) {
      console.warn("[Updater] Download/install failed:", err?.message || err);
      setState((s) => ({
        ...s,
        downloading: false,
        error: null, // Don't surface updater errors to UI
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
