export type MarketType = "spot" | "margin" | "futures";

export type BrokerEnvironment = "sandbox" | "testnet" | "live";

export type BrokerConnectionState =
  | "CONNECTED_READ_ONLY"
  | "CONNECTED_TRADING"
  | "DEGRADED"
  | "DISCONNECTED"
  | "REVOKED"
  | "SECURITY_BLOCKED"
  | "NOT_CONNECTED";

export interface BrokerCapabilityFlags {
  spot: boolean;
  margin: boolean;
  futures: boolean;
  staking: boolean;
  earn: boolean;
  websocket: boolean;
  marketOrders: boolean;
  limitOrders: boolean;
  stopOrders: boolean;
  withdrawals: boolean;
}

export interface SupportedBroker {
  brokerId: string;
  displayName: string;
  logoUrl: string | null;
  websiteUrl: string | null;
  apiDocsUrl: string | null;
  supportedMarkets: MarketType[];
  capabilities: BrokerCapabilityFlags;
  requiresPassphrase: boolean;
  environments: BrokerEnvironment[];
  implemented: boolean;
}

export interface BrokerAccountPermissions {
  read: boolean;
  trade: boolean;
  withdraw: boolean;
}

export interface BrokerAccount {
  id: string;
  brokerId: string;
  displayName: string;
  status: BrokerConnectionState;
  permissions: BrokerAccountPermissions;
  environment: BrokerEnvironment;
  lastSyncAt: string | null;
  apiKeyPreview: string;
}

export interface BrokerModuleDef {
  id: string;
  label: string;
  capability: keyof BrokerCapabilityFlags;
  comingSoon?: boolean;
}

export interface CredentialValidationRequest {
  brokerId: string;
  apiKey: string;
  apiSecret: string;
  passphrase?: string;
  environment?: BrokerEnvironment;
}

export interface CredentialValidationResponse {
  valid: boolean;
  status: BrokerConnectionState;
  permissions: BrokerAccountPermissions;
  errorMessage: string | null;
}

export interface CreateBrokerAccountRequest {
  brokerId: string;
  displayName?: string;
  apiKey: string;
  apiSecret: string;
  passphrase?: string;
  environment?: BrokerEnvironment;
}

export interface BrokerStoreState {
  supportedBrokers: SupportedBroker[];
  connectedAccounts: BrokerAccount[];
  selectedBrokerAccountId: string | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: string | null;
}

export const BROKER_MODULE_MAP: BrokerModuleDef[] = [
  { id: "overview", label: "Resumen", capability: "spot" },
  { id: "portfolio", label: "Portafolio", capability: "spot" },
  { id: "trade", label: "Comprar / Vender", capability: "marketOrders" },
  { id: "markets", label: "Mercados", capability: "spot" },
  { id: "positions", label: "Posiciones", capability: "spot" },
  { id: "orders", label: "Órdenes", capability: "marketOrders" },
  { id: "history", label: "Historial", capability: "spot" },
  { id: "earn", label: "Earn", capability: "earn", comingSoon: true },
  { id: "futures", label: "Futures", capability: "futures", comingSoon: true },
  { id: "config", label: "Configuración", capability: "spot" },
];

export function isBrokerConnected(status: BrokerConnectionState): boolean {
  return (
    status === "CONNECTED_READ_ONLY" ||
    status === "CONNECTED_TRADING"
  );
}

export function isBrokerDegraded(status: BrokerConnectionState): boolean {
  return status === "DEGRADED";
}

export function isBrokerLocked(status: BrokerConnectionState): boolean {
  return (
    status === "NOT_CONNECTED" ||
    status === "DISCONNECTED" ||
    status === "REVOKED" ||
    status === "SECURITY_BLOCKED"
  );
}

export function getModulesForBroker(broker: SupportedBroker): BrokerModuleDef[] {
  return BROKER_MODULE_MAP.filter(
    (m) => broker.capabilities[m.capability] === true
  );
}
