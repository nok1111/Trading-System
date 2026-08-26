import { useState, useCallback, useRef } from "react";

interface OptimisticUpdateOptions {
  onRollback?: (error: Error) => void;
  onConfirm?: () => void;
}

interface OptimisticUpdateReturn<T> {
  /** Current data (optimistic or confirmed) */
  data: T;
  /** True while the async operation is in flight */
  pending: boolean;
  /** Error from the last failed operation */
  error: Error | null;
  /** Apply an optimistic update and execute the async operation */
  update: (optimisticData: T, asyncFn: () => Promise<T>) => Promise<T>;
  /** Set data directly (no optimistic update) */
  setData: (data: T) => void;
  /** Rollback to the last confirmed state */
  rollback: () => void;
}

/**
 * Hook for optimistic UI updates.
 *
 * Usage:
 *   const { data: balance, update, pending } = useOptimisticUpdate(initialBalance);
 *
 *   const handleTrade = async () => {
 *     // Show new balance immediately
 *     const optimisticBalance = balance - tradeAmount;
 *     await update(optimisticBalance, async () => {
 *       return await api.executeTrade(trade);
 *     });
 *     // If the API fails, the balance automatically rolls back
 *   };
 */
export function useOptimisticUpdate<T>(
  initialData: T,
  options: OptimisticUpdateOptions = {}
): OptimisticUpdateReturn<T> {
  const [data, setDataState] = useState<T>(initialData);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const confirmedRef = useRef<T>(initialData);

  const update = useCallback(
    async (optimisticData: T, asyncFn: () => Promise<T>): Promise<T> => {
      // Save current state for rollback
      const previousData = confirmedRef.current;

      // Apply optimistic update immediately
      setDataState(optimisticData);
      setPending(true);
      setError(null);

      try {
        // Execute the async operation
        const result = await asyncFn();

        // Confirm the update with the real result
        confirmedRef.current = result;
        setDataState(result);
        options.onConfirm?.();
        return result;
      } catch (err) {
        // Rollback to the confirmed state
        setDataState(previousData);
        confirmedRef.current = previousData;
        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        options.onRollback?.(error);
        throw error;
      } finally {
        setPending(false);
      }
    },
    [options]
  );

  const setData = useCallback((newData: T) => {
    confirmedRef.current = newData;
    setDataState(newData);
    setError(null);
  }, []);

  const rollback = useCallback(() => {
    setDataState(confirmedRef.current);
  }, []);

  return {
    data,
    pending,
    error,
    update,
    setData,
    rollback,
  };
}
