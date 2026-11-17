// supabase/functions/mandi-price/index.ts
// Deploy: supabase functions deploy mandi-price
// Secrets required:
//   supabase secrets set ANTHROPIC_API_KEY=sk-ant-...
//   supabase secrets set DATA_GOV_API_KEY=...   (free — register at https://data.gov.in)
//
// Data source: data.gov.in's AGMARKNET "Variety-wise Daily Market Prices"
// resource (id 9ef84268-d588-465a-a308-a864a43d0070). This is real,
// government-published mandi data — if the key isn't configured yet, or the
// resource has no rows for this crop/state/day, we say so plainly instead
// of inventing a price, per Agro AI's real-data-first principle.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"
};

const RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const { crop, state, language } = await req.json();
    if (!crop || !state) {
      return new Response(JSON.stringify({ error: "crop and state are required" }), {
        status: 400,
        headers: { ...CORS, "Content-Type": "application/json" }
      });
    }

    const dataGovKey = Deno.env.get("DATA_GOV_API_KEY");
    if (!dataGovKey) {
      return new Response(
        JSON.stringify({
          available: false,
          summary:
            "Live mandi data isn't configured yet. Get a free API key at data.gov.in and set it as the DATA_GOV_API_KEY secret to enable real prices."
        }),
        { headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    const url = `https://api.data.gov.in/resource/${RESOURCE_ID}?api-key=${dataGovKey}&format=json&limit=30&filters[state]=${encodeURIComponent(
      state
    )}&filters[commodity]=${encodeURIComponent(crop)}`;

    const res = await fetch(url);
    if (!res.ok) {
      return new Response(
        JSON.stringify({ available: false, summary: "Mandi price service is temporarily unavailable. Please try again." }),
        { headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }
    const json = await res.json();
    const records = json.records || [];

    if (!records.length) {
      return new Response(
        JSON.stringify({
          available: false,
          summary: `No recent mandi price records found for ${crop} in ${state}. Try a nearby state or a more common crop name.`
        }),
        { headers: { ...CORS, "Content-Type": "application/json" } }
      );
    }

    const latest = records[0];
    const modalPrice = latest.modal_price ? `₹${latest.modal_price}/quintal` : "Price unavailable";

    const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
    let summary = `Latest reported price at ${latest.market || "a nearby mandi"}: ${modalPrice}.`;
    let trend = "Steady";

    if (apiKey) {
      const prompt = `Here are recent real mandi price records (₹/quintal) for ${crop} in ${state}, most recent first:
${JSON.stringify(records.slice(0, 15), null, 2)}

Reply in exactly two parts separated by "---":
Part 1: one word only — Rising, Falling, or Steady (based on the trend across these records).
Part 2: a ${language || "English"} summary under 70 words: current price, the trend, and one line of practical sell/hold advice. Use only the numbers given — never invent a price not present in this data.`;
      try {
        const aiRes = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
          body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: 400, messages: [{ role: "user", content: prompt }] })
        });
        if (aiRes.ok) {
          const aiData = await aiRes.json();
          const text = (aiData.content || []).filter((b: any) => b.type === "text").map((b: any) => b.text).join("\n").trim();
          const [trendRaw, ...rest] = text.split("---");
          trend = (trendRaw || trend).trim();
          summary = rest.join("---").trim() || summary;
        }
      } catch {
        // fall back to the raw record above — never block on the summarizer failing
      }
    }

    return new Response(JSON.stringify({ available: true, price: modalPrice, trend, summary }), {
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  }
});
