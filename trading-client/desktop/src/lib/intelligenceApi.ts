import { isFeatureEnabled } from "./featureFlags";
import type {
  MarketOverview,
  FearGreedData,
  DominanceData,
  NewsItem,
  MacroEvent,
  WhaleActivity,
  DailyReport,
  IntelligenceSignal,
  IntelligenceAlert,
  AgentInfo,
  Scenario,
  SchedulerStatus,
  PortfolioMatchRequest,
  Recommendation,
  IntelligenceReport,
  PendingNotification,
} from "./intelligenceTypes";
import {
  MOCK_MARKET_OVERVIEW,
  MOCK_FEAR_GREED,
  MOCK_DOMINANCE,
  MOCK_NEWS,
  MOCK_MACRO_EVENTS,
  MOCK_WHALE_ACTIVITY,
  MOCK_DAILY_REPORT,
} from "./intelligenceMocks";

function getAiServerUrl(): string {
  return localStorage.getItem("aiServerUrl") || "http://localhost:8000";
}

async function aiServerFetch<T>(
  path: string,
  opts: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  };
  const token = localStorage.getItem("jwt");
  if (token) headers["Authorization"] = "Bearer " + token;
  if (opts.body && !headers["Content-Type"])
    headers["Content-Type"] = "application/json";

  const r = await fetch(getAiServerUrl() + path, { ...opts, headers });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "Error" }));
    throw new Error(e.detail || "AI Server error");
  }
  return r.json();
}

export async function getMarketOverview(): Promise<MarketOverview | null> {
  if (!isFeatureEnabled("marketOverview")) return MOCK_MARKET_OVERVIEW;
  try {
    return await aiServerFetch<MarketOverview>("/v1/intelligence/market-overview");
  } catch {
    return null;
  }
}

export async function getFearGreed(): Promise<FearGreedData | null> {
  if (!isFeatureEnabled("fearGreed")) return MOCK_FEAR_GREED;
  try {
    return await aiServerFetch<FearGreedData>("/v1/intelligence/fear-greed");
  } catch {
    return null;
  }
}

export async function getDominance(): Promise<DominanceData | null> {
  if (!isFeatureEnabled("btcDominance")) return MOCK_DOMINANCE;
  try {
    return await aiServerFetch<DominanceData>("/v1/intelligence/dominance");
  } catch {
    return null;
  }
}

export async function getNews(limit?: number): Promise<NewsItem[]> {
  if (!isFeatureEnabled("news")) return MOCK_NEWS.slice(0, limit ?? 5);
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await aiServerFetch<NewsItem[]>(`/v1/intelligence/news${qs}`);
  } catch {
    return [];
  }
}

export async function getMacroEvents(): Promise<MacroEvent[]> {
  if (!isFeatureEnabled("macroEvents")) return MOCK_MACRO_EVENTS;
  try {
    return await aiServerFetch<MacroEvent[]>("/v1/intelligence/macro-events");
  } catch {
    return [];
  }
}

export async function getWhaleActivity(limit?: number): Promise<WhaleActivity[]> {
  if (!isFeatureEnabled("whaleActivity")) return MOCK_WHALE_ACTIVITY.slice(0, limit ?? 10);
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await aiServerFetch<WhaleActivity[]>(`/v1/intelligence/whale-activity${qs}`);
  } catch {
    return [];
  }
}

export async function getDailyReport(): Promise<DailyReport | null> {
  if (!isFeatureEnabled("dailyReport")) return MOCK_DAILY_REPORT;
  try {
    return await aiServerFetch<DailyReport>("/v1/intelligence/daily-report");
  } catch {
    return null;
  }
}

export async function getSignals(limit?: number): Promise<IntelligenceSignal[]> {
  if (!isFeatureEnabled("signals")) return [];
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await aiServerFetch<IntelligenceSignal[]>(`/v1/intelligence/signals${qs}`);
  } catch {
    return [];
  }
}

export async function getAlerts(limit?: number): Promise<IntelligenceAlert[]> {
  if (!isFeatureEnabled("alerts")) return [];
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await aiServerFetch<IntelligenceAlert[]>(`/v1/intelligence/alerts${qs}`);
  } catch {
    return [];
  }
}

export async function getAgents(): Promise<AgentInfo[]> {
  if (!isFeatureEnabled("agents")) return [];
  try {
    return await aiServerFetch<AgentInfo[]>("/v1/intelligence/agents");
  } catch {
    return [];
  }
}

export async function getScenarios(asset: string): Promise<Scenario[]> {
  if (!isFeatureEnabled("scenarios")) return [];
  try {
    return await aiServerFetch<Scenario[]>(`/v1/intelligence/scenarios/${asset}`);
  } catch {
    return [];
  }
}

export async function getSchedulerStatus(): Promise<SchedulerStatus | null> {
  if (!isFeatureEnabled("scheduler")) return null;
  try {
    return await aiServerFetch<SchedulerStatus>("/v1/intelligence/scheduler/status");
  } catch {
    return null;
  }
}

export async function startScheduler(): Promise<void> {
  if (!isFeatureEnabled("scheduler")) return;
  await aiServerFetch("/v1/intelligence/scheduler/start", { method: "POST" });
}

export async function stopScheduler(): Promise<void> {
  if (!isFeatureEnabled("scheduler")) return;
  await aiServerFetch("/v1/intelligence/scheduler/stop", { method: "POST" });
}

export async function getPendingNotifications(
  userHash: string
): Promise<PendingNotification[]> {
  if (!isFeatureEnabled("pending")) return [];
  try {
    return await aiServerFetch<PendingNotification[]>(
      `/v1/intelligence/pending?user_hash=${userHash}`
    );
  } catch {
    return [];
  }
}

export async function markNotificationRead(
  id: number,
  userHash: string
): Promise<void> {
  if (!isFeatureEnabled("pending")) return;
  await aiServerFetch(`/v1/intelligence/pending/${id}/read`, {
    method: "POST",
    body: JSON.stringify({ user_hash: userHash }),
  });
}

export async function portfolioMatch(
  req: PortfolioMatchRequest
): Promise<Recommendation | null> {
  if (!isFeatureEnabled("portfolioMatch")) return null;
  try {
    return await aiServerFetch<Recommendation>(
      "/v1/intelligence/portfolio-match",
      { method: "POST", body: JSON.stringify(req) }
    );
  } catch {
    return null;
  }
}

export async function getReports(asset: string): Promise<IntelligenceReport[]> {
  if (!isFeatureEnabled("reports")) return [];
  try {
    return await aiServerFetch<IntelligenceReport[]>(
      `/v1/intelligence/reports/${asset}`
    );
  } catch {
    return [];
  }
}

export { getAiServerUrl };
