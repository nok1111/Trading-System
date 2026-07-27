export const FEATURES = {
  // Intelligence — AI Server endpoints
  marketOverview: false,
  fearGreed: false,
  btcDominance: false,
  news: false,
  macroEvents: false,
  whaleActivity: false,
  dailyReport: false,
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
