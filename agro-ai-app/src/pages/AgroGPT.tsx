import { useEffect, useRef, useState } from "react";
import { agroChat } from "../lib/ai";
import { useApp } from "../lib/AppContext";
import { supabase } from "../lib/supabaseClient";

interface Msg {
  role: "user" | "bot" | "err";
  text: string;
}

const CHIPS = [
  "Should I water my field today?",
  "What is PM-KISAN and am I eligible?",
  "Best time to sow wheat this season?"
];

export default function AgroGPT() {
  const { language, location, farmSummary, crops, profile } = useApp();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || sending) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const reply = await agroChat(text, language, location, farmSummary);
      setMessages((m) => [...m, { role: "bot", text: reply }]);
      const { data: userData } = await supabase.auth.getUser();
      if (userData?.user) {
        await supabase.from("chat_messages").insert([
          { user_id: userData.user.id, role: "user", content: text },
          { user_id: userData.user.id, role: "assistant", content: reply }
        ]);
      }
    } catch {
      setMessages((m) => [...m, { role: "err", text: "Live data unavailable right now. Please try again." }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="p-4 flex flex-col gap-4">
      <div>
        <div className="text-xs text-ink-soft">/agro-gpt</div>
        <h2 className="text-xl font-semibold text-forest">Agro GPT</h2>
        {farmSummary && (
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 w-fit">
            <span>🌾</span>
            <span>Farm profile linked: {profile?.village || location} {crops.length > 0 ? `· ${crops.map(c=>c.crop_name).join(', ')}` : ""}</span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-3xl p-4 shadow-soft border border-line flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {CHIPS.map((c) => (
            <button
              key={c}
              onClick={() => send(c)}
              className="border border-leaf bg-leaf-pale text-forest rounded-full px-3.5 py-1.5 text-xs font-medium hover:bg-leaf/20 active:scale-95 transition-all"
            >
              {c}
            </button>
          ))}
        </div>

        <div ref={logRef} className="flex flex-col gap-2.5 max-h-80 overflow-y-auto">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === "user"
                  ? "self-end bg-forest text-white rounded-br-md"
                  : m.role === "err"
                  ? "self-start bg-red-50 text-red-700 rounded-bl-md"
                  : "self-start bg-cream border border-line rounded-bl-md"
              }`}
            >
              {m.text}
            </div>
          ))}
          {sending && <div className="text-xs text-ink-soft italic">Thinking (ಸಮಾಲೋಚನೆ ನಡೆಸುತ್ತಿದೆ)…</div>}
        </div>

        <div className="flex items-center gap-2 border-t border-line pt-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Type in Kannada, English, Hindi…"
            className="flex-1 border border-line rounded-full px-4 py-2.5 text-sm bg-cream focus:outline-none focus:ring-2 focus:ring-forest"
          />
          <button
            onClick={() => send(input)}
            disabled={sending}
            className="w-10 h-10 rounded-full bg-forest text-white flex items-center justify-center disabled:opacity-40 hover:bg-forest-light active:scale-95"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}
