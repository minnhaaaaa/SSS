import { useCallback, useEffect, useState, type DependencyList } from "react";

export interface ApiResource<T> {
  readonly data: T | null;
  readonly error: Error | null;
  readonly loading: boolean;
  readonly reload: () => void;
}

export function useApiResource<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  dependencies: DependencyList,
): ApiResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setData(null);
    void loader(controller.signal)
      .then((value) => {
        setData(value);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason : new Error("Unknown API error"));
          setLoading(false);
        }
      });
    return () => controller.abort();
    // The caller controls the complete dependency list for its stable loader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, revision]);

  return { data, error, loading, reload };
}
