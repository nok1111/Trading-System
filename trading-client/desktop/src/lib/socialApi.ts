/** Social trading API client — leaders, signals, follow, copy. */

import { api } from "./api";

export interface SocialLeader {
  id: number;
  user_id: number;
  display_name: string;
  bio: string;
  broker_id: string;
  is_public: boolean;
  fee_percent: number;
  min_copy_amount_usd: number;
  total_followers: number;
  roi_30d?: number;
  roi_90d?: number;
  roi_all?: number;
  win_rate?: number;
  total_trades?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
  open_positions?: number;
  created_at?: string;
}

export interface SocialSignal {
  id: number;
  leader_id: number;
  symbol: string;
  side: "BUY" | "SELL" | "CLOSE";
  size_pct: number;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  broker_id: string;
  status: "active" | "closed" | "cancelled";
  close_price: number | null;
  pnl_pct: number;
  comment: string;
  created_at: string;
  closed_at: string | null;
  leader?: {
    id: number;
    display_name: string;
    broker_id: string;
    roi_30d: number;
    win_rate: number;
    total_followers: number;
  };
}

export interface SocialFollow {
  id: number;
  follower_id: number;
  leader_id: number;
  auto_copy: boolean;
  copy_pct: number;
  max_positions: number;
  symbol_filter: string;
  max_drawdown_pct: number;
  active: boolean;
  created_at: string;
}

export interface CopyTrade {
  id: number;
  signal_id: number;
  leader_id: number;
  symbol: string;
  side: string;
  size_usd: number;
  entry_price: number | null;
  broker_id: string;
  broker_order_id: string | null;
  status: "pending" | "executed" | "failed" | "closed";
  pnl: number;
  error: string | null;
  created_at: string;
}

// ─── Leaders ────────────────────────────────────────────────────────────────

export async function getLeaders(sort: string = "roi_30d", limit: number = 50): Promise<SocialLeader[]> {
  return api<SocialLeader[]>(`/api/social/leaders?sort=${sort}&limit=${limit}`);
}

export async function getLeader(leaderId: number): Promise<SocialLeader> {
  return api<SocialLeader>(`/api/social/leaders/${leaderId}`);
}

export async function getLeaderSignals(leaderId: number, status: string = "all"): Promise<SocialSignal[]> {
  return api<SocialSignal[]>(`/api/social/leaders/${leaderId}/signals?status=${status}`);
}

export async function registerLeader(data: {
  display_name: string;
  bio?: string;
  broker_id?: string;
  is_public?: boolean;
}): Promise<SocialLeader> {
  return api<SocialLeader>("/api/social/leader/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ─── Signals ────────────────────────────────────────────────────────────────

export async function getSignalsFeed(status: string = "active", limit: number = 50, offset: number = 0): Promise<{ signals: SocialSignal[]; count: number; offset: number }> {
  return api(`/api/social/signals/feed?status=${status}&limit=${limit}&offset=${offset}`);
}

export async function publishSignal(data: {
  symbol: string;
  side: "BUY" | "SELL" | "CLOSE";
  size_pct?: number;
  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;
  comment?: string;
}): Promise<SocialSignal> {
  return api<SocialSignal>("/api/social/signals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function closeSignal(signalId: number, closePrice?: number): Promise<SocialSignal> {
  return api<SocialSignal>(`/api/social/signals/${signalId}/close${closePrice ? `?close_price=${closePrice}` : ""}`, {
    method: "POST",
  });
}

// ─── Follow ─────────────────────────────────────────────────────────────────

export async function followLeader(data: {
  leader_id: number;
  auto_copy?: boolean;
  copy_pct?: number;
  max_positions?: number;
  symbol_filter?: string;
  max_drawdown_pct?: number;
}): Promise<SocialFollow> {
  return api<SocialFollow>("/api/social/follow", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function unfollowLeader(followId: number): Promise<{ ok: boolean }> {
  return api(`/api/social/follow/${followId}`, { method: "DELETE" });
}

export async function updateFollow(followId: number, data: {
  auto_copy?: boolean;
  copy_pct?: number;
  max_positions?: number;
  symbol_filter?: string;
  max_drawdown_pct?: number;
  active?: boolean;
}): Promise<SocialFollow> {
  return api<SocialFollow>(`/api/social/follow/${followId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getMyFollows(): Promise<SocialFollow[]> {
  return api<SocialFollow[]>("/api/social/my-follows");
}

// ─── Copy ───────────────────────────────────────────────────────────────────

export async function copySignal(signalId: number, data: {
  broker_id: string;
  size_usd?: number;
}): Promise<{
  ok: boolean;
  copy_trade_id: number;
  broker: string;
  symbol: string;
  side: string;
  size_usd: number;
  quantity: number;
  entry_price: number;
  broker_order_id: string | null;
}> {
  return api(`/api/social/signals/${signalId}/copy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getMyCopyTrades(): Promise<CopyTrade[]> {
  return api<CopyTrade[]>("/api/social/my-copy-trades");
}

export async function getMyLeaderProfile(): Promise<SocialLeader | null> {
  return api<SocialLeader | null>("/api/social/my-leader-profile");
}

export async function getSchedulerStatus(): Promise<{
  running: boolean;
  copy_interval?: number;
  stats_interval?: number;
  last_copy_run?: string;
  last_stats_run?: string;
  copies_executed?: number;
  copies_failed?: number;
  stats_updated?: number;
  errors?: number;
}> {
  return api("/api/social/scheduler/status");
}
