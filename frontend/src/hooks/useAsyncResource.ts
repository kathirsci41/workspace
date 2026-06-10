import { DependencyList, Dispatch, SetStateAction, useCallback, useEffect, useState } from 'react';

interface AsyncResource<T> {
  data: T | null;
  error: string | null;
  isLoading: boolean;
  reload: () => Promise<T | null>;
  setData: Dispatch<SetStateAction<T | null>>;
}

export function useAsyncResource<T>(loader: () => Promise<T>, deps: DependencyList): AsyncResource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const next = await loader();
      setData(next);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setIsLoading(false);
    }
  }, deps);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    loader()
      .then((next) => {
        if (active) setData(next);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, deps);

  return { data, error, isLoading, reload, setData };
}
