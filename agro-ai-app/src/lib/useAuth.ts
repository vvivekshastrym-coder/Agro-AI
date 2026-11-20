import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "./supabaseClient";

export function useAuth() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const isPhoneVerified = Boolean(session?.user?.phone_confirmed_at);

  return {
    session,
    loading,
    user: session?.user ?? null,
    isPhoneVerified
  };
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
      const errMsg = data.detail?.error?.message || (typeof data.detail === "string" ? data.detail : "Incorrect verification code.");
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
    options: { emailRedirectTo: window.location.origin }
  });
  if (error) throw error;
}

export async function signOut() {
  await supabase.auth.signOut();
}
