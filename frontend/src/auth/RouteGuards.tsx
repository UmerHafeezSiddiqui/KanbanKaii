import { useEffect, type ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { safeAuthRedirect } from './redirect';
import { navigateTo } from '@/lib/navigation';

function AuthLoadingScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-violet-100 px-4">
      <div className="rounded-xl border border-violet-200 bg-white px-6 py-5 text-center shadow-lg">
        <p className="text-sm font-medium text-slate-700">Loading your workspace…</p>
      </div>
    </main>
  );
}

function AuthConfigurationError({ message }: { message: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-violet-100 px-4">
      <div className="max-w-md rounded-xl border border-red-200 bg-white p-6 shadow-lg">
        <h1 className="text-lg font-semibold text-slate-900">Authentication is not configured</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{message}</p>
      </div>
    </main>
  );
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, configurationError } = useAuth();

  useEffect(() => {
    if (!isLoading && !configurationError && !user) {
      const returnPath = `${window.location.pathname}${window.location.search}`;
      navigateTo(`/auth?redirect=${encodeURIComponent(returnPath)}`, { replace: true });
    }
  }, [configurationError, isLoading, user]);

  if (isLoading) return <AuthLoadingScreen />;
  if (configurationError) return <AuthConfigurationError message={configurationError} />;
  if (!user) return <AuthLoadingScreen />;
  return children;
}

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, configurationError } = useAuth();

  useEffect(() => {
    if (!isLoading && user) {
      navigateTo(safeAuthRedirect(), { replace: true });
    }
  }, [isLoading, user]);

  if (isLoading || user) return <AuthLoadingScreen />;
  if (configurationError) return children;
  return children;
}
