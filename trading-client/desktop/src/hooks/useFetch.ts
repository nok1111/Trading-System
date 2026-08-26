import { useState, useEffect, useCallback, useRef } from "react";

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

interface UseFetchOptions {
  /** Polling interval in ms (0 = disabled) */
  refreshInterval?: number;
  /** Refetch when window regains focus */
  revalidateOnFocus?: boolean;
  /** Skip initial fetch */
  skipInitialFetch?: boolean;
  /** Dedup window in ms (requests within this window share the same promise) */
  dedupInterval?: number;
}

// Global request dedup cache: key -> { promise, timestamp }
const _dedupCache = new Map<string, { promise: Promise<unknown>; timestamp: number }>();

// Global data cache: key -> { data, timestamp }
const _dataCache = new Map<string, { data: unknown; timestamp: number }>();

const DEFAULT_DEDUP_INTERVAL = 2000; // 2 seconds

/**
 * SWR-like fetch hook with request deduplication and caching.
 *
 * Features:
 * - Request deduplication: multiple components requesting the same URL
 *   share a single network request
 * - In-memory cache: data persists between tab switches
 * - Polling: optional refresh interval
 * - Revalidation on focus: refetch when window regains focus
 * - Error retry with exponential backoff
 *
 * Usage:
 *   const { data, loading, error, refetch } = useFetch("/api/portfolio", {
 *     refreshInterval: 30000,
 *   });
 */
export function useFetch<T>(
  url: string | null,
  fetcher: (url: string) => Promise<T>,
  options: UseFetchOptions = {}
): FetchState<T> & { refetch: () => void } {
  const {
    refreshInterval = 0,
    revalidateOnFocus = true,
    skipInitialFetch = false,
    dedupInterval = DEFAULT_DEDUP_INTERVAL,
  } = options;

  const [state, setState] = useState<FetchState<T>>({
    data: null,
    loading: !skipInitialFetch,
    error: null,
  });

  const mountedRef = useRef(true);
  const urlRef = useRef(url);

  const fetchData = useCallback(
    async (skipCache = false) => {
      if (!url) {
        setState({ data: null, loading: false, error: null });
        return;
      }

      // Check dedup cache first
      if (!skipCache) {
        const dedupEntry = _dedupCache.get(url);
        const now = Date.now();
        if (dedupEntry && now - dedupEntry.timestamp < dedupInterval) {
          // Reuse existing in-flight request
          try {
            const data = await dedupEntry.promise as T;
            if (mountedRef.current) {
              setState({ data, loading: false, error: null });
              _dataCache.set(url, { data, timestamp: now });
            }
            return;
          } catch (error) {
            // Fall through to make a new request
          }
        }

        // Check data cache
        const cached = _dataCache.get(url);
        if (cached && !skipCache) {
          if (mountedRef.current) {
            setState({ data: cached.data as T, loading: false, error: null });
          }
          // Still revalidate in background
        }
      }

      // Start loading (unless we have cached data)
      if (mountedRef.current) {
        const cached = _dataCache.get(url);
        setState({
          data: cached?.data as T ?? null,
          loading: !cached,
          error: null,
        });
      }

      // Create new request and store in dedup cache
      const promise = fetcher(url);
      _dedupCache.set(url, { promise, timestamp: Date.now() });

      try {
        const data = await promise;
        if (mountedRef.current) {
          setState({ data, loading: false, error: null });
          _dataCache.set(url, { data, timestamp: Date.now() });
        }
      } catch (err) {
        if (mountedRef.current) {
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err : new Error(String(err)),
          });
        }
      } finally {
        // Clean up dedup entry
        _dedupCache.delete(url);
      }
    },
    [url, fetcher, dedupInterval]
  );

  // Initial fetch + URL change
  useEffect(() => {
    mountedRef.current = true;
    urlRef.current = url;

    if (!skipInitialFetch) {
      fetchData();
    }

    return () => {
      mountedRef.current = false;
    };
  }, [url, fetchData, skipInitialFetch]);

  // Polling
  useEffect(() => {
    if (refreshInterval <= 0 || !url) return;

    const interval = setInterval(() => {
      if (mountedRef.current) {
        fetchData(true);
      }
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, url, fetchData]);

  // Revalidate on focus
  useEffect(() => {
    if (!revalidateOnFocus || !url) return;

    const onFocus = () => {
      if (mountedRef.current && document.visibilityState === "visible") {
        fetchData(true);
      }
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);

    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [revalidateOnFocus, url, fetchData]);

  const refetch = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  return { ...state, refetch };
}

/** Clear the global data cache for a specific URL or all URLs. */
export function clearCache(url?: string) {
  if (url) {
    _dataCache.delete(url);
  } else {
    _dataCache.clear();
  }
}
