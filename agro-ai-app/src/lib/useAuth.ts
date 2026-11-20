import React, { createContext, useContext, useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase, isSupabaseConfigured } from "./supabaseClient";

interface AuthContextValue {
  session: Session | null;
  loading: boolean;
  user: User | null;
  isPhoneVerified: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function syncLocalAuthStorage(session: Session | null) {
  try {
    if (session?.user && session.access_token) {
      localStorage.setItem("kisanToken", session.access_token);
      localStorage.setItem("kisanAuth", "true");
      localStorage.setItem(
        "kisanUser",
        JSON.stringify({
          id: session.user.id,
          email: session.user.email ?? "",
          phone: session.user.phone ?? "",
          name:
            session.user.user_metadata?.full_name ||
            session.user.user_metadata?.name ||
            session.user.email?.split("@")[0] ||
            "Farmer",
          avatar: session.user.user_metadata?.avatar_url || "",
        })
      );
    }
  } catch {
    // Ignore storage quota / private mode errors
  }
}

function clearLocalAuthStorage() {
  try {
    localStorage.removeItem("kisanToken");
    localStorage.removeItem("kisanAuth");
    localStorage.removeItem("kisanUser");
  } catch {
    // Ignore storage errors
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    if (!isSupabaseConfigured) {
      setLoading(false);
      return;
    }

    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!mounted) return;
        if (error) {
          console.error("Failed to restore auth session:", error.message);
        }
        const currentSession = data?.session ?? null;
        setSession(currentSession);
        if (currentSession) {
          syncLocalAuthStorage(currentSession);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        console.error("Unexpected auth session error:", err);
        setLoading(false);
      });

    const { data: sub } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (!mounted) return;
      setSession(nextSession);
      setLoading(false);
      if (event === "SIGNED_OUT") {
        clearLocalAuthStorage();
      } else if (nextSession) {
        syncLocalAuthStorage(nextSession);
      }
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const value: AuthContextValue = {
    session,
    loading,
    user: session?.user ?? null,
    isPhoneVerified: Boolean(session?.user?.phone_confirmed_at),
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx) return ctx;

  // Fallback for standalone usage outside AuthProvider
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!mounted) return;
        setSession(data?.session ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        setLoading(false);
      });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!mounted) return;
      setSession(s);
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return {
    session,
    loading,
    user: session?.user ?? null,
    isPhoneVerified: Boolean(session?.user?.phone_confirmed_at),
  };
}

export function formatOAuthError(error: unknown, description?: string | null): string {
  const rawMessage =
    typeof error === "string"
      ? error
      : error instanceof Error
        ? error.message
        : (error as { message?: string } | null)?.message || "";
  const combined = `${rawMessage} ${description || ""}`.toLowerCase();

  if (
    combined.includes("access_denied") ||
    combined.includes("cancel") ||
    combined.includes("denied")
  ) {
    return "Google sign-in was cancelled. You can try again or log in with Phone OTP or Email.";
  }
  if (
    combined.includes("provider is not enabled") ||
    combined.includes("unsupported provider")
  ) {
    return "Google sign-in is currently disabled. Please log in with Phone OTP or Email.";
  }
  if (
    combined.includes("invalid_client") ||
    combined.includes("client_id") ||
    combined.includes("unauthorized_client")
  ) {
    return "Google sign-in configuration is invalid. Please contact support or use Phone OTP.";
  }
  if (combined.includes("redirect_uri_mismatch") || combined.includes("redirect")) {
    return "Sign-in redirect URL mismatch. Please try again later or use Phone OTP.";
  }
  if (
    combined.includes("fetch") ||
    combined.includes("network") ||
    combined.includes("timeout")
  ) {
    return "Network connection error. Please check your internet connection and try again.";
  }
  if (combined.includes("supabase") && combined.includes("env")) {
    return "Authentication service is temporarily unavailable. Please try again later.";
  }
  if (description && !description.toLowerCase().includes("secret")) {
    return description;
  }
  return rawMessage || "Unable to complete Google sign-in. Please try again.";
}

export function formatE164Phone(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 10) return `+91${digits}`;
  if (digits.length === 12 && digits.startsWith("91")) return `+${digits}`;
  return `+${digits}`;
}

export function maskPhone(fullPhone: string): string {
  const digits = fullPhone.replace(/\D/g, "");
  if (digits.length >= 10) {
    const last4 = digits.slice(-4);
    return `+91 ****** ${last4}`;
  }
  return fullPhone;
}

export async function signInWithPhone(rawPhone: string): Promise<{ error?: string }> {
  const cleaned = rawPhone.replace(/\D/g, "");
  if (cleaned.length < 10) {
    return { error: "Please enter a valid 10-digit mobile number." };
  }
  const phone = formatE164Phone(cleaned);

  try {
    // 1. Primary: Agro AI FastAPI Production Backend Endpoint
    const apiBase = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) || "";
    const res = await fetch(`${apiBase}/api/auth/phone-otp/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, role: "farmer" }),
    });

    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      return {};
    }

    if (data.detail?.error?.message || typeof data.detail === "string") {
      const errMsg = data.detail?.error?.message || data.detail;
      return { error: errMsg };
    }

    // 2. Secondary fallback: Supabase Auth if backend endpoint is unavailable
    const { error: supaErr } = await supabase.auth.signInWithOtp({
      phone,
      options: { channel: "sms" },
    });

    if (supaErr) {
      const msg = supaErr.message?.toLowerCase() || "";
      if (msg.includes("rate") || msg.includes("too many") || supaErr.status === 429) {
        return { error: "Too many OTP requests. Please wait a few minutes before trying again." };
      }
      return { error: "Unable to send verification code right now. Please try again." };
    }

    return {};
  } catch {
    return { error: "Network connection error. Please check your internet and try again." };
  }
}

export async function verifyPhoneOtp(
  rawPhone: string,
  token: string
): Promise<{ session: Session | any | null; user: User | any | null; error?: string }> {
  const phone = formatE164Phone(rawPhone);
  const cleanToken = token.trim();

  if (!cleanToken || cleanToken.length !== 6) {
    return { session: null, user: null, error: "Please enter the complete 6-digit OTP code." };
  }

  try {
    // 1. Primary: Agro AI FastAPI Production Backend Endpoint
    const apiBase = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) || "";
    const res = await fetch(`${apiBase}/api/auth/phone-otp/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, token: cleanToken, role: "farmer" }),
    });

    const data = await res.json().catch(() => ({}));
    if (res.ok && data.access_token) {
      localStorage.setItem("kisanToken", data.access_token);
      localStorage.setItem("kisanAuth", "true");
      if (data.user) {
        localStorage.setItem("kisanUser", JSON.stringify(data.user));
      }
      const sessionObj = {
        access_token: data.access_token,
        token_type: data.token_type || "bearer",
        user: data.user,
      };
      return { session: sessionObj, user: data.user };
    }

    if (res.status === 400 || res.status === 401 || res.status === 429) {
      const errMsg =
        data.detail?.error?.message ||
        (typeof data.detail === "string" ? data.detail : "Incorrect verification code.");
      return { session: null, user: null, error: errMsg };
    }

    // 2. Secondary fallback: Supabase Auth
    const { data: supaData, error: supaErr } = await supabase.auth.verifyOtp({
      phone,
      token: cleanToken,
      type: "sms",
    });

    if (supaErr) {
      const msg = supaErr.message?.toLowerCase() || "";
      if (msg.includes("expired")) {
        return { session: null, user: null, error: "This OTP has expired. Please request a new code." };
      }
      if (msg.includes("invalid") || msg.includes("token")) {
        return { session: null, user: null, error: "Incorrect verification code. Please check and try again." };
      }
      if (msg.includes("rate") || supaErr.status === 429) {
        return { session: null, user: null, error: "Too many failed attempts. Please wait a few minutes." };
      }
      return { session: null, user: null, error: "Verification failed. Please check the code and try again." };
    }

    return { session: supaData.session, user: supaData.user };
  } catch {
    return { session: null, user: null, error: "Network error during verification. Please try again." };
  }
}

export async function checkUserOnboardingStatus(userId: string): Promise<"complete" | "draft" | "none"> {
  try {
    const { data, error } = await supabase
      .from("farmer_profiles")
      .select("onboarding_status")
      .eq("user_id", userId)
      .maybeSingle();

    if (error || !data) return "none";
    return data.onboarding_status === "complete" ? "complete" : "draft";
  } catch {
    return "none";
  }
}

export async function signInWithEmail(email: string) {
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
  });
  if (error) throw error;
}

export async function signOut() {
  clearLocalAuthStorage();
  await supabase.auth.signOut();
}
