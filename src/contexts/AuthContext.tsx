import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  getCurrentUser as fetchCurrentUser,
  registerAccount,
  signIn as apiSignIn,
  signOut as apiSignOut,
  type AuthUser,
} from "../services/api";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  register: (input: { full_name: string; email: string; password: string }) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await fetchCurrentUser());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refreshUser(); }, [refreshUser]);

  useEffect(() => {
    const expireSession = () => { setUser(null); setLoading(false); };
    window.addEventListener("aerovision:unauthorized", expireSession);
    return () => window.removeEventListener("aerovision:unauthorized", expireSession);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await apiSignIn(email, password);
    setUser(response.user);
  }, []);

  const register = useCallback(async (input: { full_name: string; email: string; password: string }) => {
    await registerAccount(input);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await apiSignOut();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, signIn, register, signOut, refreshUser }), [user, loading, signIn, register, signOut, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider.");
  return value;
}
