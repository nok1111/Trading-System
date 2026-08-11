import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type {
  SupportedBroker,
  BrokerAccount,
  BrokerStoreState,
  CredentialValidationRequest,
  CredentialValidationResponse,
  CreateBrokerAccountRequest,
} from "../lib/brokerTypes";
import {
  getSupportedBrokers,
  getConnectedAccounts,
  validateCredentials,
  createBrokerAccount,
  deleteBrokerAccount,
  syncBrokerAccount,
  revokeBrokerAccount,
} from "../lib/brokerApi";

interface BrokerContextValue extends BrokerStoreState {
  refresh: () => Promise<void>;
  validate: (req: CredentialValidationRequest) => Promise<CredentialValidationResponse>;
  connect: (req: CreateBrokerAccountRequest) => Promise<BrokerAccount>;
  disconnect: (id: string) => Promise<void>;
  sync: (id: string) => Promise<BrokerAccount>;
  revoke: (id: string) => Promise<BrokerAccount>;
  selectAccount: (id: string | null) => void;
  hasConnectedAccounts: boolean;
}

const BrokerContext = createContext<BrokerContextValue | null>(null);

export function BrokerProvider({ children }: { children: ReactNode }) {
  const [supportedBrokers, setSupportedBrokers] = useState<SupportedBroker[]>([]);
  const [connectedAccounts, setConnectedAccounts] = useState<BrokerAccount[]>([]);
  const [selectedBrokerAccountId, setSelectedBrokerAccountId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [brokers, accounts] = await Promise.all([
        getSupportedBrokers(),
        getConnectedAccounts(),
      ]);
      setSupportedBrokers(brokers);
      setConnectedAccounts(accounts);
      setLastUpdated(new Date().toISOString());
      if (accounts.length > 0 && !selectedBrokerAccountId) {
        setSelectedBrokerAccountId(accounts[0].id);
      }
      if (accounts.length === 0) {
        setSelectedBrokerAccountId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading brokers");
    } finally {
      setIsLoading(false);
    }
  }, [selectedBrokerAccountId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const validate = useCallback(
    async (req: CredentialValidationRequest): Promise<CredentialValidationResponse> => {
      return validateCredentials(req);
    },
    []
  );

  const connect = useCallback(
    async (req: CreateBrokerAccountRequest): Promise<BrokerAccount> => {
      console.log("[BrokerContext] connect called", req.brokerId);
      const account = await createBrokerAccount(req);
      console.log("[BrokerContext] createBrokerAccount succeeded:", account);
      await refresh();
      console.log("[BrokerContext] refresh done, connectedAccounts:", connectedAccounts.length);
      return account;
    },
    [refresh, connectedAccounts.length]
  );

  const disconnect = useCallback(
    async (id: string): Promise<void> => {
      await deleteBrokerAccount(id);
      if (selectedBrokerAccountId === id) {
        setSelectedBrokerAccountId(null);
      }
      await refresh();
    },
    [refresh, selectedBrokerAccountId]
  );

  const sync = useCallback(
    async (id: string): Promise<BrokerAccount> => {
      const account = await syncBrokerAccount(id);
      await refresh();
      return account;
    },
    [refresh]
  );

  const revoke = useCallback(
    async (id: string): Promise<BrokerAccount> => {
      const account = await revokeBrokerAccount(id);
      await refresh();
      return account;
    },
    [refresh]
  );

  const selectAccount = useCallback((id: string | null) => {
    setSelectedBrokerAccountId(id);
  }, []);

  const hasConnectedAccounts = connectedAccounts.length > 0;

  const value: BrokerContextValue = {
    supportedBrokers,
    connectedAccounts,
    selectedBrokerAccountId,
    isLoading,
    error,
    lastUpdated,
    refresh,
    validate,
    connect,
    disconnect,
    sync,
    revoke,
    selectAccount,
    hasConnectedAccounts,
  };

  return <BrokerContext.Provider value={value}>{children}</BrokerContext.Provider>;
}

export function useBrokerContext() {
  const ctx = useContext(BrokerContext);
  if (!ctx) throw new Error("useBrokerContext must be used within BrokerProvider");
  return ctx;
}
