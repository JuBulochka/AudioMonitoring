import { useState, useEffect, useCallback, useRef } from 'react';
import { AxiosError } from 'axios';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const isMounted = useRef(true);

  const fetch = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcher();
      if (isMounted.current) setState({ data, loading: false, error: null });
    } catch (err) {
      if (!isMounted.current) return;
      const msg =
        err instanceof AxiosError
          ? (err.response?.data as { detail?: string })?.detail || err.message
          : 'Неизвестная ошибка';
      setState({ data: null, loading: false, error: msg });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    isMounted.current = true;
    fetch();
    return () => {
      isMounted.current = false;
    };
  }, [fetch]);

  return { ...state, refetch: fetch };
}
