import { Navigate, Route, Routes } from "react-router-dom";
import { AppProvider } from "./lib/AppContext";
import { useAuth } from "./lib/useAuth";
import { DesktopHeader, Sidebar, TopBar, BottomNav } from "./components/Shell";
import Login from "./pages/Login";
import Onboarding from "./pages/Onboarding";
import FarmerProfile from "./pages/FarmerProfile";
import Home from "./pages/Home";
import Diagnose from "./pages/Diagnose";
import AgroGPT from "./pages/AgroGPT";
import Weather from "./pages/Weather";
import Market from "./pages/Market";
import PestRadar from "./pages/PestRadar";
import More from "./pages/More";

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
            <Route path="/profile" element={<FarmerProfile />} />
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
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/*" element={<MainLayout />} />
    </Routes>
  );
}

export default function App() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-cream text-forest text-sm gap-2">
        <div className="w-8 h-8 border-3 border-forest border-t-transparent rounded-full animate-spin" />
        <span className="font-semibold text-xs">Agro AI loading…</span>
      </div>
    );
  }

  if (!session) {
    return (
      <AppProvider>
        <Routes>
          <Route path="*" element={<Login />} />
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
