import { useEffect, useState } from "react";
import { fetchWeather, geocode } from "../lib/ai";
import { useApp } from "../lib/AppContext";

const WCODE: Record<number, string> = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Fog", 48: "Depositing rime fog",
  51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
  61: "Light rain", 63: "Rain", 65: "Heavy rain",
  71: "Light snow", 73: "Snow", 75: "Heavy snow",
  80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
  95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ hail"
};

export default function Weather() {
  const { location, profile } = useApp();
  // Weather uses the saved village from profile
  const targetPlace = profile?.village
    ? `${profile.village}, ${profile.district || "Karnataka"}`
    : location;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [label, setLabel] = useState(targetPlace);

  async function refresh(placeToQuery?: string) {
    const query = placeToQuery || targetPlace;
    setLoading(true);
    setError(null);
    try {
      const geo = await geocode(query);
      setLabel(geo.label);
      const w = await fetchWeather(geo.lat, geo.lon);
      setData(w);
    } catch {
      // Fallback geocode to district or state if village specific fails
      try {
        const fallbackQuery = profile?.district || "Mandya, Karnataka";
        const fallbackGeo = await geocode(fallbackQuery);
        setLabel(profile?.village ? `${profile.village} (${fallbackGeo.label})` : fallbackGeo.label);
        const w = await fetchWeather(fallbackGeo.lat, fallbackGeo.lon);
        setData(w);
      } catch {
        setError("Live weather data unavailable. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh(targetPlace);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetPlace]);

  const today = data?.daily
    ? {
        max: Math.round(data.daily.temperature_2m_max[0]),
        min: Math.round(data.daily.temperature_2m_min[0]),
        rain: data.daily.precipitation_probability_max[0],
        code: data.daily.weathercode[0]
      }
    : null;

  function advisory() {
    if (!data?.daily) return "";
    const maxRain = Math.max(...data.daily.precipitation_probability_max);
    if (maxRain >= 60) return "Heavy rain likely this week — hold off on spraying and check drainage.";
    const maxTemp = Math.max(...data.daily.temperature_2m_max);
    if (maxTemp >= 38) return "High heat expected — irrigate in early morning or evening to reduce stress.";
    return "Conditions look stable — a good window for routine field work.";
  }

  return (
    <div className="p-4 flex flex-col gap-4 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:p-8">
      <div className="lg:col-span-2">
        <div className="text-xs text-ink-soft">/weather</div>
        <h2 className="text-xl font-semibold text-forest">Weather &amp; Advisory</h2>
        {profile?.village && (
          <p className="text-xs text-forest mt-0.5">
            Hyperlocal forecast for village: <span className="font-bold">{profile.village}</span>
          </p>
        )}
      </div>

      <div className="bg-gradient-to-br from-[#3D6FA8] to-[#284C77] text-white rounded-3xl p-5 shadow-sm lg:min-h-56 lg:p-8">
        <div className="text-xs text-[#D7E5F2] mb-1">{label}</div>
        <div className="font-display text-4xl font-bold">
          {today ? `${today.max}°/${today.min}°` : "—"}
        </div>
        <div className="text-xs text-[#D7E5F2]">
          {today ? WCODE[today.code] || "—" : "Tap refresh for a live forecast"}
        </div>
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-soft border border-line lg:p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">5-day outlook</h3>
          <button
            onClick={() => refresh()}
            disabled={loading}
            className="bg-leaf-pale text-forest rounded-full px-3.5 py-1.5 text-xs font-semibold hover:bg-leaf/20 active:scale-95 transition-all"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error && <div className="text-sm text-red-700 mb-2">{error}</div>}

        {data?.daily ? (
          <>
            <div className="grid grid-cols-2 gap-2.5 pb-1 mb-3 sm:grid-cols-3 xl:grid-cols-5">
              {data.daily.time.map((t: string, i: number) => (
                <div key={t} className="bg-cream rounded-2xl p-2.5 text-center border border-line">
                  <div className="text-[11px] text-ink-soft">
                    {new Date(t).toLocaleDateString(undefined, { weekday: "short" })}
                  </div>
                  <div className="text-xs font-semibold my-1">
                    {Math.round(data.daily.temperature_2m_max[i])}°/{Math.round(data.daily.temperature_2m_min[i])}°
                  </div>
                  <div className="text-[10px] text-[#3D6FA8]">💧{data.daily.precipitation_probability_max[i]}%</div>
                </div>
              ))}
            </div>
            <div className="bg-saffron-pale text-[#8A4E0F] rounded-2xl p-3 text-sm">{advisory()}</div>
          </>
        ) : (
          <div className="text-sm text-ink-soft italic">No forecast loaded yet.</div>
        )}
      </div>
    </div>
  );
}
