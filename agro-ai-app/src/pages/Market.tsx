import { useEffect, useState } from "react";
import { mandiPrice } from "../lib/ai";
import { useApp } from "../lib/AppContext";

const CROPS = ["Ragi", "Wheat", "Paddy", "Maize", "Tomato", "Onion", "Sugarcane", "Cotton"];
const STATES = ["Karnataka", "Maharashtra", "Punjab", "Uttar Pradesh", "Tamil Nadu", "Andhra Pradesh"];

export default function Market() {
  const { language, profile, crops } = useApp();

  // Mandi defaults to the first saved crop and state from profile
  const initialCrop = crops.length > 0 ? crops[0].crop_name : CROPS[0];
  const initialState = profile?.state || STATES[0];

  const [crop, setCrop] = useState(initialCrop);
  const [state, setState] = useState(initialState);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ available: boolean; price?: string; trend?: string; summary: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sync state & crop when profile/crops become available
  useEffect(() => {
    if (crops.length > 0 && !crops.some((c) => c.crop_name.toLowerCase() === crop.toLowerCase())) {
      setCrop(crops[0].crop_name);
    }
  }, [crops]);

  useEffect(() => {
    if (profile?.state && profile.state !== state) {
      setState(profile.state);
    }
  }, [profile?.state]);

  async function getForecast() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await mandiPrice(crop, state, language);
      setResult(res);
    } catch {
      setError("Live data unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // Pre-load forecast on mount
  useEffect(() => {
    getForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crop, state]);

  // Combine default crops with user's saved crops
  const allCrops = Array.from(new Set([...crops.map((c) => c.crop_name), ...CROPS]));
  const allStates = Array.from(new Set([profile?.state, ...STATES].filter(Boolean) as string[]));

  return (
    <div className="p-4 flex flex-col gap-4">
      <div>
        <div className="text-xs text-ink-soft">/market</div>
        <h2 className="text-xl font-semibold text-forest">Mandi Market</h2>
        {crops.length > 0 && (
          <p className="text-xs text-forest mt-0.5">
            Defaulted to your farm crop: <span className="font-bold">{crops[0].crop_name}</span> ({profile?.state || "Karnataka"})
          </p>
        )}
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-soft border border-line">
        <div className="flex gap-2">
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
            className="flex-1 border border-line rounded-full px-4 py-2.5 text-sm bg-cream"
          >
            {allCrops.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="flex-1 border border-line rounded-full px-4 py-2.5 text-sm bg-cream"
          >
            {allStates.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={getForecast}
          disabled={loading}
          className="mt-3 w-full bg-saffron text-[#3A2408] rounded-full py-2.5 text-sm font-semibold disabled:opacity-50 hover:opacity-90 active:scale-95 transition-all"
        >
          {loading ? "Fetching…" : "Get forecast"}
        </button>

        {error && <div className="mt-3 text-sm text-red-700">{error}</div>}

        {result && (
          <div className="mt-4">
            {result.available ? (
              <>
                <div className="text-center mb-3">
                  <div className="font-display text-3xl font-bold text-saffron">{result.price}</div>
                  <span className="inline-block mt-1.5 bg-leaf-pale text-forest rounded-full px-3 py-1 text-xs font-semibold">
                    {result.trend}
                  </span>
                </div>
                <p className="text-sm leading-relaxed">{result.summary}</p>
              </>
            ) : (
              <p className="text-sm text-ink-soft italic">{result.summary}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
