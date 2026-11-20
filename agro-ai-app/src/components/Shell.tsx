import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useApp } from "../lib/AppContext";
import { signOut } from "../lib/useAuth";
import { AgroLogo } from "./AgroLogo";

const LANGS = [
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "te", label: "తెలుగు" },
  { code: "ta", label: "தமிழ்" }
];

export function TopBar() {
  const { language, setLanguage, profile } = useApp();
  const navigate = useNavigate();

  return (
    <>
      <div className="flex items-center justify-between px-4 pt-3.5 pb-2.5 bg-forest text-white">
        <div
          onClick={() => navigate("/")}
          className="flex items-center gap-2 cursor-pointer"
        >
          <AgroLogo className="w-7 h-7 rounded-full object-cover border border-white/30" textClassName="text-xs font-bold text-white" />
          <span className="font-display font-bold text-lg tracking-tight">Agro AI</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/profile")}
            className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 active:scale-95 border border-white/20 rounded-full px-3 py-1 text-xs text-[#EAF1E5] transition-all"
          >
            <span>👨‍🌾</span>
            <span className="max-w-[100px] truncate font-semibold">
              {profile?.full_name ? profile.full_name.split(" ")[0] : "Profile"}
            </span>
          </button>
          <button
            onClick={async () => {
              await signOut();
              navigate("/login");
            }}
            className="text-[11px] bg-white/10 border border-white/20 rounded-full px-2.5 py-1 text-sand hover:bg-white/20 active:scale-95 transition-all"
            title="Sign out"
          >
            Exit
          </button>
        </div>
      </div>

      {/* Language pill bar */}
      <div className="flex gap-2 overflow-x-auto no-scrollbar px-4 py-2 bg-forest-deep">
        {LANGS.map((l) => (
          <button
            key={l.code}
            onClick={() => setLanguage(l.code)}
            className={`flex-shrink-0 rounded-full px-3 py-1 text-xs font-semibold transition-all ${
              language === l.code || (l.code === "kn" && language.toLowerCase().includes("kannada")) || (l.code === "en" && language.toLowerCase().includes("english"))
                ? "bg-saffron text-[#3A2408]"
                : "bg-white/10 text-[#CFE0C9] hover:bg-white/15"
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
    </>
  );
}

const DESKTOP_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/diagnose", label: "Diagnose" },
  { to: "/agro-gpt", label: "Kisan GPT" },
  { to: "/weather", label: "Weather" },
  { to: "/market", label: "Mandi Market" },
  { to: "/pest-radar", label: "Pest Radar" },
  { to: "/more", label: "More" }
];

export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen flex-col bg-forest-deep p-4 text-white lg:flex">
      <NavLink to="/" className="flex items-center gap-2.5 px-3 pb-7 pt-2 font-display text-xl font-bold">
        <AgroLogo className="w-8 h-8 rounded-full object-cover border border-white/25" textClassName="text-xs font-bold text-white" />
        <span>Agro AI</span>
      </NavLink>
      <nav aria-label="Main navigation" className="flex flex-col gap-1">
        {DESKTOP_LINKS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            aria-label={item.label}
            className={({ isActive }) => `min-h-11 rounded-xl px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-saffron ${isActive ? "bg-white text-forest" : "text-[#CFE3D1] hover:bg-white/10"}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <NavLink to="/profile" className={({ isActive }) => `mt-auto min-h-11 rounded-xl px-4 py-3 text-sm font-semibold hover:bg-white/10 ${isActive ? "bg-white text-forest" : "text-[#CFE3D1]"}`}>
        Account and security
      </NavLink>
    </aside>
  );
}

export function DesktopHeader() {
  const { language, setLanguage, profile } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const title = DESKTOP_LINKS.find((item) => item.to === location.pathname)?.label ?? "Account and security";

  return (
    <header className="hidden items-center justify-between border-b border-line bg-cream/95 px-8 py-4 backdrop-blur lg:flex">
      <h1 className="font-display text-xl font-bold text-forest">{title}</h1>
      <div className="flex items-center gap-4">
        <label className="sr-only" htmlFor="desktop-language">Language</label>
        <select id="desktop-language" value={language} onChange={(event) => setLanguage(event.target.value)} className="min-h-11 rounded-full border border-line bg-white px-3 text-sm text-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest">
          {LANGS.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
        </select>
        <button onClick={() => navigate("/profile")} className="min-h-11 rounded-full border border-line bg-white px-4 text-sm font-semibold text-forest hover:bg-leaf-pale focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest">
          {profile?.full_name || "Account"}
        </button>
      </div>
    </header>
  );
}

const TABS = [
  { to: "/", label: "Home", icon: "🏠", end: true },
  { to: "/diagnose", label: "Diagnose", icon: "🍃" },
  { to: "/agro-gpt", label: "Agro GPT", icon: "💬" },
  { to: "/weather", label: "Weather", icon: "🌦️" },
  { to: "/more", label: "More", icon: "☰" }
];

export function BottomNav() {
  return (
    <nav aria-label="Main navigation" className="bg-white border-t border-line flex justify-around pt-2 pb-[calc(0.6rem+env(safe-area-inset-bottom))] z-20 shadow-md">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `min-h-11 min-w-11 flex flex-col items-center justify-center gap-0.5 text-[10.5px] font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-forest ${
              isActive ? "text-forest" : "text-ink-soft"
            }`
          }
        >
          <span className="text-lg">{t.icon}</span>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
