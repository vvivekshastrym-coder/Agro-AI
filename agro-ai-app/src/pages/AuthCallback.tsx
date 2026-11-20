import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase, isSupabaseConfigured } from "../lib/supabaseClient";
import { checkUserOnboardingStatus, formatOAuthError } from "../lib/useAuth";

export default function AuthCallback() {
  const navigate = useNavigate();
  const processedRef = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    let active = true;

    async function completeAuth() {
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
      const authCode = searchParams.get("code");

      // Immediately clean any OAuth query/hash tokens from the browser URL bar
      if (window.location.search || window.location.hash) {
        window.history.replaceState({}, document.title, "/auth/callback");
      }

      if (oauthError) {
        console.error("OAuth callback error:", oauthError);
        if (active) {
          setErrorMessage(formatOAuthError(oauthError, oauthErrorDesc));
        }
        return;
      }

      try {
        // 1. Check if Supabase's detectSessionInUrl already hydrated the session
        let { data, error: sessionErr } = await supabase.auth.getSession();

        if (sessionErr) {
          throw sessionErr;
        }

        // 2. If PKCE ?code= was present and session is not yet ready, exchange it explicitly
        if (!data.session && authCode) {
          const { data: exchangeData, error: exchangeErr } =
            await supabase.auth.exchangeCodeForSession(authCode);
          if (exchangeErr) {
            // Re-check getSession in case detectSessionInUrl finished concurrently
            const retry = await supabase.auth.getSession();
            if (retry.data.session) {
              data = retry.data;
            } else {
              throw exchangeErr;
            }
          } else {
            data = { session: exchangeData.session };
          }
        }

        if (!data.session?.user) {
          if (active) {
            setErrorMessage(
              "Your sign-in session could not be verified or has expired. Please try logging in again."
            );
          }
          return;
        }

        const onboardingStatus = await checkUserOnboardingStatus(data.session.user.id);
        if (!active) return;

        if (onboardingStatus === "complete") {
          navigate("/", { replace: true });
        } else {
          navigate("/onboarding", { replace: true });
        }
      } catch (err) {
        console.error("Auth callback processing failed:", err);
        if (active) {
          setErrorMessage(formatOAuthError(err));
        }
      }
    }

    completeAuth();

    return () => {
      active = false;
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
