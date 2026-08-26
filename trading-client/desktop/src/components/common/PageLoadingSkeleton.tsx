/** Loading skeleton for lazy-loaded pages. */
export function PageLoadingSkeleton() {
  return (
    <div className="p-5 max-w-[1400px] mx-auto space-y-4">
      {/* Hero skeleton */}
      <div className="panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-[var(--color-surface-2)] animate-pulse" />
          <div className="h-5 w-48 bg-[var(--color-surface-2)] rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="h-3 w-20 bg-[var(--color-surface-2)] rounded animate-pulse" />
            <div className="h-8 w-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-20 bg-[var(--color-surface-2)] rounded animate-pulse" />
            <div className="h-8 w-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-20 bg-[var(--color-surface-2)] rounded animate-pulse" />
            <div className="h-8 w-32 bg-[var(--color-surface-2)] rounded animate-pulse" />
          </div>
        </div>
      </div>

      {/* Content grid skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="panel p-4 h-[200px] bg-[var(--color-surface-2)] animate-pulse rounded-lg" />
          <div className="panel p-4 h-[150px] bg-[var(--color-surface-2)] animate-pulse rounded-lg" />
        </div>
        <div className="space-y-4">
          <div className="panel p-4 h-[120px] bg-[var(--color-surface-2)] animate-pulse rounded-lg" />
          <div className="panel p-4 h-[180px] bg-[var(--color-surface-2)] animate-pulse rounded-lg" />
        </div>
      </div>
    </div>
  );
}
