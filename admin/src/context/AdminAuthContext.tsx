import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import { resolveAdminApiUrl } from '../lib/api';

export type AdminRole =
  | 'super_admin'
  | 'admin'
  | 'staff'
  | 'plan_manager'
  | 'payment_manager'
  | 'payment_staff'
  | 'support_agent'
  | 'content_manager'
  | 'listing_reviewer'
  | 'seller_reviewer'
  | 'analyst';

export type HierarchyLevel = 'SUPER_ADMIN_HEAD' | 'ADMIN' | 'STAFF';

export interface AdminProfile {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: AdminRole;
  hierarchy_level: HierarchyLevel;
  permissions: Record<string, string[]>;
  authorized_modules: string[];
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
  isAdminOrAbove: boolean;
  mfaRequired: boolean;
  hasPermission: (module: string, action: string) => boolean;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => Promise<void>;
  logoutAllDevices: () => Promise<void>;
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
      const res = await fetch(resolveAdminApiUrl('/api/admin/me'), {
        headers: {
          Authorization: `Bearer ${tokenToUse}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        // Check Supabase MFA assurance level when a Supabase session is active
        let needsMfa = false;
        try {
          const { data: aalData } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
          if (aalData && aalData.nextLevel === 'aal2' && aalData.currentLevel !== 'aal2') {
            needsMfa = true;
          }
        } catch {
          // Non-Supabase local token path; backend enforces MFA_REQUIRED directly
        }
        const roleVal = (data.role || 'staff') as AdminRole;
        const hLevel: HierarchyLevel =
          data.hierarchy_level ||
          (roleVal === 'super_admin' ? 'SUPER_ADMIN_HEAD' : roleVal === 'admin' ? 'ADMIN' : 'STAFF');
        const profileObj: AdminProfile = {
          id: data.id || data.user_id,
          user_id: data.user_id,
          email: data.email,
          full_name: data.full_name || data.email?.split('@')[0] || 'Administrator',
          role: roleVal,
          hierarchy_level: hLevel,
          permissions: data.permissions || {},
          authorized_modules: data.authorized_modules || [],
          is_active: data.is_active ?? true,
          mfa_verified: !needsMfa,
        };
        setMfaRequired(needsMfa);
        setProfile(profileObj);
        setUser(userHint || { id: data.user_id, email: data.email, full_name: profileObj.full_name });
        setError(null);
        return true;
      }

      if (res.status === 401 || res.status === 403) {
        const errJson = await res.json().catch(() => ({}));
        const errCode = errJson?.detail?.error?.code;
        if (errCode === 'MFA_REQUIRED') {
          setMfaRequired(true);
          setError('Multi-factor authentication (TOTP/Passkey) is required.');
          return false;
        }
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

      try {
        const sessionPromise = supabase.auth.getSession();
        const timeoutPromise = new Promise<{ data: { session: null } }>((resolve) =>
          setTimeout(() => resolve({ data: { session: null } }), 1500)
        );
        const { data: { session } } = (await Promise.race([sessionPromise, timeoutPromise])) as any;
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
      } catch {
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
      const res = await fetch(resolveAdminApiUrl('/api/admin/login'), {
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

      const jwtToken = data.access_token;
      localStorage.setItem('agro_admin_token', jwtToken);
      setToken(jwtToken);

      const ok = await fetchAdminRole(jwtToken, data.user);
      if (!ok) {
        const userObj = data.user;
        const roleVal = (data.role || 'staff') as AdminRole;
        setUser(userObj);
        setProfile({
          id: userObj.id,
          user_id: userObj.id,
          email: userObj.email,
          full_name: userObj.full_name,
          role: roleVal,
          hierarchy_level: roleVal === 'super_admin' ? 'SUPER_ADMIN_HEAD' : roleVal === 'admin' ? 'ADMIN' : 'STAFF',
          permissions: {},
          authorized_modules: [],
          is_active: true,
          mfa_verified: true,
        });
      }
      setError(null);
    } catch (err: any) {
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
          // ignore fallback error
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

  const logoutAllDevices = async () => {
    const activeToken = token || localStorage.getItem('agro_admin_token');
    if (activeToken) {
      try {
        await fetch(resolveAdminApiUrl('/api/admin/sessions/revoke-all'), {
          method: 'POST',
          headers: { Authorization: `Bearer ${activeToken}` },
        });
      } catch {
        // continue local cleanup
      }
    }
    localStorage.removeItem('agro_admin_token');
    try {
      await supabase.auth.signOut({ scope: 'global' });
    } catch {
      // ignore
    }
    setUser(null);
    setProfile(null);
    setToken(null);
    setError(null);
    setMfaRequired(false);
  };

  // Configurable idle session timeout (default 15 minutes)
  useEffect(() => {
    if (!user || !profile) return;
    const idleMs = Number((import.meta as any).env?.VITE_ADMIN_IDLE_TIMEOUT_MS || 900000);
    if (!Number.isFinite(idleMs) || idleMs <= 0) return;
    let timer = window.setTimeout(() => {
      logout();
    }, idleMs);
    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        logout();
      }, idleMs);
    };
    const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
    events.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    return () => {
      window.clearTimeout(timer);
      events.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [user, profile]);

  const isSuperAdmin = profile?.role === 'super_admin' || profile?.hierarchy_level === 'SUPER_ADMIN_HEAD';
  const isAdminOrAbove = isSuperAdmin || profile?.role === 'admin' || profile?.hierarchy_level === 'ADMIN';

  const hasPermission = (module: string, action: string): boolean => {
    if (!profile) return false;
    if (profile.role === 'super_admin' || profile.hierarchy_level === 'SUPER_ADMIN_HEAD') return true;
    const modPerms = profile.permissions?.[module];
    if (Array.isArray(modPerms)) {
      return modPerms.includes(action);
    }
    return false;
  };

  return (
    <AdminAuthContext.Provider
      value={{
        user,
        profile,
        token,
        loading,
        error,
        isSuperAdmin,
        isAdminOrAbove,
        mfaRequired,
        hasPermission,
        login,
        logout,
        logoutAllDevices,
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
