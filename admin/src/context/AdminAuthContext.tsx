import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export type AdminRole = 'super_admin' | 'plan_manager' | 'payment_manager' | 'support_agent' | 'content_manager' | 'analyst';

export interface AdminProfile {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: AdminRole;
  is_active: boolean;
  mfa_verified: boolean;
}

interface AdminAuthContextType {
  user: any | null;
  profile: AdminProfile | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  isSuperAdmin: boolean;
  mfaRequired: boolean;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => Promise<void>;
  verifyMfa: (code: string) => Promise<boolean>;
  refreshProfile: () => Promise<void>;
}

const AdminAuthContext = createContext<AdminAuthContextType | undefined>(undefined);

export const AdminAuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<any | null>(null);
  const [profile, setProfile] = useState<AdminProfile | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('agro_admin_token'));
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [mfaRequired, setMfaRequired] = useState<boolean>(false);

  const fetchAdminRole = async (tokenToUse: string, userHint?: any) => {
    try {
      const res = await fetch('/api/admin/me', {
        headers: {
          Authorization: `Bearer ${tokenToUse}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        const profileObj: AdminProfile = {
          id: data.id || data.user_id,
          user_id: data.user_id,
          email: data.email,
          full_name: data.full_name || data.email?.split('@')[0] || 'Administrator',
          role: data.role as AdminRole,
          is_active: data.is_active ?? true,
          mfa_verified: true,
        };
        setProfile(profileObj);
        setUser(userHint || { id: data.user_id, email: data.email, full_name: profileObj.full_name });
        setError(null);
        return true;
      }

      // If backend rejected token, clear local token
      if (res.status === 401 || res.status === 403) {
        const errJson = await res.json().catch(() => ({}));
        const errMsg = errJson?.detail?.error?.message || errJson?.detail || 'Access Denied: Administrative privileges required.';
        setError(errMsg);
        return false;
      }
      return false;
    } catch (err: any) {
      console.error('Failed to verify admin status:', err);
      return false;
    }
  };

  const checkSession = async () => {
    setLoading(true);
    setError(null);
    try {
      const storedToken = localStorage.getItem('agro_admin_token');
      if (storedToken) {
        const ok = await fetchAdminRole(storedToken);
        if (ok) {
          setToken(storedToken);
          setLoading(false);
          return;
        } else {
          localStorage.removeItem('agro_admin_token');
          setToken(null);
        }
      }

      // Supabase session fallback
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user && session?.access_token) {
        const ok = await fetchAdminRole(session.access_token, session.user);
        if (ok) {
          setToken(session.access_token);
        } else {
          setUser(null);
          setProfile(null);
        }
      } else {
        setUser(null);
        setProfile(null);
        setToken(null);
      }
    } catch (err: any) {
      setError(err.message || 'Session verification error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  const login = async (email: string, password?: string) => {
    setLoading(true);
    setError(null);
    try {
      // 1. Primary backend admin login with password & Super Admin approval enforcement
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password: password || '' })
      });

      const data = await res.json();

      if (!res.ok) {
        const errMsg = data?.detail?.error?.message || data?.detail || 'Authentication failed.';
        setError(errMsg);
        throw new Error(errMsg);
      }

      // Successfully authenticated
      const jwtToken = data.access_token;
      localStorage.setItem('agro_admin_token', jwtToken);
      setToken(jwtToken);

      const userObj = data.user;
      setUser(userObj);
      setProfile({
        id: userObj.id,
        user_id: userObj.id,
        email: userObj.email,
        full_name: userObj.full_name,
        role: data.role as AdminRole,
        is_active: true,
        mfa_verified: true,
      });
      setError(null);
    } catch (err: any) {
      // Fallback: If network or server error, try Supabase password login if available
      if (password && !err.message.includes('approval') && !err.message.includes('Head Super Admin')) {
        try {
          const { data, error: supaErr } = await supabase.auth.signInWithPassword({ email, password });
          if (!supaErr && data.session) {
            const ok = await fetchAdminRole(data.session.access_token, data.user);
            if (ok) {
              setToken(data.session.access_token);
              return;
            }
          }
        } catch {
          // ignore fallback error and keep primary error
        }
      }
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const verifyMfa = async (code: string): Promise<boolean> => {
    try {
      const { data: factors } = await supabase.auth.mfa.listFactors();
      const totpFactor = factors?.totp?.[0];
      if (!totpFactor) {
        setMfaRequired(false);
        return true;
      }

      const { data: challenge, error: challengeErr } = await supabase.auth.mfa.challenge({
        factorId: totpFactor.id,
      });
      if (challengeErr) throw challengeErr;

      const { error: verifyErr } = await supabase.auth.mfa.verify({
        factorId: totpFactor.id,
        challengeId: challenge.id,
        code,
      });

      if (verifyErr) throw verifyErr;

      setMfaRequired(false);
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        await fetchAdminRole(session.access_token, session.user);
      }
      return true;
    } catch (err: any) {
      setError(err.message || 'Invalid 6-digit TOTP code');
      return false;
    }
  };

  const logout = async () => {
    localStorage.removeItem('agro_admin_token');
    try {
      await supabase.auth.signOut();
    } catch {
      // ignore
    }
    setUser(null);
    setProfile(null);
    setToken(null);
    setError(null);
    setMfaRequired(false);
  };

  const isSuperAdmin = profile?.role === 'super_admin';

  return (
    <AdminAuthContext.Provider
      value={{
        user,
        profile,
        token,
        loading,
        error,
        isSuperAdmin,
        mfaRequired,
        login,
        logout,
        verifyMfa,
        refreshProfile: checkSession,
      }}
    >
      {children}
    </AdminAuthContext.Provider>
  );
};

export const useAdminAuth = () => {
  const context = useContext(AdminAuthContext);
  if (!context) {
    throw new Error('useAdminAuth must be used within an AdminAuthProvider');
  }
  return context;
};
