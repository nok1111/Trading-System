/**
 * Binance HMAC-SHA256 request signing for client-side use.
 *
 * Uses Web Crypto API (available in Electron's renderer process).
 * Fallback to Node.js crypto module if needed.
 */

async function hmacSha256(secret: string, message: string): Promise<string> {
  // Try Web Crypto API first (works in Electron renderer)
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
    return Array.from(new Uint8Array(signature))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  // Fallback: Node.js crypto (Electron main process)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodeCrypto = (globalThis as any).require?.("crypto");
  if (nodeCrypto) {
    return nodeCrypto.createHmac("sha256", secret).update(message).digest("hex");
  }
  throw new Error("No HMAC implementation available (neither Web Crypto nor Node.js crypto)");
}

export interface SignedRequest {
  params: Record<string, string>;
  signature: string;
}

/**
 * Sign Binance API request parameters with HMAC-SHA256.
 *
 * @param apiSecret - Binance API secret
 * @param params - Request parameters (without timestamp or signature)
 * @returns Signed params including timestamp and signature
 */
export async function signBinanceRequest(
  apiSecret: string,
  params: Record<string, string | number>
): Promise<SignedRequest> {
  const timestamp = Date.now().toString();

  const allParams: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    allParams[key] = String(value);
  }
  allParams["timestamp"] = timestamp;

  // Build query string
  const query = Object.entries(allParams)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");

  const signature = await hmacSha256(apiSecret, query);
  allParams["signature"] = signature;

  return { params: allParams, signature };
}
