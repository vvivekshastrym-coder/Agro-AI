import { supabase } from './supabase';

export const getAdminToken = async (): Promise<string | null> => {
  const localToken = localStorage.getItem('agro_admin_token');
  if (localToken) return localToken;
  try {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  } catch {
    return null;
  }
};

export const getAdminAuthHeaders = async (): Promise<Record<string, string>> => {
  const token = await getAdminToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const adminFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
  const defaultHeaders = await getAdminAuthHeaders();
  return fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  });
};
