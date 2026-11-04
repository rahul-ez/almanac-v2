import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react';

export function useData<T>(load: (signal: AbortSignal) => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const loader = useRef(load);
  loader.current = load;
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loader
      .current(controller.signal)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active && e?.name !== 'AbortError') setError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
    // Call sites declare the identity of their requested resource in deps.
  }, [...deps, version]);
  return { data, setData, error, loading, reload };
}

export function usePages<T>(
  load: (
    cursor: string | null,
    signal: AbortSignal,
  ) => Promise<{ items: T[]; next_cursor: string | null }>,
  deps: DependencyList = [],
) {
  const loader = useRef(load);
  loader.current = load;
  const [items, setItems] = useState<T[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [version, setVersion] = useState(0);
  const active = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const fetchPage = useCallback(async (cursor: string | null, reset: boolean) => {
    if (pending.current && !reset) return;
    if (reset) controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    pending.current = true;
    setLoading(true);
    setError(null);
    if (reset) setItems([]);
    try {
      const p = await loader.current(cursor, abort.signal);
      if (active.current && !abort.signal.aborted) {
        setItems((old) => (reset ? p.items : [...old, ...p.items]));
        setNext(p.next_cursor);
      }
    } catch (e) {
      if (active.current && !abort.signal.aborted) setError(e);
    } finally {
      if (active.current && !abort.signal.aborted) {
        pending.current = false;
        setLoading(false);
      }
    }
  }, []);
  useEffect(() => {
    active.current = true;
    void fetchPage(null, true);
    return () => {
      active.current = false;
      controller.current?.abort();
    };
  }, [...deps, version]);
  return {
    items,
    next,
    loading,
    error,
    reload: () => setVersion((v) => v + 1),
    loadMore: () => void fetchPage(next, false),
  };
}
