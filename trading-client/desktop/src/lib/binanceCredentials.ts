/**
 * Fetches Binance API credentials from the backend for client-side signing.
 * Credentials are cached in memory only (never persisted to disk/localStorage).
 */

import { api } from "./api";

interface BinanceCredentials {
  api_key: string;
  api_secret: string;
  testnet: boolean;
}

let cachedCreds: BinanceCredentials | null = null;

export async function getBinanceCredentials(): Promise<BinanceCredentials | null> {
  if (cachedCreds) return cachedCreds;

  try {
    const creds = await api<BinanceCredentials>("/api/broker-accounts/binance/credentials");
    cachedCreds = creds;
    return creds;
  } catch (err) {
    console.error("Failed to fetch Binance credentials:", err);
    return null;
  }
}

export function clearCachedCredentials(): void {
  cachedCreds = null;
}

export function hasCachedCredentials(): boolean {
  return cachedCreds !== null;
}
