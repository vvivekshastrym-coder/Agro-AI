import { Navigate, Route, Routes } from "react-router-dom";
import { AppProvider } from "./lib/AppContext";
import { useAuth } from "./lib/useAuth";
import { TopBar, BottomNav } from "./components/Shell";
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
    <div className="max-w-[430px] mx-auto min-h-screen bg-cream flex flex-col">
      <TopBar />
      <div className="flex-1 pb-2">
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
      </div>
      <BottomNav />
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
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }

  return (
    <AppProvider>
      <AuthenticatedRoutes />
    </AppProvider>
  );
}
