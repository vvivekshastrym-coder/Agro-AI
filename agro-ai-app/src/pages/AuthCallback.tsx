import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Session } from "@supabase/supabase-js";
import { supabase, isSupabaseConfigured } from "../lib/supabaseClient";
import { checkUserOnboardingStatus, formatOAuthError } from "../lib/useAuth";

export default function AuthCallback() {
  const navigate = useNavigate();
  const completedRef = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let subscription: { unsubscribe: () => void } | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const cleanCallbackUrl = () => {
      if (window.location.search || window.location.hash) {
        window.history.replaceState({}, document.title, "/auth/callback");
      }
    };

    const finalizeSession = async (session: Session) => {
      if (completedRef.current || !active) return;
      completedRef.current = true;
      subscription?.unsubscribe();
      if (timeoutId) clearTimeout(timeoutId);

      // Safe to strip authorization code/tokens from URL now that session is established
      cleanCallbackUrl();

      try {
        const onboardingStatus = await checkUserOnboardingStatus(session.user.id);
        if (!active) return;
        if (onboardingStatus === "complete") {
          navigate("/", { replace: true });
        } else {
          navigate("/onboarding", { replace: true });
        }
      } catch (err) {
        console.error("Onboarding status lookup error:", err);
        if (active) {
          navigate("/onboarding", { replace: true });
        }
      }
    };

    async function processCallback() {
      if (!isSupabaseConfigured) {
        if (active) {
          setErrorMessage("Authentication service is not configured. Please contact support.");
        }
        return;
      }

      const searchParams = new URLSearchParams(window.location.search);
      const hashRaw = window.location.hash.startsWith("#")
        ? window.location.hash.slice(1)
        : window.location.hash;
      const hashParams = new URLSearchParams(hashRaw);

      const oauthError = searchParams.get("error") || hashParams.get("error");
      const oauthErrorDesc =
        searchParams.get("error_description") || hashParams.get("error_description");

      if (oauthError) {
        cleanCallbackUrl();
        console.error("OAuth callback error:", oauthError);
        if (active) {
          setErrorMessage(formatOAuthError(oauthError, oauthErrorDesc));
        }
        return;
      }

      // Listen for Supabase's automatic detectSessionInUrl completion
      const { data: authListener } = supabase.auth.onAuthStateChange((event, nextSession) => {
        if (!active || completedRef.current) return;
        if ((event === "SIGNED_IN" || event === "INITIAL_SESSION") && nextSession?.user) {
          void finalizeSession(nextSession);
        }
      });
      subscription = authListener.subscription;

      try {
        // Check if Supabase already hydrated the session from the URL
        const { data, error: sessionErr } = await supabase.auth.getSession();
        if (sessionErr) {
          throw sessionErr;
        }
        if (data.session?.user) {
          await finalizeSession(data.session);
          return;
        }

        // Wait up to 10s for automatic PKCE exchange to finish if ?code= or #access_token= is present
        const hasAuthPayload =
          searchParams.has("code") ||
          hashParams.has("access_token") ||
          hashParams.has("refresh_token");

        if (!hasAuthPayload) {
          if (active && !completedRef.current) {
            cleanCallbackUrl();
            setErrorMessage(
              "No active sign-in session was found. Please try signing in with Google again."
            );
          }
          return;
        }

        timeoutId = setTimeout(() => {
          if (!active || completedRef.current) return;
          completedRef.current = true;
          subscription?.unsubscribe();
          cleanCallbackUrl();
          setErrorMessage(
            "Sign-in timed out while verifying your Google session. Please try again."
          );
        }, 10000);
      } catch (err) {
        console.error("Auth callback session error:", err);
        if (active && !completedRef.current) {
          completedRef.current = true;
          subscription?.unsubscribe();
          cleanCallbackUrl();
          setErrorMessage(formatOAuthError(err));
        }
      }
    }

    void processCallback();

    return () => {
      active = false;
      subscription?.unsubscribe();
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [navigate]);

  if (errorMessage) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-cream px-5 py-8 font-sans">
        <div className="w-full max-w-md rounded-3xl border border-line bg-white p-8 text-center shadow-soft">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-2xl">
            ⚠️
          </div>
          <h1 className="font-display text-xl font-bold text-forest">Sign-In Could Not Complete</h1>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">{errorMessage}</p>
          <button
            type="button"
            onClick={() => navigate("/login", { replace: true })}
            className="mt-6 w-full rounded-full bg-forest py-3.5 text-sm font-bold text-white shadow-md hover:bg-forest-deep transition-colors"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-cream px-5 text-forest gap-3 font-sans">
      <div className="w-9 h-9 border-3 border-forest border-t-transparent rounded-full animate-spin" />
      <p className="text-sm font-semibold">Completing your Agro AI sign-in…</p>
    </div>
  );
}
