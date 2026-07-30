import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Session } from '@supabase/supabase-js';
import { getSupabaseClient } from '@/lib/supabase';
import { AuthContext, type AuthContextValue } from './AuthContext';

interface AuthProviderProps {
  children: ReactNode;
}

const SESSION_STARTED_AT_KEY = 'kanbankaii.auth.sessionStartedAt';
const MAX_SESSION_AGE_MS = 3 * 24 * 60 * 60 * 1000;

function readSessionStartedAt(userId: string): number | null {
  try {
    const value = window.localStorage.getItem(SESSION_STARTED_AT_KEY);
    if (!value) return null;

    const parsed = JSON.parse(value) as { userId?: string; startedAt?: number };
    if (parsed.userId !== userId || typeof parsed.startedAt !== 'number') {
      return null;
    }
    return parsed.startedAt;
  } catch {
    return null;
  }
}

function writeSessionStartedAt(userId: string, startedAt = Date.now()) {
  window.localStorage.setItem(
    SESSION_STARTED_AT_KEY,
    JSON.stringify({ userId, startedAt }),
  );
}

function clearSessionStartedAt() {
  window.localStorage.removeItem(SESSION_STARTED_AT_KEY);
}

function isSessionTooOld(session: Session): boolean {
  const startedAt = readSessionStartedAt(session.user.id);
  if (!startedAt) {
    writeSessionStartedAt(session.user.id);
    return false;
  }
  return Date.now() - startedAt > MAX_SESSION_AGE_MS;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [configurationError, setConfigurationError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const supabase = getSupabaseClient();

      void supabase.auth.getSession().then(({ data, error }) => {
        if (error || !data.session) {
          setSession(null);
        } else if (isSessionTooOld(data.session)) {
          clearSessionStartedAt();
          setSession(null);
          void supabase.auth.signOut();
        } else {
          setSession(data.session);
        }
        setIsLoading(false);
      });

      const { data: listener } = supabase.auth.onAuthStateChange(
        (event, nextSession) => {
          if (event === 'SIGNED_OUT' || !nextSession) {
            clearSessionStartedAt();
            setSession(null);
            setIsLoading(false);
            return;
          }

          if (event === 'SIGNED_IN') {
            writeSessionStartedAt(nextSession.user.id);
          }

          if (isSessionTooOld(nextSession)) {
            clearSessionStartedAt();
            setSession(null);
            void supabase.auth.signOut();
          } else {
            setSession(nextSession);
          }
          setIsLoading(false);
        },
      );

      return () => listener.subscription.unsubscribe();
    } catch (error) {
      setConfigurationError(
        error instanceof Error ? error.message : 'Supabase is not configured',
      );
      setIsLoading(false);
      return undefined;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      isLoading,
      configurationError,
      signOut: async () => {
        const supabase = getSupabaseClient();
        const { error } = await supabase.auth.signOut();
        clearSessionStartedAt();
        if (error) throw error;
      },
    }),
    [configurationError, isLoading, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
