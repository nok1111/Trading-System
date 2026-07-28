export const FEATURES = {
  // Intelligence — now served from local backend (free public APIs)
  marketOverview: true,
  fearGreed: true,
  btcDominance: true,
  news: true,
  macroEvents: true,
  whaleActivity: true,
  dailyReport: true,
  signals: true,
  alerts: true,
  agents: true,
  scenarios: true,
  scheduler: true,
  portfolioMatch: true,
  reports: true,
  pending: true,
  // Brokers
  brokerManagement: true,
  multiBroker: false,
  multipleAccountsPerBroker: false,
  // Trading
  futureScenarios: false,
  automaticTrading: false,
} as const;

export type FeatureFlag = keyof typeof FEATURES;

export function isFeatureEnabled(flag: FeatureFlag): boolean {
  return FEATURES[flag] === true;
}
