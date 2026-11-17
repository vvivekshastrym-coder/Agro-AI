// supabase/functions/diagnose-leaf/index.ts
// Deploy: supabase functions deploy diagnose-leaf
// Secret required: supabase secrets set ANTHROPIC_API_KEY=sk-ant-...

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const { imageBase64, mediaType, cropHint, language } = await req.json();
    if (!imageBase64) {
      return new Response(JSON.stringify({ error: "imageBase64 is required" }), {
        status: 400,
        headers: { ...CORS, "Content-Type": "application/json" }
      });
    }

    const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
    if (!apiKey) {
      return new Response(JSON.stringify({ error: "ANTHROPIC_API_KEY is not configured on the server" }), {
        status: 500,
        headers: { ...CORS, "Content-Type": "application/json" }
      });
    }

    const prompt = `You are an agricultural vision assistant analyzing a crop/leaf photo${
      cropHint ? ` (farmer says crop is: ${cropHint})` : ""
    }.
Reply in exactly two parts separated by the literal string "---":
Part 1: one severity word only — Healthy, Mild, Moderate, or Critical.
Part 2: a ${language || "English"} report under 140 words, plain flowing sentences (no headers): likely crop, likely disease/pest/deficiency, an honest confidence level (be conservative from a single photo), key visible symptoms, simple treatment steps a smallholder can follow, and one prevention tip.`;

    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 700,
        messages: [
          {
            role: "user",
            content: [
              { type: "image", source: { type: "base64", media_type: mediaType || "image/jpeg", data: imageBase64 } },
              { type: "text", text: prompt }
            ]
          }
        ]
      })
    });

    if (!res.ok) {
      const errText = await res.text();
      return new Response(JSON.stringify({ error: "AI request failed", detail: errText }), {
        status: 502,
        headers: { ...CORS, "Content-Type": "application/json" }
      });
    }

    const data = await res.json();
    const text = (data.content || []).filter((b: any) => b.type === "text").map((b: any) => b.text).join("\n").trim();
    const [severityRaw, ...rest] = text.split("---");
    const severity = (severityRaw || "Unknown").trim();
    const report = rest.join("---").trim() || text;

    return new Response(JSON.stringify({ severity, report }), {
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  }
});
