import { useUpdater } from "../hooks/useUpdater";
import { useEffect } from "react";

/**
 * Silent auto-updater that runs on app load.
 * Checks for updates 3s after startup, downloads and installs
 * automatically if a newer version is found, then relaunches.
 *
 * In dev mode, this is a no-op.
 * All errors are silently logged to console — never shown to user.
 */
export function AutoUpdater() {
  const { available, version, downloading, downloaded, downloadAndInstall } = useUpdater(true);

  useEffect(() => {
    if (available && !downloading && !downloaded) {
      console.info(`[Updater] Auto-installing update v${version}...`);
      downloadAndInstall();
    }
  }, [available, version, downloading, downloaded, downloadAndInstall]);

  return null; // No UI — completely silent
}
