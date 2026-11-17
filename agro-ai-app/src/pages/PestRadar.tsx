import { useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useApp } from "../lib/AppContext";

interface Report {
  id: string;
  crop: string;
  symptom: string;
  village: string;
  created_at: string;
}

export default function PestRadar() {
  const { location, profile } = useApp();
  // Pest Radar defaults to the saved village from profile
  const initialVillage = profile?.village || location.split(",")[0].trim();

  const [village, setVillage] = useState(initialVillage);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [crop, setCrop] = useState("");
  const [symptom, setSymptom] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (profile?.village && profile.village !== village) {
      setVillage(profile.village);
    }
  }, [profile?.village]);

  async function scan(targetVillage?: string) {
    const v = targetVillage || village;
    setLoading(true);
    setError(null);
    try {
      const since = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString();
      const { data, error: err } = await supabase
        .from("pest_reports")
        .select("id, crop, symptom, village, created_at")
        .ilike("village", `%${v}%`)
        .gte("created_at", since)
        .order("created_at", { ascending: false })
        .limit(20);
      if (err) throw err;
      setReports(data || []);
    } catch {
      setError("Could not load reports. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    scan(village);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [village]);

  async function submitReport(e: React.FormEvent) {
    e.preventDefault();
    if (!crop.trim() || !symptom.trim() || !village.trim()) return;
    setSubmitting(true);
    try {
      const { data: userData } = await supabase.auth.getUser();
      await supabase.from("pest_reports").insert({
        user_id: userData?.user?.id ?? null,
        crop,
        symptom,
        village
      });
      setCrop("");
      setSymptom("");
      setFormOpen(false);
      await scan(village);
    } catch {
      setError("Could not submit report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const riskLevel = reports.length >= 5 ? "High" : reports.length >= 2 ? "Medium" : "Low";
  const riskClass =
    riskLevel === "High" ? "bg-red-100 text-red-700" : riskLevel === "Medium" ? "bg-saffron-pale text-[#8A4E0F]" : "bg-leaf-pale text-forest";

  return (
    <div className="p-4 flex flex-col gap-4 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:p-8">
      <div className="lg:col-span-2">
        <div className="text-xs text-ink-soft">/pest-radar</div>
        <h2 className="text-xl font-semibold text-forest">Pest Radar</h2>
        {profile?.village && (
          <p className="text-xs text-forest mt-0.5">
            Defaulted to your saved village: <span className="font-bold">{profile.village}</span>
          </p>
        )}
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-soft border border-line lg:grid lg:grid-cols-2 lg:gap-6 lg:p-6">
        <div className="flex gap-2 lg:col-span-2">
          <input
            value={village}
            onChange={(e) => setVillage(e.target.value)}
            placeholder="Village name"
            className="flex-1 border border-line rounded-full px-4 py-2.5 text-sm bg-cream focus:outline-none focus:ring-2 focus:ring-forest"
          />
          <button
            onClick={() => scan(village)}
            disabled={loading}
            className="bg-forest text-white rounded-full px-5 py-2.5 text-sm font-semibold hover:bg-forest-light active:scale-95 transition-all"
          >
            {loading ? "Scanning…" : "Scan"}
          </button>
        </div>

        {error && <div className="mt-3 text-sm text-red-700 lg:col-span-2">{error}</div>}

        <div className="mt-4 flex items-center justify-between lg:col-span-2">
          <span className={`inline-block rounded-full px-3.5 py-1.5 text-xs font-bold ${riskClass}`}>
            {riskLevel} risk · {reports.length} report{reports.length === 1 ? "" : "s"} in 14 days
          </span>
          <button onClick={() => setFormOpen((v) => !v)} className="text-xs text-forest font-semibold underline">
            {formOpen ? "Cancel" : "Report an issue"}
          </button>
        </div>

        {formOpen && (
          <form onSubmit={submitReport} className="mt-3 flex flex-col gap-2 bg-cream rounded-2xl p-3 border border-line">
            <input
              value={crop}
              onChange={(e) => setCrop(e.target.value)}
              placeholder="Crop (e.g. Tomato)"
              required
              className="border border-line rounded-full px-3.5 py-2 text-sm bg-white"
            />
            <input
              value={symptom}
              onChange={(e) => setSymptom(e.target.value)}
              placeholder="What are you seeing? (e.g. yellow leaf spots)"
              required
              className="border border-line rounded-full px-3.5 py-2 text-sm bg-white"
            />
            <button
              type="submit"
              disabled={submitting}
              className="bg-forest text-white rounded-full py-2 text-sm font-semibold hover:bg-forest-light active:scale-95"
            >
              {submitting ? "Submitting…" : "Submit report"}
            </button>
          </form>
        )}

        <div className="mt-4 flex flex-col gap-2 lg:mt-0">
          {reports.length === 0 && !loading && (
            <p className="text-sm text-ink-soft italic">No verified reports for this village yet — be the first to report.</p>
          )}
          {reports.map((r) => (
            <div key={r.id} className="border border-line rounded-2xl p-3 text-sm">
              <div className="font-semibold">{r.crop}</div>
              <div className="text-ink-soft">{r.symptom}</div>
              <div className="text-[11px] text-ink-soft mt-1">{new Date(r.created_at).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
