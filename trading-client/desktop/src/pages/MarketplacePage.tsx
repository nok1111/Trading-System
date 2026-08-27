import { useEffect, useState, useCallback } from "react";
import { Flame, TrendingUp, Sparkles, FolderOpen, Bookmark, Plus, Search } from "lucide-react";
import { StrategyCard } from "../components/marketplace/StrategyCard";
import { StrategyDetail } from "../components/marketplace/StrategyDetail";
import { PublishStrategyModal } from "../components/marketplace/PublishStrategyModal";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { EmptyState } from "../components/common/EmptyState";
import {
  listStrategies,
  getTrendingStrategies,
  getMyStrategies,
  getMySubscriptions,
  type StrategyListing,
  type StrategyType,
  type PremiumFilter,
} from "../lib/marketplaceApi";
import { cn } from "../lib/utils";

type Tab = "trending" | "best_roi" | "new" | "my_strategies" | "my_subscriptions";

const TABS: { key: Tab; label: string; icon: typeof Flame }[] = [
  { key: "trending", label: "Trending", icon: Flame },
  { key: "best_roi", label: "Best ROI", icon: TrendingUp },
  { key: "new", label: "New", icon: Sparkles },
  { key: "my_strategies", label: "My Strategies", icon: FolderOpen },
  { key: "my_subscriptions", label: "My Subscriptions", icon: Bookmark },
];

const TYPE_FILTERS: { value: StrategyType; label: string }[] = [
  { value: "all", label: "All Types" },
  { value: "grid", label: "Grid" },
  { value: "dca", label: "DCA" },
  { value: "custom", label: "Custom" },
  { value: "ai_generated", label: "AI" },
];

export function MarketplacePage() {
  const [activeTab, setActiveTab] = useState<Tab>("trending");
  const [strategies, setStrategies] = useState<StrategyListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showPublish, setShowPublish] = useState(false);

  // Filters
  const [typeFilter, setTypeFilter] = useState<StrategyType>("all");
  const [premiumFilter, setPremiumFilter] = useState<PremiumFilter>(undefined);
  const [search, setSearch] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === "trending") {
        const data = await getTrendingStrategies(20);
        setStrategies(data);
      } else if (activeTab === "best_roi") {
        const data = await listStrategies({ sort: "roi", type: typeFilter, premium: premiumFilter, search, limit: 30 });
        setStrategies(data.strategies);
      } else if (activeTab === "new") {
        const data = await listStrategies({ sort: "newest", type: typeFilter, premium: premiumFilter, search, limit: 30 });
        setStrategies(data.strategies);
      } else if (activeTab === "my_strategies") {
        const data = await getMyStrategies();
        setStrategies(data);
      } else if (activeTab === "my_subscriptions") {
        const data = await getMySubscriptions();
        setStrategies(data.map((s) => s.listing).filter(Boolean) as StrategyListing[]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load marketplace data");
    } finally {
      setLoading(false);
    }
  }, [activeTab, typeFilter, premiumFilter, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setTypeFilter("all");
    setPremiumFilter(undefined);
    setSearch("");
  };

  const showFilters = activeTab === "best_roi" || activeTab === "new";

  return (
    <div className="p-5 space-y-4 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-[20px] font-bold text-[var(--color-text)]">Strategy Marketplace</h1>
          <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5">
            Discover, subscribe, and publish trading strategies
          </p>
        </div>
        <button
          onClick={() => setShowPublish(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-[8px] bg-[var(--color-primary)] text-white text-[13px] font-bold hover:opacity-90"
        >
          <Plus size={15} />
          Publish
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-[var(--color-surface-2)]">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 text-[13px] font-bold border-b-2 transition-colors",
                isActive
                  ? "text-[var(--color-primary)] border-[var(--color-primary)]"
                  : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
              )}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex items-center gap-3 flex-wrap">
          {/* Type filter */}
          <div className="flex items-center gap-1">
            {TYPE_FILTERS.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTypeFilter(tf.value)}
                className={cn(
                  "px-2.5 py-1 rounded-[6px] text-[11px] font-bold transition-colors",
                  typeFilter === tf.value
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                )}
              >
                {tf.label}
              </button>
            ))}
          </div>

          {/* Premium filter */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPremiumFilter(undefined)}
              className={cn(
                "px-2.5 py-1 rounded-[6px] text-[11px] font-bold transition-colors",
                !premiumFilter
                  ? "bg-[var(--color-primary)] text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              )}
            >
              All
            </button>
            <button
              onClick={() => setPremiumFilter("free")}
              className={cn(
                "px-2.5 py-1 rounded-[6px] text-[11px] font-bold transition-colors",
                premiumFilter === "free"
                  ? "bg-green-500 text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              )}
            >
              Free
            </button>
            <button
              onClick={() => setPremiumFilter("premium")}
              className={cn(
                "px-2.5 py-1 rounded-[6px] text-[11px] font-bold transition-colors",
                premiumFilter === "premium"
                  ? "bg-amber-500 text-white"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              )}
            >
              Premium
            </button>
          </div>

          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-[300px]">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search strategies..."
              className="w-full pl-8 pr-3 py-1.5 rounded-[6px] bg-[var(--color-surface-2)] text-[var(--color-text)] text-[12px] border border-transparent focus:border-[var(--color-primary)] outline-none"
            />
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="panel p-4">
              <LoadingSkeleton lines={4} />
            </div>
          ))}
        </div>
      ) : error ? (
        <EmptyState
          title="Error"
          description={error}
        />
      ) : strategies.length === 0 ? (
        <EmptyState
          icon={activeTab === "my_strategies" ? <FolderOpen size={32} /> : <Sparkles size={32} />}
          title={
            activeTab === "my_strategies"
              ? "You haven't published any strategies yet"
              : activeTab === "my_subscriptions"
                ? "You have no active subscriptions"
                : "No strategies found"
          }
          description={
            activeTab === "my_strategies"
              ? "Click 'Publish' to share your first strategy with the community"
              : activeTab === "my_subscriptions"
                ? "Browse the marketplace and subscribe to strategies"
                : "Try adjusting your filters or check back later"
          }
          action={
            activeTab === "my_strategies" ? (
              <button
                onClick={() => setShowPublish(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-[8px] bg-[var(--color-primary)] text-white text-[13px] font-bold hover:opacity-90"
              >
                <Plus size={14} />
                Publish Strategy
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {strategies.map((strategy) => (
            <StrategyCard
              key={strategy.id}
              strategy={strategy}
              onClick={() => setSelectedId(strategy.id)}
            />
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selectedId && (
        <StrategyDetail
          listingId={selectedId}
          onClose={() => setSelectedId(null)}
          onSubscribed={() => {
            // Refresh data if on subscriptions tab
            if (activeTab === "my_subscriptions") {
              loadData();
            }
          }}
        />
      )}

      {/* Publish modal */}
      {showPublish && (
        <PublishStrategyModal
          onClose={() => setShowPublish(false)}
          onPublished={() => {
            // Refresh data if on my_strategies tab
            if (activeTab === "my_strategies") {
              loadData();
            }
          }}
        />
      )}
    </div>
  );
}
