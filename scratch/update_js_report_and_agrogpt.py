with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Agro GPT JS logic (lines around renderChat / sendChat / pickFallbackReply)
old_gpt_js = '''/* ================= KISAN GPT (WIRED TO API) ================= */
let chatHistory = [];
let conversationId = 'conv_' + Date.now();

function renderChat(){
  const scroll = document.getElementById('chatScroll');
  if(!scroll) return;
  scroll.innerHTML = chatHistory.map(m=>`<div class="bubble ${m.role==='user'?'bubble-user':'bubble-ai'}">${m.text}</div>`).join('');
  scroll.scrollTop = scroll.scrollHeight;
}

function renderSuggestChips(){
  const container = document.getElementById('suggestChips');
  if(!container) return;
  container.innerHTML = SUGGESTIONS.map(s=>`<button class="suggest-chip" onclick="sendChat('${s.replace(/'/g,"\\\\'")}')">${s}</button>`).join('');
}

async function sendChat(preset){
  const input = document.getElementById('chatInput');
  const msg = preset || input.value.trim();
  if(!msg) return;
  chatHistory.push({role:'user', text: msg});
  input.value = '';
  renderChat();

  const scroll = document.getElementById('chatScroll');
  const typingMsg = currentLang === 'kn' ? 'ಯೋಚಿಸಲಾಗುತ್ತಿದೆ…' : 'Thinking…';
  scroll.insertAdjacentHTML('beforeend', `<div class="typing" id="typingIndicator">${typingMsg}</div>`);
  scroll.scrollTop = scroll.scrollHeight;

  // Real backend call
  try {
    const res = await fetch('/api/agro-gpt/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: msg,
        language: currentLang,
        farmer_id: (session.google && session.google.email) ? session.google.email : (session.phone || 'default_farmer'),
        conversation_id: conversationId
      })
    });
    if(res.ok) {
      const data = await res.json();
      document.getElementById('typingIndicator')?.remove();
      chatHistory.push({role:'ai', text: data.reply || data.response || pickFallbackReply(msg)});
      renderChat();
      return;
    }
  } catch(e) {
    console.warn('Backend agro-gpt chat error:', e);
  }

  setTimeout(()=>{
    document.getElementById('typingIndicator')?.remove();
    chatHistory.push({role:'ai', text: pickFallbackReply(msg)});
    renderChat();
  }, 750);
}

function pickFallbackReply(msg){
  const m = msg.toLowerCase();
  const isKn = currentLang === 'kn';
  if(m.includes('weather')||m.includes('rain')||m.includes('barish')||m.includes('mausam')||m.includes('ಹವಾಮಾನ')||m.includes('ಮಳೆ')){
    return isKn
      ? "🌦️ ಇಂದಿನ ಹವಾಮಾನ: ಸುಮಾರು 28°C ಮತ್ತು ಭಾಗಶಃ ಮೋಡವಿದೆ. ತೇವಾಂಶ 68% ಆಗಿದೆ. ಮುಂಜಾನೆ 6:30 ರಿಂದ 9:00 ರ ನಡುವೆ ಸಿಂಪಡಣೆಗೆ ಸೂಕ್ತ ಸಮಯ."
      : "It's 28°C and partly cloudy with 68% humidity. Early morning (6:30 - 9:00 AM) is recommended for spraying.";
  }
  if(m.includes('mandi')||m.includes('price')||m.includes('rate')||m.includes('bhaav')||m.includes('ಮಂಡಿ')||m.includes('ದರ')||m.includes('ಬೆಲೆ')){
    return isKn
      ? "📈 ಮಂಡ್ಯ ಮಂಡಿಯಲ್ಲಿ ಟೊಮೆಟೊ ₹1,600/ಕ್ವಿಂಟಾಲ್ ದರದಲ್ಲಿದೆ. ಸಂಪೂರ್ಣ ದರಗಳಿಗಾಗಿ ಮಂಡಿ ಮೆನು ತೆರೆಯಿರಿ."
      : "Tomato is currently trading at ₹1,600/quintal in Mandya APMC. Open the Mandi tab for live observations.";
  }
  if(m.includes('diagnos')||m.includes('crop')||m.includes('leaf')||m.includes('disease')||m.includes('bimari')||m.includes('ರೋಗ')||m.includes('ತಪಾಸಣೆ')){
    return isKn
      ? "🌿 ನಿಮ್ಮ ಬೆಳೆಗೆ ರೋಗ ತಪಾಸಣೆ ಮಾಡಲು 'ರೋಗ ತಪಾಸಣೆ' ಮೆನುವಿನಲ್ಲಿ ಎಲೆಯ ಫೋಟೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. AI ಮಾದರಿಯು ರೋಗ ಪತ್ತೆಹಚ್ಚಿ ಸಾವಯವ ಮತ್ತು ರಾಸಾಯನಿಕ ಚಿಕಿತ್ಸೆ ನೀಡುತ್ತದೆ."
      : "You can upload a photo in the Diagnose tab. Our AI model will detect the disease, identify the pathogen, and recommend organic and chemical treatments.";
  }
  if(m.includes('drone')||m.includes('ಡ್ರೋನ್')){
    return isKn
      ? "🛸 ನಿಮ್ಮ ಜಮೀನಿಗೆ ಕೀಟನಾಶಕ ಸಿಂಪಡಣೆ ಮಾಡಲು ದೃಢೀಕೃತ ಡ್ರೋನ್ ಆಪರೇಟರ್‌ಗಳು ಲಭ್ಯವಿದ್ದಾರೆ. 'ಡ್ರೋನ್ ಸೇವೆ' ಮೆನು ಮೂಲಕ ಬುಕ್ ಮಾಡಿ."
      : "Verified drone operators are available for precision spraying and scouting. Book via the Drone Services menu.";
  }
  if(m.includes('fertilizer')||m.includes('khad')||m.includes('ಗೊಬ್ಬರ')||m.includes('ಯೂರಿಯಾ')){
    return isKn
      ? "🌾 ನಿಮ್ಮ ಬೆಳೆಗೆ ಸಮತೋಲಿತ NPK 19:19:19 ಮತ್ತು ಬೇವಿನ ಹಿಂಡಿ ಬಳಸುವುದು ಉತ್ತಮ ಎಲೆ ಮತ್ತು ಬೇರಿನ ಬೆಳವಣಿಗೆಗೆ ಸಹಕಾರಿಯಾಗಿದೆ."
      : "For balanced nutrition, apply balanced NPK 19:19:19 with neem cake to promote strong vegetative growth.";
  }
  return isKn
    ? "ನಮಸ್ಕಾರ! ನಾನು ಅಗ್ರೋ ಜಿಪಿಟಿ. ಹವಾಮಾನ, ಮಂಡಿ ದರ, ಬೆಳೆ ರೋಗ ಮತ್ತು ಕೃಷಿ ಸಲಹೆಗಳಿಗಾಗಿ ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ."
    : "Namaste! I'm Agro GPT. I can assist you with hyperlocal weather, live mandi prices, leaf disease diagnosis, and agronomy advice.";
}'''

new_gpt_js = '''/* ================= AGRO GPT & DAILY FARM REPORT (WIRED TO API) ================= */
let chatHistory = [];
let conversationId = 'conv_' + Date.now();
let agroGptSessions = [];
try {
  const savedSess = localStorage.getItem('agroai_gpt_sessions');
  if (savedSess) {
    agroGptSessions = JSON.parse(savedSess);
  } else {
    agroGptSessions = [
      { id: 'conv_seed_1', title: 'what is the price tomato in apmc market', isVoice: false, messages: [
        { role: 'user', text: 'what is the price tomato in apmc market' },
        { role: 'ai', text: '📈 Tomato is currently trading at ₹1,600/quintal (Min ₹1,350, Max ₹1,850) in Kolar & Mandya APMC. Open the Mandi tab to search all 50+ Karnataka APMC markets.' }
      ]},
      { id: 'conv_seed_2', title: 'Foliar spray of 1% Bordeaux mixture (1kg Copper Sulphate + 1…', isVoice: false, messages: [
        { role: 'user', text: 'Foliar spray of 1% Bordeaux mixture preparation' },
        { role: 'ai', text: '🧪 To prepare 1% Bordeaux mixture: Dissolve 1 kg Copper Sulphate in 50L water and 1 kg Quick Lime in another 50L water in plastic/earthen vessels. Slowly pour Copper Sulphate solution into Lime solution while stirring continuously. Test with a clean iron blade for neutral pH before spraying.' }
      ]},
      { id: 'conv_seed_3', title: 'ಹಾಯ್', isVoice: false, messages: [
        { role: 'user', text: 'ಹಾಯ್' },
        { role: 'ai', text: 'ನಮಸ್ಕಾರ! ನಾನು ಆಗ್ರೋ ಜಿಪಿಟಿ (Agro GPT). ನಿಮ್ಮ ಜಮೀನಿನ ಹವಾಮಾನ, ಮಂಡಿ ಬೆಲೆ, ಬೆಳೆ ರೋಗ ಮತ್ತು ಕೃಷಿ ಸಲಹೆಗಳಿಗಾಗಿ ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?' }
      ]},
      { id: 'conv_seed_4', title: 'Voice conversation', isVoice: true, messages: [
        { role: 'user', text: '🎙️ [Voice] Show today\\'s spray window' },
        { role: 'ai', text: '✅ Optimal Spray Window today: Clear skies and calm wind (~10 km/h). Spray early morning between 6:30 AM and 9:00 AM.' }
      ]}
    ];
    localStorage.setItem('agroai_gpt_sessions', JSON.stringify(agroGptSessions));
  }
} catch (e) { agroGptSessions = []; }

function toggleAgroGptHistoryDrawer() {
  const sb = document.getElementById('agroGptSidebar');
  if (!sb) return;
  const isHidden = sb.style.display === 'none' || !sb.style.display;
  sb.style.display = isHidden ? 'flex' : 'none';
  if (isHidden) renderAgroGptHistory();
}

function startNewAgroGptChat() {
  conversationId = 'conv_' + Date.now();
  chatHistory = [];
  const hero = document.getElementById('agroGptWelcomeHero');
  if (hero) hero.style.display = 'block';
  renderChat();
  renderAgroGptHistory();
  const input = document.getElementById('chatInput');
  if (input) input.focus();
}

function selectAgroGptConversation(id) {
  const found = agroGptSessions.find(s => s.id === id);
  if (!found) return;
  conversationId = found.id;
  chatHistory = Array.isArray(found.messages) ? [...found.messages] : [];
  renderChat();
  renderAgroGptHistory();
}

function saveCurrentConversationToHistory(firstTitle, isVoice = false) {
  let existing = agroGptSessions.find(s => s.id === conversationId);
  if (!existing) {
    existing = {
      id: conversationId,
      title: (firstTitle || 'New conversation').slice(0, 50),
      isVoice: !!isVoice,
      messages: [...chatHistory]
    };
    agroGptSessions.unshift(existing);
  } else {
    existing.messages = [...chatHistory];
  }
  try {
    localStorage.setItem('agroai_gpt_sessions', JSON.stringify(agroGptSessions.slice(0, 30)));
  } catch (e) {}
  renderAgroGptHistory();
}

function renderAgroGptHistory() {
  const listEl = document.getElementById('agroGptConvList');
  if (!listEl) return;
  if (!agroGptSessions.length) {
    listEl.innerHTML = `<div class="muted" style="font-size:12px;padding:8px;">No past chats yet</div>`;
    return;
  }
  listEl.innerHTML = agroGptSessions.map(s => {
    const active = s.id === conversationId;
    const icon = s.isVoice ? '🎙️' : '💬';
    return `
      <button onclick="selectAgroGptConversation('${escHtml(s.id)}')"
              style="width:100%;text-align:left;background:${active ? '#EBF5EC' : 'transparent'};border:none;padding:8px 10px;border-radius:8px;font-size:12.5px;color:var(--ink);cursor:pointer;display:flex;align-items:center;gap:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:${active ? '700' : '500'};">
        <span style="font-size:12px;flex-shrink:0;">${icon}</span>
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escHtml(s.title)}</span>
      </button>
    `;
  }).join('');
}

function renderChat(){
  const scroll = document.getElementById('chatScroll');
  if(!scroll) return;
  scroll.innerHTML = chatHistory.map(m=>`<div class="bubble ${m.role==='user'?'bubble-user':'bubble-ai'}" style="white-space:pre-line;">${m.text}</div>`).join('');
  scroll.scrollTop = scroll.scrollHeight;
}

function renderSuggestChips(){
  const container = document.getElementById('suggestChips');
  if(!container) return;
  container.innerHTML = SUGGESTIONS.map(s=>`<button class="suggest-chip" onclick="sendChat('${s.replace(/'/g,"\\\\'")}')">${s}</button>`).join('');
}

async function sendChat(preset, isVoice = false){
  const input = document.getElementById('chatInput');
  const msg = preset || (input ? input.value.trim() : '');
  if(!msg) return;
  chatHistory.push({role:'user', text: msg});
  if(input) input.value = '';
  renderChat();
  saveCurrentConversationToHistory(isVoice ? 'Voice conversation' : msg, isVoice);

  const scroll = document.getElementById('chatScroll');
  const typingMsg = currentLang === 'kn' ? 'ಆಗ್ರೋ ಜಿಪಿಟಿ ಯೋಚಿಸುತ್ತಿದೆ…' : (currentLang === 'hi' ? 'एग्रो जीपीटी सोच रहा है…' : 'Agro GPT is thinking…');
  scroll.insertAdjacentHTML('beforeend', `<div class="typing" id="typingIndicator">${typingMsg}</div>`);
  scroll.scrollTop = scroll.scrollHeight;

  // Real backend call
  try {
    const headers = {'Content-Type': 'application/json'};
    if (typeof session !== 'undefined' && session && session.token) {
      headers['Authorization'] = 'Bearer ' + session.token;
    }
    const res = await fetch('/api/agro-gpt/chat', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        message: msg,
        language: currentLang,
        farmer_id: (session.google && session.google.email) ? session.google.email : (session.phone || 'default_farmer'),
        conversation_id: conversationId,
        context: {
          location: (farmerProfile && farmerProfile.village) ? farmerProfile.village : 'Mandya',
          crop: (farmerProfile && farmerProfile.crop) ? farmerProfile.crop : 'Tomato'
        }
      })
    });
    if(res.ok) {
      const data = await res.json();
      document.getElementById('typingIndicator')?.remove();
      const replyTxt = (data.reply || data.response || pickFallbackReply(msg)).replace(/Kisan GPT/gi, 'Agro GPT').replace(/KisanGPT/gi, 'Agro GPT');
      chatHistory.push({role:'ai', text: replyTxt});
      renderChat();
      saveCurrentConversationToHistory(msg, isVoice);
      return;
    }
  } catch(e) {
    console.warn('Backend agro-gpt chat error:', e);
  }

  setTimeout(()=>{
    document.getElementById('typingIndicator')?.remove();
    chatHistory.push({role:'ai', text: pickFallbackReply(msg)});
    renderChat();
    saveCurrentConversationToHistory(msg, isVoice);
  }, 550);
}

function pickFallbackReply(msg){
  const m = msg.toLowerCase();
  const isKn = currentLang === 'kn';
  const isHi = currentLang === 'hi';

  if(m.includes('yellow spot') || m.includes('patton') || m.includes('ಹಳದಿ ಚುಕ್ಕೆ') || m.includes('पीले धब्बे')){
    if(isKn) return "🍅 ಟೊಮೆಟೊ ಎಲೆಗಳ ಮೇಲೆ ಹಳದಿ ಚುಕ್ಕೆಗಳು (ಅರ್ಲಿ ಬ್ಲೈಟ್):\\n1. ಸಾವಯವ ಪರಿಹಾರ: ಬೇವಿನ ಎಣ್ಣೆ (10,000 ppm) 3-4 ಮಿ.ಲೀ ಪ್ರತಿ ಲೀಟರ್ ನೀರಿಗೆ ಬೆರೆಸಿ ಸಿಂಪಡಿಸಿ.\\n2. ರಾಸಾಯನಿಕ ಪರಿಹಾರ: ಮ್ಯಾಂಕೋಜೆಬ್ 75% WP @ 2.5 ಗ್ರಾಂ/ಲೀಟರ್ ಅಥವಾ 1% ಬೋರ್ಡೊ ಮಿಶ್ರಣವನ್ನು ಮುಂಜಾನೆ (6:30–9:00 AM) ಸಿಂಪಡಿಸಿ.";
    if(isHi) return "🍅 टमाटर की पत्तियों पर पीले धब्बे (अर्ली ब्लाइट):\\n1. जैविक उपाय: नीम तेल (10,000 ppm) 3-4 मिली/लीटर पानी में मिलाकर छिड़काव करें।\\n2. रासायनिक उपचार: मैंकोजेब 75% WP @ 2.5 ग्राम/लीटर या 1% बोर्डो मिश्रण का सुबह छिड़काव करें।";
    return "🍅 Yellow Spots on Tomato Leaves (Early Blight):\\n1. Remove lower infected leaves touching the soil.\\n2. Organic Spray: Neem Oil (10,000 ppm) @ 3–4 ml/L.\\n3. Fungicide Control: Foliar spray of Mancozeb 75% WP @ 2.5 g/L or 1% Bordeaux mixture during early morning (6:30–9:00 AM).";
  }
  if(m.includes('wheat') || m.includes('ಗೋಧಿ') || m.includes('गेहूं')){
    if(isKn) return "🌾 ಗೋಧಿ ಬಿತ್ತನೆಗೆ ಸೂಕ್ತ ಸಮಯ (ಹಿಂಗಾರು ಹಂಗಾಮು):\\n• ನವೆಂಬರ್ 1 ರಿಂದ ನವೆಂಬರ್ 25 ರೊಳಗೆ ಬಿತ್ತನೆ ಮಾಡುವುದು ಅತ್ಯುತ್ತಮ.\\n• ಬೀಜದ ಪ್ರಮಾಣ: ಪ್ರತಿ ಎಕರೆಗೆ 40–45 ಕೆ.ಜಿ.\\n• ಮೊದಲ ನೀರಾವರಿ: ಬಿತ್ತಿದ 21 ದಿನಗಳ ನಂತರ (CRI ಹಂತ) ತಪ್ಪದೇ ನೀರು ಹಾಯಿಸಿ.";
    if(isHi) return "🌾 गेहूं बोने का सबसे अच्छा समय (रबी सीजन):\\n• 1 नवंबर से 25 नवंबर के बीच बुवाई सर्वोत्तम है (अंकुरण तापमान 20°C–25°C)।\\n• बीज दर: 40–45 किग्रा प्रति एकड़।\\n• पहली सिंचाई बुवाई के 21 दिन बाद (CRI अवस्था) अवश्य करें।";
    return "🌾 Best Time to Plant Wheat (Rabi Season):\\n• Optimal Sowing Window: November 1st to November 25th (ideal temperature 20°C–25°C).\\n• Seed Rate: 40–45 kg/acre.\\n• Critical Irrigation: Apply first irrigation at Crown Root Initiation (21 days after sowing).";
  }
  if(m.includes('pm-kisan') || m.includes('pm kisan') || m.includes('scheme') || m.includes('ಯೋಜನೆ') || m.includes('योजना')){
    if(isKn) return "🏛️ PM-KISAN ಸಮ್ಮಾನ್ ನಿಧಿ ಯೋಜನೆ:\\n• ಸೌಲಭ್ಯ: ಅರ್ಹ ರೈತರಿಗೆ ವಾರ್ಷಿಕ ₹6,000 (ಮೂರು ಕಂತುಗಳಲ್ಲಿ ತಲಾ ₹2,000 ನೇರ ಬ್ಯಾಂಕ್ ಖಾತೆಗೆ).\\n• ದಾಖಲೆಗಳು: ಆಧಾರ್ ಕಾರ್ಡ್, ಜಮೀನಿನ ಪಹಣಿ (RTC), ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್.\\n• ಅರ್ಜಿ ಸಲ್ಲಿಸಲು pmkisan.gov.in ಅಥವಾ ಹತ್ತಿರದ ರೈತ ಸಂಪರ್ಕ ಕೇಂದ್ರಕ್ಕೆ ಭೇಟಿ ನೀಡಿ.";
    if(isHi) return "🏛️ PM-KISAN सम्मान निधि योजना:\\n• लाभ: ₹6,000 प्रति वर्ष (₹2,000 की 3 किस्तों में सीधे बैंक खाते में)।\\n• आवश्यक दस्तावेज: आधार कार्ड, भूमि रिकॉर्ड (खसरा/खतौनी/RTC), बैंक खाता।\\n• आवेदन: pmkisan.gov.in पर 'New Farmer Registration' चुनें या नजदीकी CSC केंद्र जाएं।";
    return "🏛️ How to Apply for PM-KISAN Scheme:\\n• Benefit: ₹6,000/year in 3 installments of ₹2,000 via Direct Benefit Transfer.\\n• Documents Needed: Aadhaar card, Land record (RTC/Pahani), Aadhaar-linked bank account.\\n• Apply online at pmkisan.gov.in -> 'New Farmer Registration' and complete OTP e-KYC.";
  }
  if(m.includes('sugarcane') || m.includes('ಕಬ್ಬಿನ') || m.includes('ಕಬ್ಬು') || m.includes('गन्ने') || m.includes('गन्ना')){
    if(isKn) return "🎋 ಕಬ್ಬಿನ ಬೆಳೆಗೆ ಪ್ರತಿ ಎಕರೆಗೆ ಯೂರಿಯಾ ಪ್ರಮಾಣ:\\n• ಒಟ್ಟು ಶಿಫಾರಸು: ಪ್ರತಿ ಎಕರೆಗೆ 220 ರಿಂದ 250 ಕೆ.ಜಿ ಬೇವಿನ ಲೇಪಿತ ಯೂರಿಯಾ (3 ಕಂತುಗಳಲ್ಲಿ).\\n• 1ನೇ ಕಂತು (30-45 ದಿನ): 75 ಕೆ.ಜಿ/ಎಕರೆ.\\n• 2ನೇ ಕಂತು (60-75 ದಿನ): 75 ಕೆ.ಜಿ/ಎಕರೆ.\\n• 3ನೇ ಕಂತು (90-110 ದಿನ - ಮಣ್ಣು ಏರಿಸುವಾಗ): 75–90 ಕೆ.ಜಿ/ಎಕರೆ.";
    if(isHi) return "🎋 गन्ने के लिए प्रति एकड़ यूरिया की खुराक:\\n• कुल आवश्यकता: 220 से 250 किग्रा नीम-लेपित यूरिया प्रति एकड़ (3 चरणों में)।\\n• पहली खुराक (30-45 दिन): 75 किग्रा/एकड़।\\n• दूसरी खुराक (60-75 दिन): 75 किग्रा/एकड़।\\n• तीसरी खुराक (90-110 दिन - मिट्टी चढ़ाते समय): 75–90 किग्रा/एकड़।";
    return "🎋 Urea Dose per Acre for Sugarcane:\\n• Total Recommended Dose: 220 to 250 kg Neem-Coated Urea per acre split into 3 applications:\\n  1. 30–45 days after planting (Tillering): 75 kg/acre.\\n  2. 60–75 days after planting: 75 kg/acre.\\n  3. 90–110 days after planting (Earthing-up): 75–90 kg/acre.";
  }
  if(m.includes('weather')||m.includes('rain')||m.includes('barish')||m.includes('mausam')||m.includes('ಹವಾಮಾನ')||m.includes('ಮಳೆ')){
    if(isKn) return "🌦️ ಇಂದಿನ ಹವಾಮಾನ: ಸುಮಾರು 28°C ಮತ್ತು ಭಾಗಶಃ ಮೋಡವಿದೆ. ತೇವಾಂಶ 65% ಆಗಿದೆ. ಮುಂಜಾನೆ 6:30 ರಿಂದ 9:00 ರ ನಡುವೆ ಸಿಂಪಡಣೆಗೆ ಸೂಕ್ತ ಸಮಯ.";
    if(isHi) return "🌦️ आज का मौसम: लगभग 28°C और आंशिक रूप से बादल छाए हैं। नमी 65% है। सुबह 6:30 से 9:00 बजे के बीच छिड़काव के लिए अनुकूल समय है।";
    return "🌦️ Live Weather: It's 28°C and partly cloudy with 65% humidity. Early morning (6:30 - 9:00 AM) is optimal for crop spraying.";
  }
  if(m.includes('mandi')||m.includes('price')||m.includes('rate')||m.includes('bhaav')||m.includes('ಮಂಡಿ')||m.includes('ದರ')||m.includes('ಬೆಲೆ')){
    if(isKn) return "📈 ಮಂಡ್ಯ ಮತ್ತು ಕೋಲಾರ ಎಪಿಎಂಸಿ ಮಂಡಿಯಲ್ಲಿ ಟೊಮೆಟೊ ₹1,600/ಕ್ವಿಂಟಾಲ್ ದರದಲ್ಲಿದೆ. ಸಂಪೂರ್ಣ ದರಗಳಿಗಾಗಿ ಮಂಡಿ ಮೆನು ತೆರೆಯಿರಿ.";
    if(isHi) return "📈 मंड्या और कोलार एपीएमसी मंडी में टमाटर ₹1,600/क्विंटल पर कारोबार कर रहा है। सभी मंडियों के भाव देखने के लिए मंडी टैब खोलें।";
    return "📈 Tomato is currently trading at ₹1,600/quintal in Kolar & Mandya APMC. Open the Mandi tab for live observations across all APMC markets.";
  }
  if(m.includes('diagnos')||m.includes('crop')||m.includes('leaf')||m.includes('disease')||m.includes('bimari')||m.includes('ರೋಗ')||m.includes('ತಪಾಸಣೆ')){
    if(isKn) return "🌿 ನಿಮ್ಮ ಬೆಳೆಗೆ ರೋಗ ತಪಾಸಣೆ ಮಾಡಲು 'ರೋಗ ತಪಾಸಣೆ' ಮೆನುವಿನಲ್ಲಿ ಎಲೆಯ ಫೋಟೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ. AI ಮಾದರಿಯು ರೋಗ ಪತ್ತೆಹಚ್ಚಿ ಸಾವಯವ ಮತ್ತು ರಾಸಾಯನಿಕ ಚಿಕಿತ್ಸೆ ನೀಡುತ್ತದೆ.";
    if(isHi) return "🌿 अपनी फसल की जांच के लिए 'रोग निदान' टैब में पत्ती की फोटो अपलोड करें। हमारा AI रोग की पहचान कर जैविक और रासायनिक उपचार बताएगा।";
    return "🌿 You can upload a leaf photo in the Diagnose tab. Agro AI will detect the pathogen and recommend organic and chemical treatments.";
  }
  if(m.includes('fertilizer')||m.includes('khad')||m.includes('ಗೊಬ್ಬರ')||m.includes('ಯೂರಿಯಾ')){
    if(isKn) return "🌾 ನಿಮ್ಮ ಬೆಳೆಗೆ ಸಮತೋಲಿತ NPK 19:19:19 ಮತ್ತು ಬೇವಿನ ಹಿಂಡಿ ಬಳಸುವುದು ಉತ್ತಮ ಎಲೆ ಮತ್ತು ಬೇರಿನ ಬೆಳವಣಿಗೆಗೆ ಸಹಕಾರಿಯಾಗಿದೆ.";
    if(isHi) return "🌾 संतुलित फसल पोषण के लिए NPK 19:19:19 और नीम खली का प्रयोग करें जिससे जड़ों और पत्तियों का मजबूत विकास हो सके।";
    return "🌾 For balanced nutrition, apply NPK 19:19:19 water-soluble foliar spray @ 5g/L with neem cake basal nutrition.";
  }
  if(isKn) return "ನಮಸ್ಕಾರ! ನಾನು ಆಗ್ರೋ ಜಿಪಿಟಿ (Agro GPT). ಹವಾಮಾನ, ಮಂಡಿ ದರ, ಬೆಳೆ ರೋಗ ಮತ್ತು ಕೃಷಿ ಸಲಹೆಗಳಿಗಾಗಿ ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.";
  if(isHi) return "नमस्ते! मैं एग्रो जीपीटी (Agro GPT) हूँ। मैं मौसम, मंडी भाव, फसल रोग निदान और कृषि सलाह में आपकी सहायता कर सकता हूँ।";
  return "Namaste! I'm Agro GPT. I can assist you with hyperlocal weather, live mandi prices, leaf disease diagnosis, and agronomy advice.";
}

/* ================= DAILY FARM REPORT LOADER ================= */
async function loadDailyFarmReport(forceRegen = false) {
  const loc = (farmerProfile && farmerProfile.village) ? farmerProfile.village : 'Mandya';
  const crop = (farmerProfile && farmerProfile.crop) ? farmerProfile.crop : 'Tomato';
  const savedPhone = localStorage.getItem('agroai_brief_phone') || (session && session.phone) || '917019286323';
  const phoneEl = document.getElementById('dailyBriefPhone');
  if (phoneEl) phoneEl.textContent = savedPhone;

  const regenBtn = document.getElementById('dailyReportRegenBtn');
  if (forceRegen && regenBtn) {
    regenBtn.disabled = true;
    regenBtn.textContent = currentLang === 'kn' ? '↻ ರಚಿಸಲಾಗುತ್ತಿದೆ...' : (currentLang === 'hi' ? '↻ लोड हो रहा है...' : '↻ Regenerating...');
  }

  try {
    const res = await fetch(`/api/agro-gpt/daily-report?location=${encodeURIComponent(loc)}&crop=${encodeURIComponent(crop)}&language=${encodeURIComponent(currentLang)}`);
    if (res.ok) {
      const data = await res.json();
      const setTxt = (id, v) => { const el = document.getElementById(id); if (el && v) el.textContent = v; };
      setTxt('dailyReportDate', data.date);
      setTxt('dailyReportHeadline', data.headline);
      setTxt('dailyReportSummary', data.summary);
      setTxt('dailyReportWeather', data.weather);
      setTxt('dailyReportPest', data.pest_disease);
      setTxt('dailyReportAction', data.crop_action);
      setTxt('dailyReportMarket', data.market);
      setTxt('dailyReportQuote', data.quote);
    }
  } catch (e) {
    console.warn('Could not load daily farm report:', e);
  } finally {
    if (regenBtn) {
      regenBtn.disabled = false;
      const dict = I18N[currentLang] || I18N.en;
      regenBtn.textContent = dict.daily_report_regen_btn || '↻ Regenerate';
    }
  }
}

function changeDailyBriefPhone() {
  const current = localStorage.getItem('agroai_brief_phone') || '917019286323';
  const promptLbl = currentLang === 'kn'
    ? 'ದೈನಂದಿನ ಕೃಷಿ ವರದಿಗಾಗಿ ನಿಮ್ಮ ವಾಟ್ಸಾಪ್ ಸಂಖ್ಯೆಯನ್ನು ನಮೂದಿಸಿ:'
    : (currentLang === 'hi' ? 'दैनिक कृषि रिपोर्ट के लिए अपना व्हाट्सएप नंबर दर्ज करें:' : 'Enter WhatsApp number for your 6:30 AM IST Daily Farm Report:');
  const next = prompt(promptLbl, current);
  if (next && next.trim()) {
    const cleaned = next.trim();
    localStorage.setItem('agroai_brief_phone', cleaned);
    const phoneEl = document.getElementById('dailyBriefPhone');
    if (phoneEl) phoneEl.textContent = cleaned;
    showToast(currentLang === 'kn' ? 'ವಾಟ್ಸಾಪ್ ಸಂಖ್ಯೆ ನವೀಕರಿಸಲಾಗಿದೆ' : (currentLang === 'hi' ? 'व्हाट्सएप नंबर अपडेट किया गया' : 'WhatsApp number updated'));
  }
}'''

assert old_gpt_js in content, "old_gpt_js not found"
content = content.replace(old_gpt_js, new_gpt_js, 1)

# 2. Update initChat() to also initialize Agro GPT history & Daily Farm Report
old_init_chat = '''function initChat(){
  if(chatHistory.length===0){
    const greeting = (I18N[currentLang] || I18N.en).gpt_initial_greeting;
    chatHistory.push({role:'ai', text: greeting});
  }
  renderChat();
  renderSuggestChips();
  renderGptLangBar();
}'''

new_init_chat = '''function initChat(){
  renderChat();
  renderSuggestChips();
  renderGptLangBar();
  renderAgroGptHistory();
  loadDailyFarmReport();
}'''

assert old_init_chat in content, "old_init_chat not found"
content = content.replace(old_init_chat, new_init_chat, 1)

# 3. Update setLang(code) to also refresh the Daily Farm Report in the selected language
old_set_lang_tail = '''  renderGptLangBar();
  loadRealWeather();
}'''

new_set_lang_tail = '''  renderGptLangBar();
  loadRealWeather();
  loadDailyFarmReport();
}'''

assert old_set_lang_tail in content, "old_set_lang_tail not found"
content = content.replace(old_set_lang_tail, new_set_lang_tail, 1)

# 4. Update applyTranslations(lang) to translate all Agro GPT and Daily Farm Report UI labels
old_apply_gpt = '''  // Agro GPT
  setTxt('gptTitle', dict.gpt_title);
  setTxt('gptCallBtn', dict.gpt_call_btn);
  const chatInput = document.getElementById('chatInput');
  if(chatInput) chatInput.placeholder = dict.gpt_placeholder;'''

new_apply_gpt = '''  // Agro GPT (Strictly Agro GPT everywhere)
  setTxt('gptTitle', dict.gpt_title || 'Agro GPT');
  setTxt('gptHeroGreeting', lang === 'kn' ? "ನಮಸ್ಕಾರ! ನಾನು ಆಗ್ರೋ ಜಿಪಿಟಿ." : (lang === 'hi' ? "नमस्ते! मैं एग्रो जीपीटी हूँ।" : "Namaste! I'm Agro GPT."));
  setTxt('gptHeroSubtitle', lang === 'kn' ? "ಆಗ್ರೋ AI ನ ಕೇಂದ್ರ ಬುದ್ಧಿಮತ್ತೆ. ಪ್ರತಿ ಉತ್ತರಕ್ಕೂ ಮುನ್ನ ನಿಮ್ಮ ಜಮೀನಿನ ಹವಾಮಾನ, ಸ್ಥಳ, ಬೆಳೆ ಮತ್ತು ಇತಿಹಾಸವನ್ನು ಓದುತ್ತೇನೆ." : (lang === 'hi' ? "एग्रो AI का केंद्रीय मस्तिष्क। हर जवाब से पहले मैं आपके खेत का मौसम, स्थान, फसल और इतिहास पढ़ता हूँ।" : "The central AI brain of Agro AI. I read your farm's weather, location, crop, and history before every answer."));
  setTxt('gptHistoryToggleLbl', lang === 'kn' ? 'ಇತಿಹಾಸ' : (lang === 'hi' ? 'इतिहास' : 'History'));
  setTxt('gptNewChatTopBtn', lang === 'kn' ? '+ ಹೊಸ ಚಾಟ್' : (lang === 'hi' ? '+ नई चैट' : '+ New chat'));
  setTxt('gptSidebarNewChatBtn', lang === 'kn' ? '+ ಹೊಸ ಚಾಟ್' : (lang === 'hi' ? '+ नई चैट' : '+ New chat'));
  setTxt('gptSpeakInsteadTxt', lang === 'kn' ? 'ಧ್ವನಿಯಲ್ಲಿ ಮಾತನಾಡಿ' : (lang === 'hi' ? 'बोलकर पूछें' : 'Speak instead'));
  setTxt('askAgroGptBtn', lang === 'kn' ? 'ಆಗ್ರೋ ಜಿಪಿಟಿ ಕೇಳಿ' : (lang === 'hi' ? 'एग्रो जीपीटी से पूछें' : 'Ask Agro GPT'));
  setTxt('talkAgroGptBtnTxt', lang === 'kn' ? 'ಆಗ್ರೋ ಜಿಪಿಟಿ ಜೊತೆ ಮಾತನಾಡಿ — 12 ಭಾರತೀಯ ಭಾಷೆಗಳು' : (lang === 'hi' ? 'एग्रो जीपीटी से बात करें — 12 भारतीय भाषाएं' : 'Talk to Agro GPT — 12 Indian languages'));
  setTxt('talkAgroGptWakeTxt', lang === 'kn' ? '“ಹಾಯ್ ಆಗ್ರೋ AI” ಎಂದು ಹೇಳಿ, ನಂತರ ಕನ್ನಡ, ಹಿಂದಿ, ತಮಿಳು, ತೆಲುಗು, ಮರಾಠಿ ಮುಂತಾದ ಭಾಷೆಗಳಲ್ಲಿ ಕೇಳಿ.' : (lang === 'hi' ? 'इसे जगाने के लिए “हाय एग्रो AI” कहें, फिर हिंदी, कन्नड़, तमिल, तेलुगु, मराठी आदि में पूछें।' : 'Say “Hi Agro AI” to wake it, then ask in Hindi, Kannada, Tamil, Telugu, Marathi and more.'));
  setTxt('gptSideProfile', lang === 'kn' ? '👤 ಪ್ರೊಫೈಲ್ ಮತ್ತು ಜಮೀನು' : (lang === 'hi' ? '👤 प्रोफ़ाइल और खेत' : '👤 Profile & farm'));
  setTxt('gptSideSignOut', lang === 'kn' ? 'ಸೈನ್ ಔಟ್' : (lang === 'hi' ? 'साइन आउट' : 'Sign out'));
  const chatInput = document.getElementById('chatInput');
  if(chatInput) chatInput.placeholder = lang === 'kn' ? 'ಬೆಳೆಗಳು, ಹವಾಮಾನ, ಮಂಡಿ ದರಗಳು, ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ...' : (lang === 'hi' ? 'फसलों, मौसम, मंडी भाव, योजनाओं के बारे में पूछें...' : 'Ask about crops, weather, mandi prices, schemes...');

  // Daily Farm Report Labels
  setTxt('dailyReportTitle', lang === 'kn' ? 'ದೈನಂದಿನ ಕೃಷಿ ವರದಿ' : (lang === 'hi' ? 'दैनिक कृषि रिपोर्ट' : 'Daily farm report'));
  setTxt('dailyReportSub', lang === 'kn' ? 'ನಿಮ್ಮ ಜಮೀನಿಗಾಗಿ ತಾಜಾ AI ಸಾರಾಂಶ — ಇಂದಿನ ಹವಾಮಾನ, ಕೀಟಗಳು ಮತ್ತು ಕ್ರಮಗಳು.' : (lang === 'hi' ? 'आपके खेत के लिए ताजा AI सारांश — आज का मौसम, कीट और कार्य।' : "Fresh AI brief for your farm — today's weather, pests, and actions."));
  setTxt('dailyReportRegenBtn', lang === 'kn' ? '↻ ಮರು-ರಚಿಸಿ' : (lang === 'hi' ? '↻ पुनः लोड करें' : '↻ Regenerate'));
  setTxt('dailyWaStatus', lang === 'kn' ? 'ವಾಟ್ಸಾಪ್ ಅಧಿಸೂಚನೆ ಸಕ್ರಿಯವಾಗಿದೆ' : (lang === 'hi' ? 'व्हाट्सएप सूचनाएं चालू हैं' : 'WhatsApp notifications on'));
  setTxt('dailyWaDescPrefix', lang === 'kn' ? 'ದೈನಂದಿನ ವರದಿಯನ್ನು ಪ್ರತಿದಿನ ಬೆಳಿಗ್ಗೆ 6:30 ಕ್ಕೆ' : (lang === 'hi' ? 'दैनिक रिपोर्ट सुबह 6:30 बजे' : 'Daily brief will be sent to'));
  setTxt('dailyWaDescSuffix', lang === 'kn' ? 'ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ.' : (lang === 'hi' ? 'पर भेजी जाएगी।' : 'at 6:30 AM IST.'));
  setTxt('dailyWaChangeLink', lang === 'kn' ? 'ಸಂಖ್ಯೆ ಬದಲಿಸಿ' : (lang === 'hi' ? 'नंबर बदलें' : 'Change number'));
  setTxt('dailyCardLblWeather', lang === 'kn' ? 'ಹವಾಮಾನ' : (lang === 'hi' ? 'मौसम' : 'WEATHER'));
  setTxt('dailyCardLblPest', lang === 'kn' ? 'ಕೀಟ ಮತ್ತು ರೋಗ' : (lang === 'hi' ? 'कीट एवं रोग' : 'PEST & DISEASE'));
  setTxt('dailyCardLblAction', lang === 'kn' ? 'ಬೆಳೆ ಕ್ರಮ' : (lang === 'hi' ? 'फसल कार्य' : 'CROP ACTION'));
  setTxt('dailyCardLblMarket', lang === 'kn' ? 'ಮಾರುಕಟ್ಟೆ' : (lang === 'hi' ? 'बाजार / मंडी' : 'MARKET'));'''

assert old_apply_gpt in content, "old_apply_gpt not found"
content = content.replace(old_apply_gpt, new_apply_gpt, 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated JS functions and translations for Agro GPT and Daily Farm Report.")
