// ═══════════════════════════════════════════════════════════
// AGRO AI — WHATSAPP INTEGRATION v2.0
// Share reports, alerts, and farm updates via WhatsApp
// Uses wa.me deep links (free, works on all devices)
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  // ── Check if user has WhatsApp enabled ────────────────────
  function isEnabled(category) {
    if (!window.KisanEngine) return true;
    const settings = window.KisanEngine.getSettings();
    if (!settings.whatsapp_enabled) return false;
    if (category && settings.whatsapp_categories) {
      return settings.whatsapp_categories[category] !== false;
    }
    return true;
  }

  function getPhone() {
    if (!window.KisanEngine) return '';
    const farmer = window.KisanEngine.getFarmer();
    return farmer.whatsapp_number || farmer.phone || '';
  }

  function getFarmerName() {
    if (!window.KisanEngine) return 'Farmer';
    return window.KisanEngine.getFarmer().name || 'Farmer';
  }

  // ── Share via WhatsApp ─────────────────────────────────────
  function share(message, phone) {
    const encoded = encodeURIComponent(message);
    const target = phone ? `https://wa.me/${phone.replace(/[^0-9]/g, '')}?text=${encoded}`
      : `https://wa.me/?text=${encoded}`;
    window.open(target, '_blank');
  }

  // ── Diagnosis Report ───────────────────────────────────────
  function shareDiagnosisReport(report) {
    if (!isEnabled('diagnosis')) return false;
    const farmer = getFarmerName();
    const farm = window.KisanEngine?.getFarm();
    const location = farm?.location_name || window.KisanEngine?.get('farmer.district') || 'India';
    const date = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const time = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

    const severity_emoji = { none: '✅', mild: '⚠️', moderate: '🔶', severe: '🚨' };
    const sev = report.severity || 'mild';

    const msg = `🌾 *AGRO AI — CROP DIAGNOSIS REPORT*
━━━━━━━━━━━━━━━━━━━━
👨‍🌾 Farmer: *${farmer}*
📍 Location: ${location}
📅 Date: ${date} | ${time}
━━━━━━━━━━━━━━━━━━━━

🌿 *CROP*: ${report.crop || 'Unknown'}
🔬 *DISEASE*: ${report.disease || 'Unknown'}
${report.scientific_name ? `🔬 _Scientific: ${report.scientific_name}_\n` : ''}🎯 *Confidence*: ${report.confidence || 0}%
${severity_emoji[sev]} *Severity*: ${sev.toUpperCase()}

📋 *CAUSE*:
${report.cause || 'Unknown cause'}

🌿 *ORGANIC TREATMENT*:
${report.organic_treatment || 'Consult local agricultural officer'}

💊 *CHEMICAL TREATMENT*:
${report.chemical_treatment || 'No specific recommendation'}

⏰ *BEST SPRAY TIME*:
${report.spray_timing || 'Early morning'}

📅 *Expected Recovery*: ${report.recovery_days || 14} days

🛡️ *PREVENTION*:
${report.preventive_measures || 'Monitor regularly'}
━━━━━━━━━━━━━━━━━━━━
🤖 _Powered by Agro AI_ 🌱
_For expert support, consult your local KVK_`;

    share(msg, getPhone());
    return true;
  }

  // ── Weather Alert ──────────────────────────────────────────
  function shareWeatherAlert(weather, advisory) {
    if (!isEnabled('weather')) return false;
    const farmer = getFarmerName();
    const loc = weather.location_name || weather.city || 'your location';

    const msg = `🌤️ *AGRO AI — WEATHER ALERT*
━━━━━━━━━━━━━━━━━━━━
👨‍🌾 ${farmer} | 📍 ${loc}

🌡️ *Today*: ${weather.temp}°C (Feels ${weather.feels_like}°C)
💧 Humidity: ${weather.humidity}%
🌬️ Wind: ${weather.wind_speed} km/h
☁️ Condition: ${weather.condition}
${weather.rain_1h > 0 ? `🌧️ Rain: ${weather.rain_1h}mm last hour\n` : ''}
📅 *7-Day Forecast*:
${(weather.forecast || []).slice(0, 5).map(f => `${f.day}: ${f.condition} | ${f.temp_max}°/${f.temp_min}° | Rain: ${f.rain}mm`).join('\n')}

${advisory ? `\n🤖 *AI FARM ADVISORY*:\n${advisory}` : ''}
━━━━━━━━━━━━━━━━━━━━
🤖 _Powered by Agro AI_ 🌱`;

    share(msg, getPhone());
    return true;
  }

  // ── Market Price Alert ─────────────────────────────────────
  function shareMarketAlert(prices, topMover) {
    if (!isEnabled('market')) return false;
    const farmer = getFarmerName();
    const date = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });

    const priceList = (prices || []).slice(0, 8).map(p =>
      `${p.commodity} (${p.market}): ₹${p.modal_price}/q`
    ).join('\n');

    const msg = `📈 *AGRO AI — MANDI PRICE UPDATE*
━━━━━━━━━━━━━━━━━━━━
👨‍🌾 ${farmer} | 📅 ${date}

💹 *TODAY'S PRICES*:
${priceList}
${topMover ? `\n🔥 *TOP MOVER*: ${topMover.commodity} ${topMover.change > 0 ? '📈 +' : '📉 '}${Math.abs(topMover.change || 0)}% at ₹${topMover.modal_price}/q` : ''}

⏰ _Updated: ${new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}_
━━━━━━━━━━━━━━━━━━━━
🤖 _Powered by Agro AI_ 🌱`;

    share(msg, getPhone());
    return true;
  }

  // ── Daily Digest ───────────────────────────────────────────
  function shareDailyDigest(digest) {
    if (!isEnabled('daily_digest')) return false;
    const msg = `${digest}\n\n🤖 _Sent by Agro AI_ 🌱\n_Your AI Agriculture Operating System_`;
    share(msg, getPhone());
    return true;
  }

  // ── GPT Response Share ─────────────────────────────────────
  function shareGptResponse(question, answer) {
    if (!isEnabled('gpt_responses')) return false;
    const farmer = getFarmerName();
    const msg = `🤖 *AGRO AI — KISAN GPT ANSWER*
━━━━━━━━━━━━━━━━━━━━
👨‍🌾 ${farmer}

❓ *Your Question*:
${question}

💡 *Kisan GPT Answer*:
${answer}
━━━━━━━━━━━━━━━━━━━━
🤖 _Powered by Agro AI_ 🌱
_Ask more questions: bit.ly/agroai_`;

    share(msg, getPhone());
    return true;
  }

  // ── Generic Share ──────────────────────────────────────────
  function shareText(text) {
    share(text, getPhone());
  }

  // ── Auto-trigger on events ─────────────────────────────────
  if (window.KisanEngine) {
    // Auto-prompt after diagnosis if enabled
    window.KisanEngine.on('diagnosis.complete', (report) => {
      if (isEnabled('diagnosis')) {
        // Don't auto-send, but dispatch event for UI to show share button
        window.KisanEngine.dispatch('whatsapp.diagnosis.ready', report);
      }
    });

    // Auto-prompt after weather update if urgent
    window.KisanEngine.on('weather.updated', (weather) => {
      if (weather?.rain_1h > 10 && isEnabled('weather')) {
        window.KisanEngine.dispatch('whatsapp.weather.alert.ready', weather);
      }
    });
  }

  // ── Expose ─────────────────────────────────────────────────
  window.KisanWhatsApp = {
    share,
    shareText,
    shareDiagnosisReport,
    shareWeatherAlert,
    shareMarketAlert,
    shareDailyDigest,
    shareGptResponse,
    isEnabled,
  };

  console.log('📱 KisanWhatsApp v2.0 loaded');
})();
