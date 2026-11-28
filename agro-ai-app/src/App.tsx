import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppProvider } from "./lib/AppContext";
import { AuthProvider, useAuth } from "./lib/useAuth";
import { DesktopHeader, Sidebar, TopBar, BottomNav } from "./components/Shell";
import { AgroLogo } from "./components/AgroLogo";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import Onboarding from "./pages/Onboarding";
import FarmerProfile from "./pages/FarmerProfile";
import Home from "./pages/Home";
import Diagnose from "./pages/Diagnose";
import AgroGPT from "./pages/AgroGPT";
import Weather from "./pages/Weather";
import Market from "./pages/Market";
import PestRadar from "./pages/PestRadar";
import More from "./pages/More";
import DroneServices from "./pages/DroneServices";

function hasOAuthUrlParams(): boolean {
  const search = window.location.search || "";
  const hash = window.location.hash || "";
  return (
    window.location.pathname === "/auth/callback" ||
    search.includes("code=") ||
    search.includes("error=") ||
    search.includes("error_description=") ||
    hash.includes("access_token=") ||
    hash.includes("error=") ||
    hash.includes("error_description=")
  );
}

function SplashScreen({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    try {
      sessionStorage.setItem("agro_splash_shown", "1");
    } catch {
      // ignore
    }
    const timer = setTimeout(onDone, 1500);
    return () => clearTimeout(timer);
  }, [onDone]);

  return (
    <div
      onClick={onDone}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onDone();
      }}
      className="fixed inset-0 z-50 flex cursor-pointer flex-col items-center justify-center bg-gradient-to-br from-forest to-forest-deep px-6 text-center text-white"
    >
      <div className="mb-5 flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border-2 border-white/30 bg-white shadow-lg">
        <AgroLogo className="h-full w-full object-cover" textClassName="text-base font-bold text-forest" />
      </div>
      <h1 className="font-display text-3xl font-bold tracking-tight">Agro AI</h1>
      <p className="mt-2 text-sm text-white/85">The AI Operating System for your Farm</p>
      <p className="mt-6 text-xs text-white/65">Tap anywhere to continue</p>
    </div>
  );
}

function MainLayout() {
  return (
    <div className="min-h-screen bg-cream lg:grid lg:grid-cols-[260px_minmax(0,1fr)]">
      <Sidebar />
      <div className="min-w-0">
        <div className="lg:hidden"><TopBar /></div>
        <DesktopHeader />
        <main className="mx-auto w-full max-w-[720px] pb-24 lg:max-w-[1180px] lg:px-8 lg:pb-12">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/diagnose" element={<Diagnose />} />
            <Route path="/agro-gpt" element={<AgroGPT />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/market" element={<Market />} />
            <Route path="/pest-radar" element={<PestRadar />} />
            <Route path="/more" element={<More />} />
            <Route path="/drone-services" element={<DroneServices />} />
            <Route path="/profile" element={<FarmerProfile />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <div className="fixed inset-x-0 bottom-0 z-20 lg:hidden"><BottomNav /></div>
    </div>
  );
}

function AuthenticatedRoutes() {
  return (
    <Routes>
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/*" element={<MainLayout />} />
    </Routes>
  );
}

function RedirectToLoginWithReturn() {
  const location = useLocation();
  useEffect(() => {
    const full = `${location.pathname}${location.search}`;
    if (full && full !== "/" && full !== "/login" && !full.startsWith("/auth/callback")) {
      try {
        sessionStorage.setItem("agro_return_to", full);
      } catch {
        // ignore
      }
    }
  }, [location.pathname, location.search]);

  return <Navigate to="/login" replace />;
}

function AppRouter() {
  const { status } = useAuth();
  const [showSplash, setShowSplash] = useState<boolean>(() => {
    if (hasOAuthUrlParams()) return false;
    try {
      return sessionStorage.getItem("agro_splash_shown") !== "1";
    } catch {
      return false;
    }
  });

  // Never show splash or login, and never redirect while auth status is loading
  if (status === "loading") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-cream text-forest text-sm gap-2">
        <div className="w-8 h-8 border-3 border-forest border-t-transparent rounded-full animate-spin" />
        <span className="font-semibold text-xs">Signing you in…</span>
      </div>
    );
  }

  if (status === "signedOut") {
    if (showSplash && !hasOAuthUrlParams()) {
      return <SplashScreen onDone={() => setShowSplash(false)} />;
    }

    return (
      <AppProvider>
        <Routes>
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<RedirectToLoginWithReturn />} />
        </Routes>
      </AppProvider>
    );
  }

  return (
    <AppProvider>
      <AuthenticatedRoutes />
    </AppProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
