import { useRef, useState } from "react";
import { diagnoseLeaf } from "../lib/ai";
import { useApp } from "../lib/AppContext";
import { supabase } from "../lib/supabaseClient";

const CROPS = ["", "Wheat", "Rice", "Cotton", "Tomato", "Ragi", "Maize", "Sugarcane", "Onion"];

export default function Diagnose() {
  const { language } = useApp();
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [base64, setBase64] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<string>("image/jpeg");
  const [cropHint, setCropHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ severity: string; report: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMediaType(file.type);
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setPreview(dataUrl);
      setBase64(dataUrl.split(",")[1]);
      setResult(null);
      setError(null);
    };
    reader.readAsDataURL(file);
  }

  async function analyze() {
    if (!base64) return;
    setLoading(true);
    setError(null);
    try {
      const res = await diagnoseLeaf(base64, mediaType, cropHint, language);
      setResult(res);
      // Save to farmer's history (requires the diagnoses table + RLS, see migrations)
      const { data: userData } = await supabase.auth.getUser();
      if (userData?.user) {
        await supabase.from("diagnoses").insert({
          user_id: userData.user.id,
          crop_hint: cropHint || null,
          severity: res.severity,
          report: res.report
        });
      }
    } catch (err: any) {
      setError("AI service temporarily unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const severityColor: Record<string, string> = {
    healthy: "bg-leaf-pale text-forest",
    mild: "bg-saffron-pale text-[#8A4E0F]",
    moderate: "bg-saffron-pale text-[#8A4E0F]",
    critical: "bg-red-100 text-red-700"
  };

  return (
    <div className="p-4 flex flex-col gap-4 lg:grid lg:grid-cols-2 lg:items-start lg:gap-6 lg:p-8">
      <div className="lg:col-span-2">
        <div className="text-xs text-ink-soft">/diagnose</div>
        <h2 className="text-xl font-semibold text-forest">Leaf Diagnose</h2>
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-soft border border-line lg:grid lg:grid-cols-2 lg:gap-4 lg:p-6">
        <div
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-line rounded-3xl p-7 text-center text-sm text-ink-soft cursor-pointer bg-cream/50 lg:row-start-1"
        >
          {preview ? (
            <img src={preview} alt="leaf" className="max-h-40 mx-auto rounded-2xl mb-2" />
          ) : (
            "📷 Tap to upload or capture a leaf photo"
          )}
          {preview && <div>Photo ready — choose crop and analyze</div>}
        </div>
        <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} className="hidden" />

        <div className="mt-3 flex gap-2 lg:col-span-2">
          <select
            value={cropHint}
            onChange={(e) => setCropHint(e.target.value)}
            className="flex-1 border border-line rounded-full px-4 py-2.5 text-sm bg-cream"
          >
            {CROPS.map((c) => (
              <option key={c} value={c}>
                {c || "Crop (optional)"}
              </option>
            ))}
          </select>
          <button
            onClick={analyze}
            disabled={!base64 || loading}
            className="bg-forest text-white rounded-full px-5 py-2.5 text-sm font-semibold disabled:opacity-40"
          >
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>

        {error && <div className="mt-4 text-sm text-red-700 lg:col-span-2">{error}</div>}

        {result && (
          <div className="mt-4 lg:col-start-2 lg:row-start-1 lg:mt-0">
            <span
              className={`inline-block rounded-full px-3 py-1 text-xs font-bold mb-2 ${
                severityColor[result.severity.toLowerCase()] || "bg-leaf-pale text-forest"
              }`}
            >
              {result.severity}
            </span>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.report}</p>
            <p className="text-[11px] text-ink-soft italic mt-2">
              AI estimate from a single photo — not a lab-confirmed diagnosis. Confirm with a local
              agronomist before treating high-value crops.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
