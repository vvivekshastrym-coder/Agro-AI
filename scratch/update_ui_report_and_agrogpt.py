with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace any remaining '1800-KISAN' or '1800-ಕಿಸಾನ್' or '1800-किसान' with '1800-AGRO-AI'
content = content.replace('1800-KISAN', '1800-AGRO-AI')
content = content.replace('1800-ಕಿಸಾನ್', '1800-ಆಗ್ರೋ-AI')
content = content.replace('1800-किसान', '1800-एग्रो-AI')

# 2. Update Home View to include Daily Farm Report card right before "Your reports"
home_reports_target = '''      <div class="section-title" id="homeSecReports">Your reports</div>
      <div class="card" id="reportsContainer">
        <div class="muted" id="reportsEmptyText">No diagnosis reports yet. Run a crop diagnosis to start building your farm history — it will show up here and inside Agro GPT.</div>
      </div>'''

home_reports_replacement = '''      <!-- ============ DAILY FARM REPORT ============ -->
      <div style="margin: 18px 0 16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:36px;height:36px;border-radius:50%;background:var(--forest);color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;">✨</div>
            <div>
              <h3 class="display" style="font-size:20px;margin:0;color:var(--ink);" id="dailyReportTitle">Daily farm report</h3>
              <div class="muted" style="font-size:12px;" id="dailyReportSub">Fresh AI brief for your farm — today's weather, pests, and actions.</div>
            </div>
          </div>
          <button class="btn" style="background:var(--forest);color:#fff;padding:7px 14px;border-radius:999px;font-size:12px;font-weight:600;border:none;cursor:pointer;white-space:nowrap;" id="dailyReportRegenBtn" onclick="loadDailyFarmReport(true)">↻ Regenerate</button>
        </div>

        <!-- WhatsApp Notifications Banner -->
        <div style="background:#E8F4EA;border:1px solid #C5E1C9;border-radius:12px;padding:11px 14px;margin-bottom:12px;display:flex;align-items:flex-start;gap:10px;">
          <span style="color:var(--forest);font-size:15px;font-weight:700;line-height:1.2;">✓</span>
          <div style="font-size:12.5px;line-height:1.45;">
            <div style="font-weight:700;color:var(--forest);" id="dailyWaStatus">WhatsApp notifications on</div>
            <div style="color:var(--ink-soft);">
              <span id="dailyWaDescPrefix">Daily brief will be sent to</span>
              <strong style="color:var(--ink);" id="dailyBriefPhone">917019286323</strong>
              <span id="dailyWaDescSuffix">at 6:30 AM IST.</span>
              <a href="javascript:void(0)" onclick="changeDailyBriefPhone()" style="color:var(--ink-soft);text-decoration:underline;margin-left:4px;" id="dailyWaChangeLink">Change number</a>
            </div>
          </div>
        </div>

        <!-- Main Daily Report Card -->
        <div class="card" style="padding:18px;border-radius:16px;background:#fff;border:1px solid var(--line);">
          <div class="muted" style="font-size:12px;margin-bottom:4px;" id="dailyReportDate">2026-10-26</div>
          <div class="display" style="font-size:20px;font-weight:700;color:var(--ink);margin-bottom:4px;line-height:1.3;" id="dailyReportHeadline">Good morning to our hardworking farmer in Mandya.</div>
          <div style="font-size:13.5px;color:var(--ink-soft);margin-bottom:14px;" id="dailyReportSummary">Partly cloudy skies with moderate temperatures are expected today across the district.</div>

          <div class="grid2" style="gap:10px;margin-bottom:14px;">
            <div style="background:#FAF7EE;border:1px solid #EDE7D5;border-radius:12px;padding:12px;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                <span style="font-size:14px;">☀️</span>
                <span style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:var(--ink-soft);" id="dailyCardLblWeather">WEATHER</span>
              </div>
              <div style="font-size:12.5px;color:var(--ink);line-height:1.45;" id="dailyReportWeather">Expect a high of 29°C with moderate humidity and light breezes throughout the afternoon.</div>
            </div>

            <div style="background:#FAF7EE;border:1px solid #EDE7D5;border-radius:12px;padding:12px;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                <span style="font-size:14px;">🐞</span>
                <span style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:var(--ink-soft);" id="dailyCardLblPest">PEST &amp; DISEASE</span>
              </div>
              <div style="font-size:12.5px;color:var(--ink);line-height:1.45;" id="dailyReportPest">Dry and windy conditions increase the risk of thrips and aphids on your standing crops.</div>
            </div>

            <div style="background:#FAF7EE;border:1px solid #EDE7D5;border-radius:12px;padding:12px;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                <span style="font-size:14px;">🌱</span>
                <span style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:var(--ink-soft);" id="dailyCardLblAction">CROP ACTION</span>
              </div>
              <div style="font-size:12.5px;color:var(--ink);line-height:1.45;" id="dailyReportAction">Ensure adequate irrigation during the evening to maintain soil moisture levels against the daytime heat.</div>
            </div>

            <div style="background:#FAF7EE;border:1px solid #EDE7D5;border-radius:12px;padding:12px;cursor:pointer;" onclick="go('market')">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                <span style="font-size:14px;">📈</span>
                <span style="font-size:11px;font-weight:700;letter-spacing:0.04em;color:var(--ink-soft);" id="dailyCardLblMarket">MARKET</span>
              </div>
              <div style="font-size:12.5px;color:var(--ink);line-height:1.45;" id="dailyReportMarket">For the latest local crop prices, please check the Mandi tab in the application.</div>
            </div>
          </div>

          <div style="font-size:12px;font-style:italic;color:var(--ink-soft);" id="dailyReportQuote">Your dedication feeds the nation; may your harvest be as bountiful as your efforts.</div>
        </div>
      </div>

      <div class="section-title" id="homeSecReports">Your reports</div>
      <div class="card" id="reportsContainer">
        <div class="muted" id="reportsEmptyText">No diagnosis reports yet. Run a crop diagnosis to start building your farm history — it will show up here and inside Agro GPT.</div>
      </div>'''

assert home_reports_target in content, "home_reports_target not found"
content = content.replace(home_reports_target, home_reports_replacement, 1)

# 3. Replace the Agro GPT View (data-view="kisangpt") with the full Agro GPT layout
gpt_view_target = '''    <!-- ============ KISAN GPT ============ -->
    <section class="view" data-view="kisangpt" style="display:none;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin:4px 0 10px;">
        <h2 class="display" style="font-size:20px;margin:0;" id="gptTitle">Agro GPT</h2>
        <button class="pill pill-forest" style="border:none;cursor:pointer;" id="gptCallBtn" onclick="showToast('Dialing 1800-AGRO-AI…')">📞 1800-AGRO-AI</button>
      </div>
      <div class="pillbar" id="gptLangBar"></div>
      <div class="chat-scroll" id="chatScroll"></div>
      <div class="pillbar" id="suggestChips"></div>
      <div class="chat-input-row">
        <button class="icon-btn mic" id="micBtn" onclick="toggleMic()" title="Voice mic">🎙️</button>
        <input class="chat-input" id="chatInput" placeholder="Type your question…" onkeydown="if(event.key==='Enter')sendChat()">
        <button class="icon-btn send" onclick="sendChat()" title="Send">➤</button>
      </div>
    </section>'''

gpt_view_replacement = '''    <!-- ============ AGRO GPT ============ -->
    <section class="view" data-view="kisangpt" style="display:none;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin:4px 0 10px;gap:8px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <button class="btn btn-outline" style="padding:5px 10px;font-size:12px;" onclick="toggleAgroGptHistoryDrawer()" title="Chat History">☰ <span id="gptHistoryToggleLbl">History</span></button>
          <h2 class="display" style="font-size:20px;margin:0;" id="gptTitle">Agro GPT</h2>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          <button class="btn" style="background:var(--forest);color:#fff;padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600;border:none;cursor:pointer;" id="gptNewChatTopBtn" onclick="startNewAgroGptChat()">+ New chat</button>
        </div>
      </div>

      <div class="pillbar" id="gptLangBar" style="margin-bottom:10px;"></div>

      <div style="display:flex;gap:12px;align-items:stretch;position:relative;">
        <!-- Collapsible Chat History Sidebar -->
        <aside id="agroGptSidebar" style="display:none;width:210px;flex-shrink:0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px;flex-direction:column;justify-content:space-between;max-height:520px;">
          <div>
            <button class="btn btn-block" style="background:var(--forest);color:#fff;border-radius:999px;padding:9px 12px;font-size:13px;font-weight:600;border:none;cursor:pointer;margin-bottom:10px;" id="gptSidebarNewChatBtn" onclick="startNewAgroGptChat()">+ New chat</button>
            <div id="agroGptConvList" style="display:flex;flex-direction:column;gap:4px;max-height:360px;overflow-y:auto;padding-right:2px;"></div>
          </div>
          <div style="border-top:1px solid var(--line);padding-top:10px;margin-top:10px;display:flex;flex-direction:column;gap:8px;font-size:12.5px;">
            <a href="javascript:void(0)" onclick="go('account')" style="color:var(--ink);text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:600;" id="gptSideProfile">👤 Profile &amp; farm</a>
            <a href="javascript:void(0)" onclick="signOut()" style="color:var(--ink-soft);text-decoration:none;" id="gptSideSignOut">Sign out</a>
          </div>
        </aside>

        <!-- Main Agro GPT Panel -->
        <div style="flex:1;min-width:0;display:flex;flex-direction:column;">
          <!-- Welcome Hero (Always says Agro GPT) -->
          <div id="agroGptWelcomeHero" style="text-align:center;padding:14px 10px 12px;">
            <div style="width:46px;height:46px;border-radius:13px;background:var(--forest);color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:22px;margin-bottom:8px;">🌱</div>
            <h3 class="display" style="font-size:24px;margin:0 0 6px;color:var(--ink);" id="gptHeroGreeting">Namaste! I'm Agro GPT.</h3>
            <p class="muted" style="font-size:13px;max-width:420px;margin:0 auto;line-height:1.45;" id="gptHeroSubtitle">The central AI brain of Agro AI. I read your farm's weather, location, crop, and history before every answer.</p>
          </div>

          <!-- Active Chat Scroll -->
          <div class="chat-scroll" id="chatScroll" style="min-height:120px;max-height:280px;margin-bottom:10px;"></div>

          <!-- Main Input Box Card -->
          <div style="background:#fff;border:1.5px solid var(--line);border-radius:16px;padding:12px 14px;box-shadow:0 3px 12px rgba(0,0,0,0.03);margin-bottom:12px;">
            <textarea id="chatInput" rows="2" placeholder="Ask about crops, weather, mandi prices, schemes..." style="width:100%;border:none;outline:none;resize:none;font-family:inherit;font-size:14px;color:var(--ink);background:transparent;margin-bottom:8px;" onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault();sendChat();}"></textarea>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
              <button id="micBtn" onclick="toggleMic()" style="background:#F7F4EB;border:1px solid #E6E1D2;color:var(--ink);padding:7px 14px;border-radius:999px;font-size:12.5px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px;">
                <span>🎙️</span> <span id="gptSpeakInsteadTxt">Speak instead</span>
              </button>
              <button id="askAgroGptBtn" onclick="sendChat()" style="background:var(--forest);color:#fff;border:none;padding:8px 18px;border-radius:999px;font-size:12.5px;font-weight:600;cursor:pointer;">
                Ask Agro GPT
              </button>
            </div>
          </div>

          <!-- Prominent Voice Button (12 Indian Languages) -->
          <div style="text-align:center;margin-bottom:12px;">
            <button id="talkAgroGptBtn" onclick="toggleMic()" style="background:#3B873E;color:#fff;border:none;padding:10px 22px;border-radius:999px;font-size:13px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:8px;box-shadow:0 3px 10px rgba(59,135,62,0.22);">
              <span>🎙️</span> <span id="talkAgroGptBtnTxt">Talk to Agro GPT — 12 Indian languages</span>
            </button>
            <div class="muted" style="font-size:11.5px;margin-top:6px;" id="talkAgroGptWakeTxt">Say “Hi Agro AI” to wake it, then ask in Hindi, Kannada, Tamil, Telugu, Marathi and more.</div>
          </div>

          <!-- Suggestion Chips -->
          <div id="suggestChips" style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;"></div>
        </div>
      </div>
    </section>'''

assert gpt_view_target in content, "gpt_view_target not found"
content = content.replace(gpt_view_target, gpt_view_replacement, 1)

# 4. Update SUGGESTIONS_I18N with the exact 4 prompts in EN, KN, HI
suggestions_target = '''const SUGGESTIONS_I18N = {
  en: ["Show today's weather", "Diagnose my crop", "Today's mandi price", "Book a drone", "What fertilizer should I buy?"],
  kn: ["ಇಂದಿನ ಹವಾಮಾನ ತೋರಿಸಿ", "ನನ್ನ ಬೆಳೆ ರೋಗ ತಪಾಸಣೆ ಮಾಡಿ", "ಇಂದಿನ ಮಂಡಿ ದರಗಳು", "ಡ್ರೋನ್ ಬುಕ್ ಮಾಡಿ", "ಯಾವ ಗೊಬ್ಬರ ಬಳಸಬೇಕು?"],
  hi: ["आज का मौसम दिखाएं", "मेरी फसल की जांच करें", "आज का मंडी भाव", "ड्रोन बुक करें", "मुझे कौन सी खाद खरीदनी चाहिए?"]
};'''

suggestions_replacement = '''const SUGGESTIONS_I18N = {
  en: [
    "Mere tomato ke patton par yellow spots aa rahe hain, kya karu?",
    "Best time to plant wheat this season?",
    "How do I apply for the PM-KISAN scheme?",
    "Urea dose per acre for sugarcane?"
  ],
  kn: [
    "ನನ್ನ ಟೊಮೆಟೊ ಎಲೆಗಳ ಮೇಲೆ ಹಳದಿ ಚುಕ್ಕೆಗಳು ಬರುತ್ತಿವೆ, ಏನು ಮಾಡಬೇಕು?",
    "ಈ ಋತುವಿನಲ್ಲಿ ಗೋಧಿ ಬಿತ್ತಲು ಉತ್ತಮ ಸಮಯ ಯಾವುದು?",
    "PM-KISAN ಯೋಜನೆಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು ಹೇಗೆ?",
    "ಕಬ್ಬಿನ ಬೆಳೆಗೆ ಪ್ರತಿ ಎಕರೆಗೆ ಯೂರಿಯಾ ಪ್ರಮಾಣ ಎಷ್ಟು?"
  ],
  hi: [
    "मेरे टमाटर के पत्तों पर पीले धब्बे आ रहे हैं, क्या करूं?",
    "इस सीजन में गेहूं बोने का सबसे अच्छा समय क्या है?",
    "मैं PM-KISAN योजना के लिए आवेदन कैसे करूं?",
    "गन्ने के लिए प्रति एकड़ यूरिया की खुराक क्या है?"
  ]
};'''

assert suggestions_target in content, "suggestions_target not found"
content = content.replace(suggestions_target, suggestions_replacement, 1)

# 5. Update go(view) to trigger loadDailyFarmReport and renderAgroGptHistory
go_target = '''  if(view === 'kisangpt') renderChat();
  if(view === 'weather') loadRealWeather();
  if(view === 'market') initMandiMarketView();
  if(view === 'home') { loadRealWeather(); renderReportsList(); loadHomeBroadcasts(); loadHomePlansCard(); }'''

go_replacement = '''  if(view === 'kisangpt') { renderChat(); renderAgroGptHistory(); renderSuggestChips(); }
  if(view === 'weather') loadRealWeather();
  if(view === 'market') initMandiMarketView();
  if(view === 'home') { loadRealWeather(); loadDailyFarmReport(); renderReportsList(); loadHomeBroadcasts(); loadHomePlansCard(); }'''

assert go_target in content, "go_target not found"
content = content.replace(go_target, go_replacement, 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated HTML layout for Daily Farm Report and Agro GPT.")
