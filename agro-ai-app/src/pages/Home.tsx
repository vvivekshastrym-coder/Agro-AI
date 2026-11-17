import { useNavigate } from "react-router-dom";
import { useApp } from "../lib/AppContext";
import { calculateProfileCompletion } from "../lib/farmerProfile";

const SHORTCUTS = [
  { to: "/diagnose", icon: "🍃", label: "Diagnose crop", sub: "Photo → disease + treatment" },
  { to: "/weather", icon: "🌦️", label: "Weather", sub: "5-day village forecast" },
  { to: "/market", icon: "🌾", label: "Mandi Market", sub: "Price + trend" },
  { to: "/pest-radar", icon: "🐛", label: "Pest Radar", sub: "Community reports" }
];

export default function Home() {
  const { location, setLocation, profile, farms, crops } = useApp();
  const navigate = useNavigate();

  const completion = calculateProfileCompletion(profile, farms);
  const isProfileIncomplete = !profile || profile.onboarding_status !== "complete";

  return (
    <div className="flex flex-col gap-4 p-4 lg:grid lg:grid-cols-4 lg:gap-6 lg:p-8">
      {/* Onboarding Incomplete Alert Banner */}
      {isProfileIncomplete && (
        <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-between shadow-sm animate-fade-in lg:col-span-4">
          <div>
            <p className="text-xs font-bold text-amber-900">
              🌱 Complete your Farmer Profile ({completion.percentage}%)
            </p>
            <p className="text-[11px] text-amber-700">
              Add your village, land area & crops for tailored advisories.
            </p>
          </div>
          <button
            onClick={() => navigate("/onboarding")}
            className="px-3 py-1.5 bg-forest text-sand font-bold text-xs rounded-xl shadow hover:bg-forest-light active:scale-95 transition-all whitespace-nowrap ml-2"
          >
            Setup →
          </button>
        </div>
      )}

      {/* Hero Card */}
      <div className="bg-gradient-to-br from-forest to-forest-deep text-white rounded-3xl p-5 shadow-sm lg:col-span-4 lg:p-8">
        <div className="text-xs text-[#B9CBB4] mb-1">
          {profile?.full_name ? `Namaste, ${profile.full_name} 🙏` : "Namaste 🙏"} · {profile?.village || location}
        </div>
        <h2 className="text-xl font-bold font-serif leading-snug mb-3">
          {profile?.village ? (
            <>
              Smart farming decisions for{" "}
              <span className="text-sand">{profile.village}</span>.
            </>
          ) : (
            <>
              Every rich farmer has a team.
              <br />
              Now, so do you.
            </>
          )}
        </h2>

        {crops.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {crops.map((c) => (
              <span
                key={c.crop_name}
                className="bg-white/15 text-sand text-[11px] font-semibold px-2.5 py-0.5 rounded-full"
              >
                🌱 {c.crop_name}
              </span>
            ))}
          </div>
        )}

        <button
          onClick={() => navigate("/agro-gpt")}
          className="w-full flex items-center gap-2.5 bg-white/10 hover:bg-white/15 border border-white/20 rounded-full px-4 py-2.5 text-xs text-[#EAF1E5] transition-all"
        >
          <span>🎙️</span>
          <span className="truncate">Ask Agro GPT anything about your farm…</span>
        </button>
      </div>

      {/* Quick Actions */}
      <div className="lg:col-span-4">
        <div className="text-xs font-bold text-ink-soft mb-2 uppercase tracking-wider">
          Quick actions
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {SHORTCUTS.map((s) => (
            <div
              key={s.to}
              onClick={() => navigate(s.to)}
              className="bg-white rounded-2xl p-3.5 shadow-soft border border-line flex flex-col gap-1.5 cursor-pointer hover:border-forest/30 transition-all"
            >
              <span className="text-xl">{s.icon}</span>
              <span className="text-sm font-semibold text-forest">{s.label}</span>
              <span className="text-[11px] text-ink-soft">{s.sub}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Location Setting Card */}
      <div className="bg-white rounded-2xl p-4 shadow-soft border border-line lg:col-span-2">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-xs font-bold text-forest uppercase tracking-wider">
            Your Farm Location
          </h3>
          <button
            onClick={() => navigate("/profile")}
            className="text-xs font-semibold text-forest underline hover:text-forest-light"
          >
            Manage profile
          </button>
        </div>
        <p className="text-xs text-ink-soft mb-2.5">
          Agro GPT, Weather, Market and Pest Radar automatically adapt to your village.
        </p>
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Village / district"
          className="w-full border border-line rounded-xl px-3.5 py-2 text-xs bg-cream focus:outline-none focus:ring-1 focus:ring-forest text-ink font-medium"
        />
      </div>
    </div>
  );
}
