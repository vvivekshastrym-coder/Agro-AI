// ═══════════════════════════════════════════════════════════
// AGRO AI — REPORT GENERATOR v2.0
// Generates shareable HTML reports and PDF downloads
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  // ── Weather Icon Mapping ───────────────────────────────────
  function getWeatherEmoji(condition) {
    const map = {
      'Clear': '☀️', 'Sunny': '☀️',
      'Clouds': '⛅', 'Overcast': '☁️',
      'Rain': '🌧️', 'Drizzle': '🌦️',
      'Thunderstorm': '⛈️', 'Storm': '⛈️',
      'Snow': '❄️', 'Mist': '🌫️',
      'Haze': '🌫️', 'Fog': '🌁',
    };
    for (const key in map) {
      if (condition?.toLowerCase().includes(key.toLowerCase())) return map[key];
    }
    return '🌤️';
  }

  function getSeverityColor(severity) {
    const colors = { none: '#22c55e', mild: '#f59e0b', moderate: '#f97316', severe: '#ef4444' };
    return colors[severity] || '#6b7280';
  }

  function getSeverityLabel(severity) {
    const labels = { none: 'HEALTHY', mild: 'MILD', moderate: 'MODERATE', severe: 'SEVERE' };
    return labels[severity] || 'UNKNOWN';
  }

  // ── Generate Diagnosis Report HTML ─────────────────────────
  function generateDiagnosisReportHTML(report, imageDataUrl) {
    const farmer = window.KisanEngine?.getFarmer() || {};
    const farm = window.KisanEngine?.getFarm() || {};
    const weather = window.KisanEngine?.getWeather();
    const date = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' });
    const time = new Date().toLocaleTimeString('en-IN');
    const reportId = 'AGR-' + Date.now().toString(36).toUpperCase();
    const sevColor = getSeverityColor(report.severity);

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agro AI Diagnosis Report — ${reportId}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: #f0f4f0; color: #1a2e1a; }
  .report { max-width: 700px; margin: 0 auto; background: #fff; }
  .header { background: linear-gradient(135deg, #0e1f11, #1a4a24); color: #fff; padding: 32px; }
  .logo { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
  .logo-icon { background: linear-gradient(135deg, #f59e0b, #22c55e); width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 900; color: #0e1f11; }
  .logo-text { font-size: 22px; font-weight: 800; }
  .report-title { font-size: 28px; font-weight: 800; margin-bottom: 8px; }
  .report-meta { opacity: 0.7; font-size: 13px; }
  .section { padding: 24px 32px; border-bottom: 1px solid #e8f0e8; }
  .section-title { font-size: 12px; font-weight: 700; color: #6b8f6b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 16px; }
  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .info-item label { font-size: 11px; color: #6b8f6b; display: block; margin-bottom: 4px; }
  .info-item span { font-size: 15px; font-weight: 600; }
  .disease-card { background: ${sevColor}18; border: 2px solid ${sevColor}; border-radius: 16px; padding: 20px; text-align: center; margin: 8px 0; }
  .disease-name { font-size: 24px; font-weight: 800; color: ${sevColor}; margin-bottom: 8px; }
  .confidence-bar { height: 8px; background: #e5f0e5; border-radius: 4px; overflow: hidden; margin: 8px 0; }
  .confidence-fill { height: 100%; background: ${sevColor}; border-radius: 4px; width: ${report.confidence || 0}%; }
  .severity-badge { display: inline-block; background: ${sevColor}; color: #fff; padding: 4px 16px; border-radius: 999px; font-size: 12px; font-weight: 700; }
  .treatment-box { background: #f0f8f0; border-left: 4px solid #22c55e; padding: 16px; border-radius: 0 12px 12px 0; margin: 8px 0; }
  .treatment-box.chemical { border-color: #f59e0b; background: #fffbeb; }
  .treatment-box.warning { border-color: #ef4444; background: #fef2f2; }
  .treatment-title { font-size: 12px; font-weight: 700; margin-bottom: 8px; }
  .crop-image { width: 100%; max-height: 280px; object-fit: cover; border-radius: 12px; }
  .weather-mini { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .weather-mini-item { text-align: center; background: #f0f8f0; border-radius: 10px; padding: 12px; }
  .footer { background: #0e1f11; color: rgba(255,255,255,0.7); padding: 24px 32px; text-align: center; font-size: 12px; }
  .report-id { font-family: monospace; background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; }
  @media print { body { background: #fff; } }
</style>
</head>
<body>
<div class="report">
  <div class="header">
    <div class="logo">
      <div class="logo-icon">🌾</div>
      <div class="logo-text">Agro AI</div>
    </div>
    <div class="report-title">Crop Diagnosis Report</div>
    <div class="report-meta">${date} | ${time} | Report ID: ${reportId}</div>
  </div>

  ${imageDataUrl ? `<img src="${imageDataUrl}" class="crop-image" alt="Diagnosed crop">` : ''}

  <div class="section">
    <div class="section-title">👨‍🌾 Farmer & Farm Details</div>
    <div class="info-grid">
      <div class="info-item"><label>Farmer Name</label><span>${farmer.name || 'Not specified'}</span></div>
      <div class="info-item"><label>Phone</label><span>${farmer.phone || 'Not specified'}</span></div>
      <div class="info-item"><label>Location</label><span>${farm.location_name || farmer.district || 'Not specified'}</span></div>
      <div class="info-item"><label>Farm Size</label><span>${farm.acres || '?'} Acres</span></div>
      <div class="info-item"><label>Current Crops</label><span>${(farm.crops || []).join(', ') || 'Not specified'}</span></div>
      <div class="info-item"><label>State</label><span>${farmer.state || 'Karnataka'}</span></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">🔬 Diagnosis Result</div>
    <div class="disease-card">
      <div class="disease-name">${report.disease || 'Analysis Complete'}</div>
      <div style="font-size:14px; color: #555; margin-bottom: 12px;">
        Detected on: <strong>${report.crop || 'Unknown Crop'}</strong>
        ${report.scientific_name ? `<br><em>${report.scientific_name}</em>` : ''}
      </div>
      <div class="confidence-bar"><div class="confidence-fill"></div></div>
      <div style="font-size:13px; margin-bottom: 12px;">AI Confidence: <strong>${report.confidence || 0}%</strong></div>
      <div class="severity-badge">${getSeverityLabel(report.severity)} SEVERITY</div>
    </div>
    <p style="margin-top:16px; font-size:14px; line-height:1.6; color:#374151;">${report.description || ''}</p>
  </div>

  <div class="section">
    <div class="section-title">🦠 Cause</div>
    <p style="font-size:14px; line-height:1.6;">${report.cause || 'Unknown'}</p>
  </div>

  <div class="section">
    <div class="section-title">💊 Treatment Plan</div>
    <div class="treatment-box">
      <div class="treatment-title">🌿 ORGANIC TREATMENT</div>
      <p style="font-size:14px; line-height:1.6;">${report.organic_treatment || 'Consult local agricultural officer'}</p>
    </div>
    <div class="treatment-box chemical">
      <div class="treatment-title">🧪 CHEMICAL TREATMENT</div>
      <p style="font-size:14px; line-height:1.6;">${report.chemical_treatment || 'No specific recommendation'}</p>
    </div>
    <div class="treatment-box warning">
      <div class="treatment-title">⏰ BEST SPRAY TIMING</div>
      <p style="font-size:14px; line-height:1.6;">${report.spray_timing || 'Early morning before 9 AM'}</p>
    </div>
    <p style="margin-top:16px; font-size:13px; color:#6b8f6b;">📅 Expected recovery: <strong>${report.recovery_days || 14} days</strong> with consistent treatment</p>
  </div>

  <div class="section">
    <div class="section-title">🛡️ Prevention Measures</div>
    <p style="font-size:14px; line-height:1.6;">${report.preventive_measures || 'Monitor plants regularly'}</p>
  </div>

  ${weather ? `
  <div class="section">
    <div class="section-title">🌤️ Current Weather Conditions</div>
    <div class="weather-mini">
      <div class="weather-mini-item">
        <div style="font-size:24px;">${getWeatherEmoji(weather.condition)}</div>
        <div style="font-weight:700; font-size:20px;">${weather.temp}°C</div>
        <div style="font-size:11px; color:#6b8f6b;">${weather.condition}</div>
      </div>
      <div class="weather-mini-item">
        <div style="font-size:24px;">💧</div>
        <div style="font-weight:700; font-size:20px;">${weather.humidity}%</div>
        <div style="font-size:11px; color:#6b8f6b;">Humidity</div>
      </div>
      <div class="weather-mini-item">
        <div style="font-size:24px;">🌬️</div>
        <div style="font-weight:700; font-size:20px;">${weather.wind_speed} km/h</div>
        <div style="font-size:11px; color:#6b8f6b;">Wind Speed</div>
      </div>
    </div>
  </div>` : ''}

  <div class="footer">
    <p style="margin-bottom:8px;">🌾 <strong>Agro AI</strong> — AI-Powered Agriculture Operating System</p>
    <p>Report ID: <span class="report-id">${reportId}</span></p>
    <p style="margin-top:8px;">For expert advice, contact your local Krishi Vigyan Kendra (KVK) or call Kisan Call Center: 1800-180-1551</p>
  </div>
</div>
</body>
</html>`;
  }

  // ── Print / Download as PDF ────────────────────────────────
  function downloadPDF(report, imageDataUrl) {
    const html = generateDiagnosisReportHTML(report, imageDataUrl);
    const printWindow = window.open('', '_blank', 'width=800,height=900');
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.onload = () => {
      setTimeout(() => {
        printWindow.print();
      }, 500);
    };
  }

  // ── Plain Text for WhatsApp ────────────────────────────────
  function getDiagnosisText(report) {
    const farmer = window.KisanEngine?.getFarmer() || {};
    return `AGRO AI DIAGNOSIS | ${new Date().toLocaleDateString('en-IN')}
Farmer: ${farmer.name || 'N/A'} | Crop: ${report.crop}
Disease: ${report.disease} | Severity: ${report.severity?.toUpperCase()}
Confidence: ${report.confidence}%
Treatment: ${report.organic_treatment?.substring(0, 100)}...
Spray Time: ${report.spray_timing}`;
  }

  // ── Expose ─────────────────────────────────────────────────
  window.KisanReports = {
    generateDiagnosisReportHTML,
    downloadPDF,
    getDiagnosisText,
    getWeatherEmoji,
    getSeverityColor,
  };

  console.log('📄 KisanReports v2.0 loaded');
})();
