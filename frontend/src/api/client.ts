import { getSupabaseClient } from '@/lib/supabase';

export interface ApiRequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | null | undefined>;
}

export async function apiRequest<T = void>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
  if (!apiBaseUrl) {
    throw new Error('Frontend API configuration is missing');
  }

  const { data, error } = await getSupabaseClient().auth.getSession();
  if (error || !data.session?.access_token) {
    throw new Error('Your session has expired. Please sign in again.');
  }

  const url = new URL(path, apiBaseUrl);
  if (options.params) {
    for (const [key, value] of Object.entries(options.params)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${data.session.access_token}`,
      'ngrok-skip-browser-warning': '1',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

