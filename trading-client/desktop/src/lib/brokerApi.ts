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
