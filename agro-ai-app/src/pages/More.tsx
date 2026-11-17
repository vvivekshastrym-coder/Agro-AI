import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "../lib/AppContext";
import { calculateProfileCompletion } from "../lib/farmerProfile";

const ITEMS = [
  { icon: "🌾", label: "Mandi Market", tier: "Must-have · live", to: "/market" },
  { icon: "🐛", label: "Pest Radar", tier: "Must-have · live", to: "/pest-radar" },
  { icon: "🛒", label: "Inputs Compare", tier: "Growth", desc: "Agri-shop price comparison for seeds, fertilizer and pesticide — cheapest vendor, savings %, dosage advice." },
  { icon: "🚚", label: "Logistics", tier: "Growth", desc: "“Ola for trucks” — harvest transport matching with pickup village, destination mandi, tonnage and ETA." },
  { icon: "💳", label: "Credit Score", tier: "Growth", desc: "Credit scoring for unbanked farmers using crop history, satellite NDVI and mandi sales." },
  { icon: "🚁", label: "Drone Marketplace", tier: "Growth", desc: "Book drone pilots for spraying, scouting or NDVI mapping by acreage and service type." },
  { icon: "🛰️", label: "Satellite Twin", tier: "Growth", desc: "Digital twin of your field from Sentinel-2 NDVI — false-colour map, timeline, stress alerts." },
  { icon: "🌍", label: "Carbon Credits", tier: "Year 2", desc: "Passive income for sustainable practices — estimated tCO₂e/year and payout calculator." },
  { icon: "🛡️", label: "Auto Insurance", tier: "Year 2", desc: "Weather-triggered parametric crop insurance with zero claim friction and instant payout." },
  { icon: "🧪", label: "Soil DNA Lab", tier: "Year 2", desc: "Mail-in soil microbiome test kit with lab-based prescription report." },
  { icon: "🪪", label: "Farm Passport", tier: "Year 2", desc: "Blockchain provenance for premium buyers — QR code, batch timeline, certifications." }
];

export default function More() {
  const navigate = useNavigate();
  const { profile, farms } = useApp();
  const [soon, setSoon] = useState<{ label: string; desc: string } | null>(null);

  const completion = calculateProfileCompletion(profile, farms);

  return (
    <div className="p-4 flex flex-col gap-4">
      <div>
        <div className="text-xs text-ink-soft">More</div>
        <h2 className="text-xl font-semibold text-forest">All Agro AI services</h2>
      </div>

      {/* Featured Farmer Profile Card */}
      <div
        onClick={() => navigate("/profile")}
        className="p-4 rounded-3xl bg-forest text-sand shadow-sm cursor-pointer hover:bg-forest-light transition-all flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-2xl">
            👨‍🌾
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-sand/80">
              Farmer Profile (ರೈತರ ಪ್ರೊಫೈಲ್)
            </div>
            <div className="text-base font-bold text-white">
              {profile?.full_name || "Your Farm Profile"}
            </div>
            <div className="text-xs text-sand/80">
              {profile?.village ? `${profile.village}, ${profile.district}` : "Manage land, crops & account"}
              {" · "}
              <span className="font-bold">{completion.percentage}% complete</span>
            </div>
          </div>
        </div>
        <span className="text-lg font-bold">→</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {ITEMS.map((it) => (
          <div
            key={it.label}
            onClick={() => (it.to ? navigate(it.to) : setSoon({ label: it.label, desc: it.desc! }))}
            className="relative bg-white rounded-3xl p-3.5 shadow-soft border border-line cursor-pointer hover:border-forest/30 transition-all"
          >
            {!it.to && (
              <span className="absolute top-2.5 right-2.5 bg-saffron-pale text-[#8A4E0F] text-[9.5px] font-bold px-1.5 py-0.5 rounded-full">
                Soon
              </span>
            )}
            <span className="text-xl">{it.icon}</span>
            <div className="text-sm font-semibold mt-1.5">{it.label}</div>
            <div className="text-[10.5px] text-ink-soft mt-0.5">{it.tier}</div>
          </div>
        ))}
      </div>

      {soon && (
        <div className="fixed inset-0 bg-black/40 flex items-end justify-center z-50" onClick={() => setSoon(null)}>
          <div className="bg-cream w-full max-w-[430px] rounded-t-4xl p-5 pb-8" onClick={(e) => e.stopPropagation()}>
            <div className="w-10 h-1 bg-line rounded-full mx-auto mb-4" />
            <h3 className="font-display text-lg mb-2">{soon.label}</h3>
            <p className="text-sm text-ink-soft">
              {soon.desc} This module is on the Year-2/Growth roadmap and isn't wired to live data yet.
            </p>
            <button onClick={() => setSoon(null)} className="mt-4 w-full bg-forest text-white rounded-full py-2.5 text-sm font-semibold">
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
