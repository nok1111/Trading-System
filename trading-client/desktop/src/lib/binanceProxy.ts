/**
 * High-level Binance API client that routes requests through the VPS proxy.
 *
 * The client signs requests locally with HMAC-SHA256 and sends them to the
 * proxy, which forwards to Binance. API keys never touch the VPS.
 */

import { signBinanceRequest } from "./binanceSigner";
import { getBinanceCredentials } from "./binanceCredentials";

const DEFAULT_PROXY_URL = "http://76.13.180.80:9100";
const DEFAULT_PROXY_TOKEN = "9448c6314b9a70f270728f4fadf7f0cee73d643481094a56b52d6aed2f76de4c";
const PROXY_TOKEN_KEY = "binanceProxyToken";

function getProxyUrl(): string {
  return localStorage.getItem("binanceProxyUrl") || DEFAULT_PROXY_URL;
}

function getProxyToken(): string {
  return localStorage.getItem(PROXY_TOKEN_KEY) || DEFAULT_PROXY_TOKEN;
}

export function setProxyConfig(url: string, token: string): void {
  localStorage.setItem("binanceProxyUrl", url);
  localStorage.setItem(PROXY_TOKEN_KEY, token);
}

export function getProxyConfig(): { url: string; token: string } {
  return { url: getProxyUrl(), token: getProxyToken() };
}

export class BinanceProxyError extends Error {
  code?: number;
  constructor(message: string, code?: number) {
    super(message);
    this.code = code;
    this.name = "BinanceProxyError";
  }
}

/**
 * Low-level: send a signed request through the proxy.
 */
async function binanceRequest(
  method: "GET" | "POST" | "DELETE",
  path: string,
  params: Record<string, string | number> = {},
  requireAuth = true
): Promise<any> {
  const proxyUrl = getProxyUrl();
  const proxyToken = getProxyToken();

  if (!proxyToken) {
    throw new BinanceProxyError("Proxy token no configurado. Ve a Settings para configurarlo.");
  }

  let apiKey = "";
  let apiSecret = "";
  let testnet = false;

  if (requireAuth) {
    const creds = await getBinanceCredentials();
    if (!creds) {
      throw new BinanceProxyError("No hay credenciales de Binance. Conecta tu broker desde Conexiones.");
    }
    apiKey = creds.api_key;
    apiSecret = creds.api_secret;
    testnet = creds.testnet;

    const { params: signedParams } = await signBinanceRequest(apiSecret, params);
    params = signedParams;
  }

  const body = {
    method,
    path,
    params,
    api_key_header: apiKey,
    testnet,
  };

  const resp = await fetch(`${proxyUrl}/proxy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${proxyToken}`,
    },
    body: JSON.stringify(body),
  });

  if (resp.status === 401) {
    throw new BinanceProxyError("Token del proxy inválido. Contacta soporte.");
  }
  if (resp.status === 403) {
    throw new BinanceProxyError("Token del proxy rechazado. Verifica la configuración.");
  }
  if (resp.status === 429) {
    throw new BinanceProxyError("Rate limit del proxy excedido. Intenta en un momento.");
  }
  if (resp.status === 502) {
    throw new BinanceProxyError("El proxy no pudo conectar con Binance. Intenta de nuevo.");
  }

  const data = await resp.json();

  // Check for Binance error in response
  if (data && typeof data === "object" && "code" in data && "msg" in data) {
    const code = (data as any).code;
    const msg = (data as any).msg;
    if (code === -2015) {
      throw new BinanceProxyError(
        `Binance rechazó las credenciales (-2015). Verifica que la IP del proxy (${getProxyUrl().replace("http://", "").replace(":9100", "")}) esté en tu whitelist de Binance API Management.`,
        code
      );
    }
    throw new BinanceProxyError(`Binance API error ${code}: ${msg}`, code);
  }

  return data;
}

// ─── High-level API functions ───────────────────────────────────────────────

export async function getAccount(): Promise<any> {
  return binanceRequest("GET", "/api/v3/account");
}

export async function getOpenOrders(symbol?: string): Promise<any[]> {
  const params: Record<string, string> = {};
  if (symbol) params.symbol = symbol;
  return binanceRequest("GET", "/api/v3/openOrders", params);
}

export async function getAllOrders(symbol: string, limit: number = 50): Promise<any[]> {
  return binanceRequest("GET", "/api/v3/allOrders", { symbol, limit });
}

export async function placeOrder(params: {
  symbol: string;
  side: string;
  type: string;
  quantity?: string;
  quoteOrderQty?: string;
  price?: string;
  timeInForce?: string;
  stopPrice?: string;
}): Promise<any> {
  return binanceRequest("POST", "/api/v3/order", params);
}

export async function placeOCO(params: {
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  stopPrice: string;
  stopLimitPrice: string;
  stopLimitTimeInForce: string;
}): Promise<any> {
  return binanceRequest("POST", "/api/v3/order/oco", params);
}

export async function cancelOCO(symbol: string, orderListId: string): Promise<any> {
  return binanceRequest("DELETE", "/api/v3/orderList", { symbol, orderListId });
}

export async function cancelOrder(symbol: string, orderId: string): Promise<any> {
  return binanceRequest("DELETE", "/api/v3/order", { symbol, orderId });
}

export async function getFuturesPositions(): Promise<any[]> {
  return binanceRequest("GET", "/fapi/v2/positionRisk");
}

export async function getExchangeInfo(symbol: string): Promise<any> {
  return binanceRequest("GET", "/api/v3/exchangeInfo", { symbol }, false);
}

export async function testProxyConnection(): Promise<boolean> {
  try {
    const proxyUrl = getProxyUrl();
    const resp = await fetch(`${proxyUrl}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}
