export interface MarketOverview {
  regime: string;
  riskLevel: "low" | "medium" | "high";
  riskOnOff: "risk_on" | "risk_off";
  capitalFlows?: { from: string; to: string; amount: number }[];
  summary: string;
  timestamp: string;
}

export interface FearGreedData {
  value: number;
  classification: string;
  previousValue: number;
  previousClassification: string;
  history: { timestamp: string; value: number }[];
  timestamp: string;
}

export interface DominanceData {
  btc: number;
  eth: number;
  others: number;
  history: { timestamp: string; btc: number; eth: number; others: number }[];
  timestamp: string;
}

export interface NewsItem {
  id: string;
  title: string;
  source: string;
  url: string;
  timestamp: string;
  sentiment: "positive" | "neutral" | "negative";
  assets: string[];
  impact: "high" | "medium" | "low";
  summary: string;
}

export interface MacroEvent {
  id: string;
  event: string;
  date: string;
  country: string;
  impact: "high" | "medium" | "low";
  actual: string | null;
  forecast: string | null;
  previous: string | null;
}

export interface WhaleActivity {
  id: string;
  asset: string;
  amount: number;
  amountUsd: number;
  direction: "inflow" | "outflow";
  fromAddress: string;
  toAddress: string;
  timestamp: string;
  exchange: string | null;
}

export interface DailyReport {
  date: string;
  summary: string;
  sections: {
    marketOverview: string;
    keyEvents: string;
    performance: string;
    outlook: string;
  };
  timestamp: string;
}

export interface SignalTarget {
  price: number;
  probability: number;
}

export interface SignalEntryZone {
  min: number;
  max: number;
}

export interface SignalInvalidation {
  type: string;
  value: number;
}

export interface AgentVote {
  agentId: string;
  agentName: string;
  vote: "BUY" | "HOLD" | "SELL";
  confidence: number;
}

export interface IntelligenceSignal {
  id: string;
  asset: string;
  decision: "BUY" | "HOLD" | "SELL";
  confidence: number;
  riskLevel: "low" | "medium" | "high";
  entryZone: SignalEntryZone;
  targets: SignalTarget[];
  invalidation: SignalInvalidation;
  agentVotes: AgentVote[];
  mainReasons: string[];
  mainRisks: string[];
  validFrom: string;
  expiresAt: string | null;
  requiresConfirmation: boolean;
  status: "ACTIVE" | "SUPERSEDED" | "EXPIRED" | "INVALIDATED" | "CANCELLED";
  consensusData?: Record<string, unknown>;
  timestamp: string;
}

export interface IntelligenceAlert {
  id: string;
  asset: string;
  alertType: string;
  severity: "low" | "medium" | "high";
  message: string;
  details: string | null;
  timestamp: string;
  expiresAt: string | null;
  crashRisk?: number;
}

export interface AgentInfo {
  agentId: string;
  agentName: string;
  role: string;
  interval: string;
  lastRun: string | null;
  status: "running" | "idle" | "error";
  provider: string | null;
  model: string | null;
  isOptional: boolean;
}

export interface Scenario {
  asset: string;
  bullish: { target: number; probability: number };
  base: { target: number; probability: number };
  bearish: { target: number; probability: number };
  supports: number[];
  resistances: number[];
  timestamp: string;
}

export interface SchedulerStatus {
  running: boolean;
  symbols: string[];
  interval: string;
  lastRun: string | null;
  nextRun: string | null;
}

export interface PortfolioMatchRequest {
  signalId: string;
  asset: string;
  decision: string;
  entryZone: SignalEntryZone;
  targets: SignalTarget[];
  riskLevel: string;
  riskProfile: string;
  brokerAccountId?: string;
  currentPositions?: { asset: string; quantity: number; entryPrice: number }[];
  totalEquity?: number;
}

export interface Recommendation {
  signalId: string;
  asset: string;
  action: string;
  reason: string;
  confidence: number;
  amountChange?: number;
  targetAllocation?: number;
}

export interface IntelligenceReport {
  id: string;
  date: string;
  type: "daily" | "weekly" | "monthly";
  asset: string;
  summary: string;
  sections: {
    marketOverview: string;
    keyEvents: string;
    performance: string;
    outlook: string;
  };
}

export interface PendingNotification {
  id: number;
  type: string;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export interface ChangeItem {
  id: string;
  type: "new_opportunity" | "invalidated" | "consensus_change" | "institutional_flow" | "risk_change" | "portfolio_change" | "macro_event" | "news_high_impact";
  icon: string;
  color: "green" | "red" | "yellow" | "blue" | "orange" | "white" | "gray" | "black";
  title: string;
  detail: string;
  timestamp: string;
}

export interface PortfolioSummary {
  totalPnl: number;
  positionsCount: number;
  totalValue: number;
  bestPerformer: { asset: string; pnl: number; pnl_pct: number; symbol: string } | null;
  worstPerformer: { asset: string; pnl: number; pnl_pct: number; symbol: string } | null;
}

export interface MoverItem {
  asset: string;
  decision: string;
  confidence: number;
  price: number | null;
  reason: string;
  target_price: number | null;
}

export interface BuyRecommendation {
  asset: string;
  price: number | null;
  targetPrice: number | null;
  potentialUpside: number | null;
  confidence: number;
  riskLevel: string;
  brokers: string[];
  reason: string;
}

export interface HighImpactNewsItem {
  id: number;
  title: string;
  source: string;
  url: string;
  impact: string;
  sentiment: string;
  assets: string[];
  image_url: string | null;
}

export interface SinceLastVisitData {
  lastLogin: string;
  hoursSinceLogin: number;
  greeting: string;
  changes: ChangeItem[];
  toReview: { asset: string; reason: string }[];
  portfolio?: PortfolioSummary;
  movers?: MoverItem[];
  buyRecommendations?: BuyRecommendation[];
  highImpactNews?: HighImpactNewsItem[];
}

export interface PriorityAsset {
  id: string;
  asset: string;
  recommendation: "BUY" | "HOLD" | "SELL" | "BUY ON PULLBACK" | "WAIT";
  confidence: number;
  risk: "low" | "medium" | "high";
  mainReason: string;
  expiresAt: string | null;
  reasons: { label: string; confirmed: boolean }[];
}

export interface TodayPrioritiesData {
  priorities: PriorityAsset[];
}

export interface AIActivityEntry {
  id: string;
  timestamp: string;
  agent: "Technical" | "News" | "On-chain" | "Contrarian" | "Consensus" | "Macro";
  action: string;
  detail: string;
  decision?: "BUY" | "HOLD" | "SELL";
  confidence?: number;
}

export interface AIActivityData {
  entries: AIActivityEntry[];
}
