import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, uuid } from "./api";

export interface Loadable<T> {
  data: T | undefined;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** GET a path; optionally poll every `pollMs` while `shouldPoll(data)` is true. */
export function useGet<T>(path: string | null, opts: { pollMs?: number; shouldPoll?: (d: T | undefined) => boolean } = {}): Loadable<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const [tick, setTick] = useState(0);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = async (first: boolean) => {
      if (first) setLoading(true);
      try {
        const d = await api.get<T>(path);
        if (!alive) return;
        setData(d);
        setError(null);
        const { pollMs, shouldPoll } = optsRef.current;
        if (pollMs && shouldPoll?.(d)) timer = setTimeout(() => run(false), pollMs);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) }));
      } finally {
        if (alive && first) setLoading(false);
      }
    };
    run(true);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

/**
 * A user action that POSTs once. The Idempotency-Key is generated when the action is first attempted and reused on
 * retry of the same body, so a timed-out write can be retried safely (server replays the stored response).
 */
export function useMutation<T>() {
  const keyRef = useRef<{ key: string; sig: string } | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<T | null>(null);

  const run = useCallback(async (path: string, body: unknown): Promise<T | null> => {
    const sig = path + JSON.stringify(body);
    if (!keyRef.current || keyRef.current.sig !== sig) keyRef.current = { key: uuid(), sig };
    setPending(true);
    setError(null);
    try {
      const r = await api.post<T>(path, body, keyRef.current.key);
      setResult(r);
      keyRef.current = null; // completed: the next action gets a fresh key
      return r;
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, { code: "CLIENT_ERROR", message: String(e) });
      setError(err);
      // Keep the key for network errors (retry is the same action). Clear it for definite server rejections.
      if (err.status !== 0 && err.code !== "UPSTREAM_UNAVAILABLE") keyRef.current = null;
      return null;
    } finally {
      setPending(false);
    }
  }, []);

  return { run, pending, error, result, reset: () => { setError(null); setResult(null); } };
}

export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function useMediaQuery(q: string): boolean {
  const [m, setM] = useState(() => (typeof window !== "undefined" ? window.matchMedia(q).matches : false));
  useEffect(() => {
    const mq = window.matchMedia(q);
    const f = () => setM(mq.matches);
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, [q]);
  return m;
}
