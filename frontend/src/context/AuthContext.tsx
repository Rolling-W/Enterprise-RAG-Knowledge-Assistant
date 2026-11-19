import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api/client";
import type { Session } from "../types";

interface AuthValue {
  session: Session | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
}
const AuthContext = createContext<AuthValue | undefined>(undefined);
const SESSION_STORAGE_KEY = "enterprise-rag-session";

interface StoredSession {
  session: Session;
  expiresAt: number;
}

function restoreSession(): StoredSession | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw) as StoredSession;
    if (!stored.session?.access_token || stored.expiresAt <= Date.now()) {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return stored;
  } catch {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredSession | null>(restoreSession);
  const [session, setSession] = useState<Session | null>(stored?.session ?? null);
  useEffect(
    () => api.onUnauthorized((token) => {
      // A delayed response for an old login must not clear a newer session.
      setSession((current) => {
        if (current?.access_token !== token) return current;
        window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
        setStored(null);
        return null;
      });
    }),
    [],
  );
  useEffect(() => {
    if (!session) return;
    const expiresAt = stored?.expiresAt ?? Date.now() + session.expires_in * 1000;
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ session, expiresAt }),
    );
    const timer = window.setTimeout(
      () => {
        setSession(null);
        setStored(null);
        window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      },
      Math.max(0, expiresAt - Date.now()),
    );
    return () => window.clearTimeout(timer);
  }, [session, stored?.expiresAt]);
  async function signIn(username: string, password: string) {
    const next = await api.login(username, password);
    const expiresAt = Date.now() + next.expires_in * 1000;
    setStored({ session: next, expiresAt });
    setSession(next);
  }
  function signOut() {
    if (session) void api.logout(session.access_token).catch(() => undefined);
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    setStored(null);
    setSession(null);
  }
  return (
    <AuthContext.Provider value={{ session, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
