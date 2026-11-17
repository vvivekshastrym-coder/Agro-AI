// supabase/functions/agro-chat/index.ts
// Deploy: supabase functions deploy agro-chat
// Secret required: supabase secrets set ANTHROPIC_API_KEY=sk-ant-...

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type"
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const { message, language, location } = await req.json();
    if (!message) {
      return new Response(JSON.stringify({ error: "message is required" }), {
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

    const prompt = `You are Agro GPT — a warm, knowledgeable agronomist inside the Agro AI app, grounded in Indian farming context (mandis, kharif/rabi seasons, ICAR guidance, PM-KISAN and other government schemes).
Farmer's location: ${location || "India"}. Reply in ${language || "English"}, in short, plain, farmer-friendly sentences — no jargon.
Never invent specific weather, prices, or outbreak facts you are not certain of; if you don't have live data for something, say so plainly instead of guessing.
Farmer's message: "${message}"`;

    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 800,
        messages: [{ role: "user", content: prompt }]
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
    const reply = (data.content || []).filter((b: any) => b.type === "text").map((b: any) => b.text).join("\n").trim();

    return new Response(JSON.stringify({ reply: reply || "Sorry, I couldn't generate a response." }), {
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...CORS, "Content-Type": "application/json" }
    });
  }
});
