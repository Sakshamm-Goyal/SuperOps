import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, getToken, setToken, type Me, type Resource } from "./api";

interface AuthState {
  me: Me | null;
  loading: boolean;
  error: string | null;
  signIn: (token: string) => Promise<boolean>;
  signOut: () => void;
  canOperate: boolean;
  isAdmin: boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getToken());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (tok: string) => {
    const r = await api.get<Resource<Me>>("/v1/me", tok);
    return r.data;
  }, []);

  useEffect(() => {
    const t = getToken();
    if (!t) return;
    load(t)
      .then(setMe)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, [load]);

  const signIn = useCallback(
    async (tok: string) => {
      setError(null);
      setLoading(true);
      try {
        const m = await load(tok.trim());
        setToken(tok.trim());
        setMe(m);
        return true;
      } catch (e) {
        setError(e instanceof ApiError && e.status === 401 ? "That token was not recognised. Paste a sandbox token from var/actors.local.json." : e instanceof Error ? e.message : String(e));
        return false;
      } finally {
        setLoading(false);
      }
    },
    [load],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  const role = me?.role;
  return (
    <Ctx.Provider value={{ me, loading, error, signIn, signOut, canOperate: role === "operator" || role === "admin", isAdmin: role === "admin" }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
