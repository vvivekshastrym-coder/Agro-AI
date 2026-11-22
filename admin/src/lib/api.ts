import { supabase } from './supabase';

export const API_BASE_URL = ((import.meta as any).env?.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export const resolveAdminApiUrl = (url: string): string => {
  if (!API_BASE_URL || !url.startsWith('/api/')) return url;
  return `${API_BASE_URL}${url}`;
};

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
  return fetch(resolveAdminApiUrl(url), {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  });
};
