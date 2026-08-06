/**
 * Generic broker API client.
 *
 * Two sections:
 * 1. Account management (getSupportedBrokers, connect, disconnect, etc.)
 * 2. Broker data operations (balance, orders, positions, ticker, etc.)
 *
 * The data operations route through /api/broker/{brokerId}/* endpoints,
 * which use the broker registry to resolve the correct adapter
 * (BinanceAdapter for binance, CCXTAdapter for all others).
 */

import { api } from "./api";
import { isFeatureEnabled } from "./featureFlags";
import type {
  SupportedBroker,
  BrokerAccount,
  CredentialValidationRequest,
  CredentialValidationResponse,
  CreateBrokerAccountRequest,
} from "./brokerTypes";
import { MOCK_SUPPORTED_BROKERS, MOCK_CONNECTED_ACCOUNTS } from "./brokerMocks";

// ─── Account management ──────────────────────────────────────────────────────

export async function getSupportedBrokers(): Promise<SupportedBroker[]> {
  if (!isFeatureEnabled("brokerManagement")) {
    return MOCK_SUPPORTED_BROKERS;
  }
  try {
    return await api<SupportedBroker[]>("/api/brokers");
  } catch {
    return MOCK_SUPPORTED_BROKERS;
  }
}

export async function getConnectedAccounts(): Promise<BrokerAccount[]> {
  if (!isFeatureEnabled("brokerManagement")) {
    return MOCK_CONNECTED_ACCOUNTS;
  }
  try {
    return await api<BrokerAccount[]>("/api/broker-accounts");
  } catch {
    return MOCK_CONNECTED_ACCOUNTS;
  }
}

export async function validateCredentials(
  req: CredentialValidationRequest
): Promise<CredentialValidationResponse> {
  return api<CredentialValidationResponse>(
    "/api/broker-accounts/validate",
    { method: "POST", body: JSON.stringify(req) }
  );
}

export async function createBrokerAccount(
  req: CreateBrokerAccountRequest
): Promise<BrokerAccount> {
  return api<BrokerAccount>("/api/broker-accounts", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getBrokerAccount(id: string): Promise<BrokerAccount> {
  return api<BrokerAccount>(`/api/broker-accounts/${id}`);
}

export async function updateBrokerAccount(
  id: string,
  updates: { displayName?: string; environment?: string }
): Promise<BrokerAccount> {
  return api<BrokerAccount>(`/api/broker-accounts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function deleteBrokerAccount(id: string): Promise<void> {
  await api(`/api/broker-accounts/${id}`, { method: "DELETE" });
}

export async function syncBrokerAccount(id: string): Promise<BrokerAccount> {
  return api<BrokerAccount>(`/api/broker-accounts/${id}/sync`, {
    method: "POST",
  });
}

export async function revokeBrokerAccount(id: string): Promise<BrokerAccount> {
  return api<BrokerAccount>(`/api/broker-accounts/${id}/revoke`, {
    method: "POST",
  });
}

// ─── Broker data types ───────────────────────────────────────────────────────

export interface BrokerBalance {
  asset: string;
  free: number;
  locked: number;
  total: number;
  usd_value?: number;
}

export interface BrokerBalanceResponse {
  assets: BrokerBalance[];
  total_usd: number;
  total_mxn: number;
  mxn_rate: number;
  testnet: boolean;
  usdt_free: number;
  usdt_total: number;
  error?: string;
}

export interface BrokerOrder {
  orderId: string;
  clientOrderId: string;
  symbol: string;
  side: string;
  type: string;
  status: string;
  is_active: boolean;
  quantity: number;
  filled_quantity: number;
  price: number | null;
  avg_price: number | null;
  stop_price?: number | null;
  time: number;
  updateTime: number;
}

export interface BrokerOrdersResponse {
  orders: BrokerOrder[];
  active: BrokerOrder[];
  filled: BrokerOrder[];
  count: number;
  active_count?: number;
  error?: string;
}

export interface BrokerPosition {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  unrealized_pnl: number;
  stop_loss: number | null;
  take_profit: number | null;
  status: string;
  strategy_name: string;
  opened_at: string | null;
}

export interface BrokerPositionsResponse {
  positions: BrokerPosition[];
  count: number;
  error?: string;
}

export interface BrokerTicker {
  symbol: string;
  price: number;
  bid: number | null;
  ask: number | null;
  volume_24h: number | null;
}

export interface BrokerMarketInfo {
  symbol: string;
  broker_symbol: string;
  base_asset: string;
  quote_asset: string;
  min_quantity: number | null;
  max_quantity: number | null;
  step_size: number | null;
  min_notional: number | null;
  price_precision: number | null;
  quantity_precision: number | null;
  status: string;
}

export interface BrokerKline {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BrokerMover {
  symbol: string;
  price: number;
  price_change_percent: number;
  volume: number;
}

export interface BrokerMoversResponse {
  gainers: BrokerMover[];
  losers: BrokerMover[];
}

export interface PlaceOrderParams {
  symbol: string;
  side: "buy" | "sell";
  order_type: "market" | "limit";
  quantity?: number;
  quote_order_qty?: number;
  price?: number;
  stop_loss_price?: number;
  take_profit_price?: number;
}

export interface PlaceOrderResponse {
  status: string;
  orderId?: string;
  symbol?: string;
  side?: string;
  type?: string;
  quantity?: number;
  price?: number | null;
  executedQty?: number;
  orderStatus?: string;
  error?: string;
  stopLoss?: number;
  takeProfit?: number;
}

export interface CancelOrderParams {
  broker_order_id?: string;
  client_order_id?: string;
  symbol?: string;
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getBalance(brokerId: string): Promise<BrokerBalanceResponse> {
  return api<BrokerBalanceResponse>(`/api/broker/${brokerId}/balance`);
}

export async function getPortfolio(brokerId: string): Promise<BrokerBalanceResponse> {
  return api<BrokerBalanceResponse>(`/api/broker/${brokerId}/portfolio`);
}

export async function getOrders(
  brokerId: string,
  opts?: { symbol?: string; limit?: number; status?: "open" | "filled" | "all" }
): Promise<BrokerOrdersResponse> {
  const params = new URLSearchParams();
  if (opts?.symbol) params.set("symbol", opts.symbol);
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.status) params.set("status", opts.status);
  const qs = params.toString();
  return api<BrokerOrdersResponse>(`/api/broker/${brokerId}/orders${qs ? `?${qs}` : ""}`);
}

export async function getPositions(brokerId: string): Promise<BrokerPositionsResponse> {
  return api<BrokerPositionsResponse>(`/api/broker/${brokerId}/positions`);
}

export async function getTicker(brokerId: string, symbol: string): Promise<BrokerTicker> {
  return api<BrokerTicker>(`/api/broker/${brokerId}/ticker?symbol=${encodeURIComponent(symbol)}`);
}

export async function getMarketInfo(brokerId: string, symbol: string): Promise<BrokerMarketInfo> {
  return api<BrokerMarketInfo>(`/api/broker/${brokerId}/market-info?symbol=${encodeURIComponent(symbol)}`);
}

export async function getKlines(
  brokerId: string,
  symbol: string,
  interval: string = "1m",
  limit: number = 200
): Promise<BrokerKline[]> {
  return api<BrokerKline[]>(
    `/api/broker/${brokerId}/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`
  );
}

export async function getMovers(
  brokerId: string,
  opts?: { market?: string; limit?: number; quote?: string }
): Promise<BrokerMoversResponse> {
  const params = new URLSearchParams();
  if (opts?.market) params.set("market", opts.market);
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.quote) params.set("quote", opts.quote);
  const qs = params.toString();
  return api<BrokerMoversResponse>(`/api/broker/${brokerId}/movers${qs ? `?${qs}` : ""}`);
}

export interface BrokerSymbol {
  symbol: string;
  base: string;
  quote: string;
  price: number;
  change_24h_pct: number;
  volume: number;
}

export async function getTopSymbols(
  brokerId: string,
  opts?: { quote?: string; limit?: number }
): Promise<BrokerSymbol[]> {
  const params = new URLSearchParams();
  if (opts?.quote) params.set("quote", opts.quote);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  try {
    return await api<BrokerSymbol[]>(`/api/broker/${brokerId}/symbols${qs ? `?${qs}` : ""}`);
  } catch {
    return [];
  }
}

export async function placeOrder(brokerId: string, params: PlaceOrderParams): Promise<PlaceOrderResponse> {
  return api<PlaceOrderResponse>(`/api/broker/${brokerId}/order`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface PlaceOcoParams {
  symbol: string;
  side?: string;
  quantity: number;
  take_profit_price: number;
  stop_loss_price: number;
}

export interface PlaceOcoResponse {
  status: string;
  oco_order_id?: string;
  sl_order_id?: string;
  tp_order_id?: string;
  symbol?: string;
  stop_loss?: number;
  take_profit?: number;
  error?: string;
}

export async function placeOcoOrder(brokerId: string, params: PlaceOcoParams): Promise<PlaceOcoResponse> {
  return api<PlaceOcoResponse>(`/api/broker/${brokerId}/oco`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function cancelOrder(brokerId: string, params: CancelOrderParams): Promise<{ status: string; orderId?: string; error?: string }> {
  return api(`/api/broker/${brokerId}/order`, {
    method: "DELETE",
    body: JSON.stringify(params),
  });
}

// ─── Sync Positions ──────────────────────────────────────────────────────────

export interface SyncPositionsResponse {
  status: string;
  broker_id?: string;
  total_positions?: number;
  closed?: number;
  updated?: number;
  unchanged?: number;
  details?: string[];
  error?: string;
}

export async function syncPositions(brokerId: string): Promise<SyncPositionsResponse> {
  return api<SyncPositionsResponse>(`/api/broker/${brokerId}/sync-positions`, {
    method: "POST",
  });
}
