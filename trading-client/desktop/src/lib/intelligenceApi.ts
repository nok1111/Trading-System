import { isFeatureEnabled } from "./featureFlags";
import { api } from "./api";
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
  SinceLastVisitData,
  TodayPrioritiesData,
  AIActivityData,
} from "./intelligenceTypes";

export async function getMarketOverview(): Promise<MarketOverview | null> {
  if (!isFeatureEnabled("marketOverview")) return null;
  try {
    return await api<MarketOverview>("/api/intelligence/market-overview");
  } catch {
    return null;
  }
}

export async function getFearGreed(): Promise<FearGreedData | null> {
  if (!isFeatureEnabled("fearGreed")) return null;
  try {
    return await api<FearGreedData>("/api/intelligence/fear-greed");
  } catch {
    return null;
  }
}

export async function getDominance(): Promise<DominanceData | null> {
  if (!isFeatureEnabled("btcDominance")) return null;
  try {
    return await api<DominanceData>("/api/intelligence/dominance");
  } catch {
    return null;
  }
}

export async function getNews(limit?: number): Promise<NewsItem[]> {
  try {
    const qs = limit ? `?limit=${limit}` : "";
    const data = await api<{ news: any[]; count: number }>(`/api/intelligence/news${qs}`);
    if (!data.news) return [];
    return data.news.map((n) => ({
      id: String(n.id),
      title: n.title || "",
      source: n.source || "unknown",
      url: n.url || "",
      timestamp: n.published_at || n.fetched_at || "",
      sentiment: n.sentiment === "bullish" ? "positive" : n.sentiment === "bearish" ? "negative" : "neutral",
      assets: n.affected_assets || [],
      impact: (["critical", "high"].includes(n.impact) ? "high" : n.impact === "medium" ? "medium" : "low") as "high" | "medium" | "low",
      summary: n.summary || n.ai_analysis || "",
    }));
  } catch {
    return [];
  }
}

export async function getMacroEvents(): Promise<MacroEvent[]> {
  if (!isFeatureEnabled("macroEvents")) return [];
  try {
    return await api<MacroEvent[]>("/api/intelligence/macro-events");
  } catch {
    return [];
  }
}

export async function getWhaleActivity(limit?: number): Promise<WhaleActivity[]> {
  if (!isFeatureEnabled("whaleActivity")) return [];
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await api<WhaleActivity[]>(`/api/intelligence/whale-activity${qs}`);
  } catch {
    return [];
  }
}

export async function getDailyReport(): Promise<DailyReport | null> {
  if (!isFeatureEnabled("dailyReport")) return null;
  try {
    return await api<DailyReport>("/api/intelligence/daily-report");
  } catch {
    return null;
  }
}

export async function getSignals(limit?: number): Promise<IntelligenceSignal[]> {
  if (!isFeatureEnabled("signals")) return [];
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await api<IntelligenceSignal[]>(`/api/intelligence/signals${qs}`);
  } catch {
    return [];
  }
}

export async function getAlerts(limit?: number): Promise<IntelligenceAlert[]> {
  if (!isFeatureEnabled("alerts")) return [];
  try {
    const qs = limit ? `?limit=${limit}` : "";
    return await api<IntelligenceAlert[]>(`/api/intelligence/alerts${qs}`);
  } catch {
    return [];
  }
}

export async function getAgents(): Promise<AgentInfo[]> {
  if (!isFeatureEnabled("agents")) return [];
  try {
    return await api<AgentInfo[]>("/api/intelligence/agents");
  } catch {
    return [];
  }
}

export async function getScenarios(asset: string): Promise<Scenario[]> {
  if (!isFeatureEnabled("scenarios")) return [];
  try {
    return await api<Scenario[]>(`/api/intelligence/scenarios/${asset}`);
  } catch {
    return [];
  }
}

export async function getSchedulerStatus(): Promise<SchedulerStatus | null> {
  if (!isFeatureEnabled("scheduler")) return null;
  try {
    return await api<SchedulerStatus>("/api/intelligence/scheduler/status");
  } catch {
    return null;
  }
}

export async function startScheduler(): Promise<void> {
  if (!isFeatureEnabled("scheduler")) return;
  await api("/api/intelligence/scheduler/start", { method: "POST" });
}

export async function stopScheduler(): Promise<void> {
  if (!isFeatureEnabled("scheduler")) return;
  await api("/api/intelligence/scheduler/stop", { method: "POST" });
}

export async function getNotifications(
  unreadOnly: boolean = false,
  limit: number = 50
): Promise<PendingNotification[]> {
  try {
    const resp = await api<{ notifications: PendingNotification[]; count: number }>(
      `/api/notifications?unread_only=${unreadOnly}&limit=${limit}`
    );
    return resp.notifications || [];
  } catch {
    return [];
  }
}

export async function getUnreadNotificationCount(): Promise<number> {
  try {
    const resp = await api<{ count: number }>("/api/notifications/unread-count");
    return resp.count || 0;
  } catch {
    return 0;
  }
}

export async function markNotificationRead(id: number): Promise<void> {
  try {
    await api(`/api/notifications/${id}/read`, { method: "POST" });
  } catch {}
}

export async function markAllNotificationsRead(): Promise<void> {
  try {
    await api("/api/notifications/read-all", { method: "POST" });
  } catch {}
}

export async function portfolioMatch(
  req: PortfolioMatchRequest
): Promise<Recommendation | null> {
  if (!isFeatureEnabled("portfolioMatch")) return null;
  try {
    return await api<Recommendation>(
      "/api/intelligence/portfolio-match",
      { method: "POST", body: JSON.stringify(req) }
    );
  } catch {
    return null;
  }
}

export async function getReports(asset: string): Promise<IntelligenceReport[]> {
  if (!isFeatureEnabled("reports")) return [];
  try {
    return await api<IntelligenceReport[]>(
      `/api/intelligence/reports/${asset}`
    );
  } catch {
    return [];
  }
}

export async function getSinceLastVisit(): Promise<SinceLastVisitData | null> {
  try {
    const data = await api<SinceLastVisitData>("/api/intelligence/changes-since-last-login");
    if (!data || (data as any).error) return null;
    return data;
  } catch {
    return null;
  }
}

export async function getTodayPriorities(): Promise<TodayPrioritiesData | null> {
  try {
    const data = await api<TodayPrioritiesData>("/api/intelligence/today-priorities");
    if (!data || (data as any).error) return null;
    return data;
  } catch {
    return null;
  }
}

export async function getAIActivity(): Promise<AIActivityData | null> {
  try {
    const data = await api<AIActivityData>("/api/intelligence/activity");
    if (!data || (data as any).error) return null;
    return data;
  } catch {
    return null;
  }
}

export interface UserProfileData {
  onboarding_completed: boolean;
  experience_level: string | null;
  risk_tolerance: string | null;
  asset_interests: string[];
  capital_range: string | null;
  preferred_strategies: string[];
  trading_goal: string | null;
  preferred_language: string;
}

export async function getUserProfile(): Promise<UserProfileData | null> {
  try {
    const data = await api<UserProfileData>("/api/intelligence/profile");
    if (!data || (data as any).error) return null;
    return data;
  } catch {
    return null;
  }
}

export async function saveUserProfile(payload: {
  experience_level: string;
  risk_tolerance: string;
  asset_interests: string[];
  capital_range: string;
  preferred_strategies: string[];
  trading_goal: string;
  preferred_language: string;
}): Promise<UserProfileData | null> {
  try {
    const data = await api<UserProfileData>("/api/intelligence/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return data;
  } catch {
    return null;
  }
}
