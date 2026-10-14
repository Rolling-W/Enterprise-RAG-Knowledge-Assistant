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
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(
      () => setSession(null),
      session.expires_in * 1000,
    );
    return () => window.clearTimeout(timer);
  }, [session]);
  async function signIn(username: string, password: string) {
    setSession(await api.login(username, password));
  }
  function signOut() {
    if (session) void api.logout(session.access_token).catch(() => undefined);
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
