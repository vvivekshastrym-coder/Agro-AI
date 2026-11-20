import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import {
  signInWithPhone,
  verifyPhoneOtp,
  signInWithEmail,
  maskPhone,
  checkUserOnboardingStatus,
  formatOAuthError,
} from "../lib/useAuth";
import { getDictionary, SUPPORTED_LANGUAGES, type LanguageCode } from "../lib/i18n";
import { useApp } from "../lib/AppContext";
import { AgroLogo } from "../components/AgroLogo";

export default function Login() {
  const navigate = useNavigate();
  const { language, setLanguage } = useApp();
  const [langCode, setLangCode] = useState<LanguageCode>(() => {
    if (language?.toLowerCase().startsWith("kn")) return "kn";
    if (language?.toLowerCase().startsWith("hi")) return "hi";
    if (language?.toLowerCase().startsWith("te")) return "te";
    if (language?.toLowerCase().startsWith("ta")) return "ta";
    return "en";
  });

  const t = getDictionary(langCode);

  // Screen state: "phone" | "otp" | "email"
  const [mode, setMode] = useState<"phone" | "otp" | "email">("phone");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [emailSent, setEmailSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // OTP State: 6 digit array
  const [otpDigits, setOtpDigits] = useState<string[]>(["", "", "", "", "", ""]);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // 30s resend timer
  const [resendTimer, setResendTimer] = useState(30);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (mode === "otp" && resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [mode, resendTimer]);

  const handleLanguageChange = (code: string) => {
    setLangCode(code as LanguageCode);
    const langObj = SUPPORTED_LANGUAGES.find((l: { code: string; label: string; native: string }) => l.code === code);
    if (langObj) {
      setLanguage(langObj.label.split(" ")[0]);
    }
  };

  // Format 10 digit input
  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, "").slice(0, 10);
    setPhone(raw);
    setError(null);
  };

  // Send OTP
  async function handleSendOtp(e?: React.FormEvent) {
    if (e) e.preventDefault();
    setError(null);
    if (phone.length < 10) {
      setError(t.errGeneric);
      return;
    }

    setLoading(true);
    const res = await signInWithPhone(phone);
    setLoading(false);

    if (res.error) {
      setError(res.error);
    } else {
      setMode("otp");
      setResendTimer(30);
      setOtpDigits(["", "", "", "", "", ""]);
      setTimeout(() => inputRefs.current[0]?.focus(), 150);
    }
  }

  // Handle single digit in OTP box
  const handleOtpChange = (index: number, val: string) => {
    setError(null);
    const digitsOnly = val.replace(/\D/g, "");
    if (!digitsOnly) {
      const next = [...otpDigits];
      next[index] = "";
      setOtpDigits(next);
      return;
    }

    // Single digit input
    const char = digitsOnly.slice(-1);
    const next = [...otpDigits];
    next[index] = char;
    setOtpDigits(next);

    // Auto advance to next box
    if (index < 5 && char) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto verify if all 6 digits entered
    const joined = next.join("");
    if (joined.length === 6) {
      submitOtpCode(joined);
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otpDigits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  // Paste support for 6 digits
  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (!pasted) return;

    const next = ["", "", "", "", "", ""];
    for (let i = 0; i < pasted.length; i++) {
      next[i] = pasted[i];
    }
    setOtpDigits(next);

    if (pasted.length === 6) {
      submitOtpCode(pasted);
    } else {
      inputRefs.current[pasted.length]?.focus();
    }
  };

  // Submit OTP
  async function submitOtpCode(code: string) {
    setError(null);
    setLoading(true);

    const { user, error: verifyErr } = await verifyPhoneOtp(phone, code);
    setLoading(false);

    if (verifyErr || !user) {
      setError(verifyErr || t.errGeneric);
      return;
    }

    // After verification: if the user has no completed profile, go to onboarding; otherwise go to returnTo or Home.
    const status = await checkUserOnboardingStatus(user.id);
    if (status === "complete") {
      const returnTo = sessionStorage.getItem("agro_return_to");
      if (returnTo) {
        sessionStorage.removeItem("agro_return_to");
        navigate(returnTo, { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } else {
      navigate("/onboarding", { replace: true });
    }
  }

  // Resend OTP
  async function handleResendOtp() {
    if (resendTimer > 0 || loading) return;
    setError(null);
    setLoading(true);
    const res = await signInWithPhone(phone);
    setLoading(false);
    if (res.error) {
      setError(res.error);
    } else {
      setResendTimer(30);
      setOtpDigits(["", "", "", "", "", ""]);
      inputRefs.current[0]?.focus();
    }
  }

  // Email Magic Link submission
  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signInWithEmail(email);
      setEmailSent(true);
    } catch (err: any) {
      setError(err?.message || t.errGeneric);
    } finally {
      setLoading(false);
    }
  }

  // Google OAuth Sign-In via Supabase Auth
  const handleGoogleSignIn = async () => {
    setError(null);
    setLoading(true);

    try {
      const redirectUrl = `${window.location.origin}/auth/callback`;

      const { error: oauthErr } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: redirectUrl,
          queryParams: {
            prompt: "select_account",
          },
        },
      });

      if (oauthErr) {
        throw oauthErr;
      }
    } catch (err) {
      console.error("Google OAuth error:", err);
      setError(formatOAuthError(err));
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full min-w-0 overflow-x-clip bg-cream lg:grid lg:grid-cols-[1.05fr_1fr]">
      <aside className="hidden flex-col justify-center bg-gradient-to-br from-forest to-forest-deep p-12 text-white xl:p-16 lg:flex">
        <div className="mx-auto w-full max-w-xl">
          <div className="mb-10 flex items-center gap-3 text-2xl font-bold"><span className="text-4xl">🌾</span> Agro AI</div>
          <h1 className="font-display text-4xl font-bold leading-tight xl:text-5xl">The AI team every farmer deserves.</h1>
          <p className="mt-5 max-w-lg text-lg text-white/80">Practical guidance for every season, in the language you speak.</p>
          <ul className="mt-10 space-y-4 text-base text-white/90">
            <li>✓ Crop health guidance from a leaf photo</li>
            <li>✓ Local weather and farming advisories</li>
            <li>✓ Market insights for your crops</li>
          </ul>
        </div>
      </aside>
      <section className="flex min-h-screen w-full min-w-0 flex-col justify-between px-5 py-6 font-sans lg:px-10 xl:px-16">
      {/* Top Header with Language Selector */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-forest text-white flex items-center justify-center text-sm font-bold shadow-sm">
            🌾
          </div>
          <span className="font-display text-lg font-bold text-forest">Agro AI</span>
        </div>

        <div className="flex min-w-0 flex-1 justify-end gap-1 overflow-x-auto no-scrollbar lg:flex-none">
          {SUPPORTED_LANGUAGES.map((l: { code: string; label: string; native: string }) => (
            <button
              key={l.code}
              onClick={() => handleLanguageChange(l.code)}
              className={`text-xs px-2.5 py-1 rounded-full font-medium transition-colors ${
                langCode === l.code ? "bg-forest text-white" : "bg-white text-ink-soft border border-line"
              }`}
            >
              {l.native}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="my-auto w-full min-w-0 py-8 lg:mx-auto lg:max-w-[440px] lg:rounded-[28px] lg:border lg:border-line lg:bg-white lg:p-10 lg:shadow-soft">
        {mode === "phone" && (
          <div>
            {/* Logo and Tagline */}
            <div className="text-center mb-6">
              <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-white border-2 border-forest flex items-center justify-center shadow-md overflow-hidden">
                <AgroLogo className="w-full h-full object-cover" textClassName="text-sm font-bold text-forest" />
              </div>
              <h1 className="font-display text-2xl font-bold text-forest tracking-tight">Agro AI</h1>
              <p className="text-ink-soft text-sm mt-2 px-4 leading-relaxed font-medium">{t.tagline}</p>
            </div>

            {/* Google Sign-In */}
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 rounded-full border border-line bg-white py-3.5 px-4 text-sm font-bold text-ink shadow-sm hover:bg-cream active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="#4285F4"
                  d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
                />
                <path
                  fill="#34A853"
                  d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.11-6.72-4.96H1.29v3.14C3.26 21.3 7.31 24 12 24Z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.28 14.24c-.24-.72-.38-1.49-.38-2.24s.14-1.52.38-2.24V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.99-3.14Z"
                />
                <path
                  fill="#EA4335"
                  d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.99 3.14c.95-2.85 3.6-4.96 6.72-4.96Z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>

            <div className="relative my-5 flex items-center">
              <div className="flex-grow border-t border-line" />
              <span className="mx-3 shrink-0 text-xs font-medium text-ink-soft">or continue with phone</span>
              <div className="flex-grow border-t border-line" />
            </div>

            {/* Phone Form */}
            <form onSubmit={handleSendOtp} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-semibold text-ink-soft uppercase tracking-wider mb-2">
                  {t.phoneLabel}
                </label>
                <div className="flex items-center bg-white border border-line rounded-2xl px-4 py-3.5 shadow-sm focus-within:border-forest transition-colors">
                  <span className="font-bold text-forest text-base mr-3 select-none">+91</span>
                  <input
                    type="tel"
                    inputMode="numeric"
                    autoComplete="tel-national"
                    value={phone}
                    onChange={handlePhoneChange}
                    placeholder={t.phonePlaceholder}
                    className="w-full text-base font-semibold text-ink outline-none bg-transparent"
                    autoFocus
                  />
                </div>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl p-3 leading-relaxed">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || phone.length < 10}
                className="w-full bg-forest text-white rounded-full py-4 text-base font-bold shadow-md hover:bg-forest-deep active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none mt-2"
              >
                {loading ? "..." : t.continueBtn}
              </button>

              <div className="text-center mt-3">
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setMode("email");
                  }}
                  className="text-xs text-forest font-semibold hover:underline"
                >
                  {t.emailOption}
                </button>
              </div>
            </form>
          </div>
        )}

        {mode === "otp" && (
          <div>
            <div className="text-center mb-6">
              <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-forest/10 text-forest flex items-center justify-center text-2xl">
                📱
              </div>
              <h2 className="font-display text-2xl font-bold text-forest">{t.otpTitle}</h2>
              <p className="text-ink-soft text-xs mt-1">{t.otpSubtitle}</p>
              <div className="mt-2 inline-flex items-center gap-2 bg-white border border-line rounded-full px-3 py-1 text-xs">
                <span className="text-ink-soft">{t.otpMaskedPrefix}</span>
                <strong className="text-forest font-bold">{maskPhone(phone)}</strong>
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setMode("phone");
                  }}
                  className="text-saffron-dark font-bold underline ml-1"
                >
                  {t.changeNumber}
                </button>
              </div>
            </div>

            {/* 6 separate OTP input boxes */}
            <div className="flex justify-center gap-2 sm:gap-3 my-6">
              {otpDigits.map((digit, idx) => (
                <input
                  key={idx}
                  ref={(el) => (inputRefs.current[idx] = el)}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleOtpChange(idx, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                  onPaste={handleOtpPaste}
                  className="w-12 h-14 sm:w-13 sm:h-15 text-center text-2xl font-bold rounded-2xl border-2 border-line bg-white focus:border-forest focus:outline-none shadow-sm transition-all"
                />
              ))}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl p-3 leading-relaxed mb-4 text-center">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={() => submitOtpCode(otpDigits.join(""))}
              disabled={loading || otpDigits.join("").length !== 6}
              className="w-full bg-forest text-white rounded-full py-4 text-base font-bold shadow-md hover:bg-forest-deep active:scale-[0.98] transition-all disabled:opacity-50"
            >
              {loading ? t.verifyingBtn : t.verifyBtn}
            </button>

            {/* 30-Second Resend Countdown */}
            <div className="text-center mt-5 text-xs text-ink-soft">
              {resendTimer > 0 ? (
                <span>
                  {t.resendPrefix} <strong className="text-forest font-bold">00:{resendTimer < 10 ? `0${resendTimer}` : resendTimer}</strong>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={loading}
                  className="text-forest font-bold underline hover:text-forest-deep"
                >
                  {t.resendAction}
                </button>
              )}
            </div>
          </div>
        )}

        {mode === "email" && (
          <div>
            <div className="text-center mb-6">
              <h2 className="font-display text-2xl font-bold text-forest">{t.emailOption}</h2>
              <p className="text-ink-soft text-xs mt-1">Receive a secure login link via email.</p>
            </div>

            {emailSent ? (
              <div className="bg-leaf-pale text-forest rounded-3xl p-5 text-sm text-center border border-leaf">
                {t.checkEmailMsg} (<strong>{email}</strong>)
              </div>
            ) : (
              <form onSubmit={handleEmailSubmit} className="flex flex-col gap-3">
                <input
                  type="email"
                  required
                  placeholder={t.emailPlaceholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border border-line rounded-2xl px-4 py-3.5 text-sm bg-white"
                />
                {error && <div className="text-xs text-red-700">{error}</div>}
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-forest text-white rounded-full py-3.5 text-sm font-semibold disabled:opacity-50"
                >
                  {loading ? "..." : t.sendLinkBtn}
                </button>
              </form>
            )}

            <div className="text-center mt-4">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setMode("phone");
                }}
                className="text-xs text-forest font-semibold hover:underline"
              >
                ← {t.phoneOption}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer Terms & Privacy */}
      <div className="text-center text-[11px] text-ink-soft pt-4 border-t border-line/60">
        <p className="leading-relaxed">
          {t.termsNotice}{" "}
          <a href="#" className="underline text-forest font-semibold">
            {t.termsLink}
          </a>{" "}
          ·{" "}
          <a href="#" className="underline text-forest font-semibold">
            {t.privacyLink}
          </a>
        </p>
      </div>
      </section>
    </div>
  );
}
