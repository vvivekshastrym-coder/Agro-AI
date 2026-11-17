import { NavLink, useNavigate } from "react-router-dom";
import { useApp } from "../lib/AppContext";
import { signOut } from "../lib/useAuth";

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
          <span className="text-xl">🌾</span>
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

const TABS = [
  { to: "/", label: "Home", icon: "🏠", end: true },
  { to: "/diagnose", label: "Diagnose", icon: "🍃" },
  { to: "/agro-gpt", label: "Agro GPT", icon: "💬" },
  { to: "/weather", label: "Weather", icon: "🌦️" },
  { to: "/more", label: "More", icon: "☰" }
];

export function BottomNav() {
  return (
    <nav className="sticky bottom-0 left-0 right-0 bg-white border-t border-line flex justify-around pt-2 pb-[calc(0.6rem+env(safe-area-inset-bottom))] z-20 shadow-md">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 text-[10.5px] font-semibold ${
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
