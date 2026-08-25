import { useUpdater } from "../hooks/useUpdater";
import { useEffect } from "react";

/**
 * Silent auto-updater that runs on app load.
 * Shows a toast notification when an update is available,
 * then downloads and installs it automatically.
 *
 * In dev mode, this is a no-op (Tauri internals not available).
 */
export function AutoUpdater() {
  const { available, version, downloading, downloaded, error, downloadAndInstall } = useUpdater(true);

  useEffect(() => {
    if (available && !downloading && !downloaded) {
      // Auto-download and install silently
      downloadAndInstall();
    }
  }, [available, downloading, downloaded, downloadAndInstall]);

  // Log errors but don't show UI — silent updater
  useEffect(() => {
    if (error) {
      console.warn("[Updater] Update check failed:", error);
    }
  }, [error]);

  // Log progress
  useEffect(() => {
    if (available) {
      console.info(`[Updater] Update available: v${version}`);
    }
  }, [available, version]);

  useEffect(() => {
    if (downloading) {
      console.info("[Updater] Downloading update...");
    }
  }, [downloading]);

  useEffect(() => {
    if (downloaded) {
      console.info("[Updater] Update installed — relaunching...");
    }
  }, [downloaded]);

  return null; // No UI — silent updater
}
