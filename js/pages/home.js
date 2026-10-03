// ═══════════════════════════════════════════════════════════
// AGRO AI — HOME PAGE v2.0
// Living Dashboard: Farm Health, Live Weather, AI Tip, Market
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let digestLoaded = false;
  let digestText = '';

  function render(container) {
    const engine = window.KisanEngine;
    const farmer = engine?.getFarmer() || {};
    const farm = engine?.getFarm() || {};
    const weather = engine?.getWeather();
    const lastDiag = engine?.getLastDiagnosis();
    const market = engine?.getMarket();
    const healthScore = farm.health_score || 87;

    const hour = new Date().getHours();
    const greeting = hour < 12 ? '🌅 Good Morning' : hour < 17 ? '☀️ Good Afternoon' : '🌙 Good Evening';
    const farmerName = farmer.name || 'Farmer';

    container.innerHTML = `
      <!-- Greeting Header -->
      <div class="animate-slide-up" style="margin-bottom: 20px;">
        <p style="font-size: 13px; color: var(--text-muted); font-weight: 500; margin-bottom: 4px;">${greeting}</p>
        <h1 style="font-size: 26px; font-weight: 900; letter-spacing: -0.04em; margin-bottom: 4px;">
          ${farmerName} <span style="font-size: 22px;">👨‍🌾</span>
        </h1>
        <p style="font-size: 13px; color: var(--text-muted);">
          ${farm.location_name || farmer.district || 'Your Farm'} · ${new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}
        </p>
      </div>

      <!-- Farm Health + Weather Row -->
      <div class="grid-2" style="margin-bottom: 4px;">

        <!-- Farm Health Score -->
        <div class="glass-card glass-card-interactive card-glow-green animate-slide-up" 
             data-link="#/diagnose" style="text-align: center; padding: 20px 12px;">
          <div style="position: relative; width: 90px; height: 90px; margin: 0 auto 10px;">
            <svg class="health-ring-svg" width="90" height="90" viewBox="0 0 90 90">
              <circle class="health-ring-bg" cx="45" cy="45" r="38" stroke-width="7"/>
              <circle class="health-ring-fill" id="healthRingFill" cx="45" cy="45" r="38" stroke-width="7"
                style="stroke-dashoffset: ${283 - (283 * healthScore / 100)};"/>
            </svg>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); text-align: center;">
              <div style="font-size: 20px; font-weight: 900; color: var(--text); line-height: 1;">${healthScore}%</div>
              <div style="font-size: 9px; color: var(--text-muted); font-weight: 600; margin-top: 1px;">HEALTH</div>
            </div>
          </div>
          <div style="font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 4px;">Farm Health</div>
          <div class="badge ${healthScore >= 80 ? 'badge-success' : healthScore >= 60 ? 'badge-warning' : 'badge-danger'}">
            ${healthScore >= 80 ? '● Excellent' : healthScore >= 60 ? '● Good' : '● Needs Care'}
          </div>
        </div>

        <!-- Weather Mini Card -->
        <div class="glass-card glass-card-interactive animate-slide-up" id="weatherMiniCard"
             data-link="#/weather" style="padding: 20px 16px;">
          ${weather ? renderWeatherMini(weather) : renderWeatherLoading()}
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="glass-card animate-slide-up" style="padding: 16px;">
        <div class="section-title-sm" style="margin-bottom: 14px;">⚡ Quick Actions</div>
        <div class="grid-4">
          ${renderQuickAction('#/diagnose', '🔬', 'Diagnose')}
          ${renderQuickAction('#/kisan-gpt', '🤖', 'Ask AI')}
          ${renderQuickAction('#/weather', '🌤️', 'Weather')}
          ${renderQuickAction('#/market', '📈', 'Mandi')}
        </div>
      </div>

      <!-- AI Daily Digest -->
      <div class="glass-card card-glow-gold animate-slide-up" id="digestCard">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <div>
            <div class="section-title-sm">🤖 AI Daily Digest</div>
            <div style="font-size: 11px; color: var(--text-muted);">Powered by Gemini AI</div>
          </div>
          <span class="badge badge-warning">● Live</span>
        </div>
        <div id="digestText" style="font-size: 14px; line-height: 1.6; color: var(--text-secondary);">
          ${digestLoaded ? digestText : renderDigestLoading()}
        </div>
        ${!digestLoaded ? '' : `<button class="btn btn-whatsapp btn-sm" style="margin-top: 12px; width: auto;" onclick="KisanWhatsApp.shareDailyDigest(window._lastDigest)">📱 Share on WhatsApp</button>`}
      </div>

      <!-- Last Diagnosis -->
      ${lastDiag ? renderLastDiagnosis(lastDiag) : ''}

      <!-- Market Flash -->
      ${market?.prices?.length ? renderMarketFlash(market.prices) : renderMarketLoading()}

      <!-- Product Suite -->
      <div style="margin-bottom: 14px;">
        <div class="section-header">
          <div class="section-title-sm">🌾 AI Feature Suite</div>
        </div>
        <div class="grid-2">
          ${renderFeatureCard('#/diagnose', '🔬', 'Leaf Diagnosis', 'AI-powered crop disease detection', 'badge-success')}
          ${renderFeatureCard('#/kisan-gpt', '🗣️', 'Kisan GPT', 'Voice AI Agronomist', 'badge-warning')}
          ${renderFeatureCard('#/satellite', '🛰️', 'Digital Twin', 'NDVI satellite farm mapping', 'badge-info')}
          ${renderFeatureCard('#/soil-dna', '🧪', 'Soil DNA', 'Smart soil analysis & advice', 'badge-purple')}
          ${renderFeatureCard('#/drone', '🚁', 'Drone Scout', 'Book aerial farm scanning', 'badge-info')}
          ${renderFeatureCard('#/carbon', '🌍', 'Carbon Credits', 'Earn from sustainable farming', 'badge-success')}
        </div>
      </div>

      <!-- Footer -->
      <div style="text-align: center; padding: 20px 0 8px; border-top: 1px solid var(--border); margin-top: 8px;">
        <p style="font-size: 12px; color: var(--text-muted); font-weight: 500;">🌾 Agro AI — AI Operating System for Agriculture</p>
        <p style="font-size: 11px; color: var(--text-muted); margin-top: 4px; opacity: 0.5;">v2.0 · Powered by Gemini AI</p>
      </div>
    `;

    // Attach click handlers
    container.querySelectorAll('[data-link]').forEach(el => {
      el.addEventListener('click', () => {
        window.location.hash = el.getAttribute('data-link');
      });
    });

    // Animate health ring
    setTimeout(() => {
      const ring = container.querySelector('#healthRingFill');
      if (ring) {
        ring.style.transition = 'stroke-dashoffset 1.5s cubic-bezier(0.34, 1.2, 0.64, 1)';
      }
    }, 100);

    // Load weather if needed
    if (!weather || (window.KisanEngine?.isWeatherStale())) {
      loadWeather(container);
    }

    // Load AI digest if not loaded
    if (!digestLoaded) {
      loadDigest(container);
    }

    // Load market if needed
    if (!market?.prices?.length) {
      loadMarket(container);
    }
  }

  function renderWeatherMini(w) {
    const emoji = window.KisanReports?.getWeatherEmoji(w.condition) || '🌤️';
    return `
      <div style="margin-bottom: 8px;">
        <div style="font-size: 36px; line-height: 1;">${emoji}</div>
        <div style="font-size: 28px; font-weight: 900; letter-spacing: -0.04em; color: var(--text); line-height: 1.1;">
          ${w.temp}°
        </div>
        <div style="font-size: 12px; color: var(--text-secondary); text-transform: capitalize; margin-top: 4px;">${w.condition}</div>
      </div>
      <div style="font-size: 11px; color: var(--text-muted);">
        <div>💧 ${w.humidity}%</div>
        <div>🌬️ ${w.wind_speed} km/h</div>
        <div style="margin-top: 4px; font-weight: 600; color: var(--text-secondary); font-size: 12px;">${w.location_name || w.city || ''}</div>
      </div>
    `;
  }

  function renderWeatherLoading() {
    return `
      <div style="text-align:center; padding: 16px 0;">
        <div class="spinner" style="margin: 0 auto 12px;"></div>
        <div style="font-size: 12px; color: var(--text-muted);">Fetching weather...</div>
      </div>
    `;
  }

  function renderQuickAction(href, emoji, label) {
    return `
      <div class="glass-card-interactive" data-link="${href}" 
           style="background: var(--surface-2); border: 1px solid var(--border); border-radius: 14px; padding: 12px 6px; text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 0;">
        <div style="font-size: 24px; margin-bottom: 6px;">${emoji}</div>
        <div style="font-size: 11px; font-weight: 600; color: var(--text-secondary);">${label}</div>
      </div>
    `;
  }

  function renderLastDiagnosis(diag) {
    const sev = diag.severity || 'mild';
    const badgeClass = sev === 'severe' ? 'badge-danger' : sev === 'moderate' ? 'badge-warning' : 'badge-success';
    const date = new Date(diag.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
    return `
      <div class="glass-card glass-card-interactive animate-slide-up" data-link="#/diagnose">
        <div class="section-header" style="margin-bottom: 10px;">
          <div class="section-title-sm">🔬 Last Diagnosis</div>
          <span class="badge badge-info">${date}</span>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>
            <div style="font-size: 15px; font-weight: 700;">${diag.disease || 'N/A'}</div>
            <div style="font-size: 12px; color: var(--text-muted);">${diag.crop || ''} · ${diag.confidence || 0}% confidence</div>
          </div>
          <span class="badge ${badgeClass}">${sev.toUpperCase()}</span>
        </div>
      </div>
    `;
  }

  function renderMarketFlash(prices) {
    const top = prices.slice(0, 4);
    return `
      <div class="glass-card animate-slide-up">
        <div class="section-header" style="margin-bottom: 10px;">
          <div class="section-title-sm">📈 Market Flash</div>
          <span class="badge badge-live">● Live</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 0;">
          ${top.map(p => `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border);">
              <span style="font-size: 14px; font-weight: 600;">${p.commodity}</span>
              <div style="text-align: right;">
                <span style="font-size: 15px; font-weight: 800; color: var(--text);">₹${p.modal_price}</span>
                <span style="font-size: 10px; color: var(--text-muted);">/q</span>
                ${p.change !== undefined ? `<span style="font-size: 11px; font-weight: 600; color: ${p.change >= 0 ? 'var(--accent)' : 'var(--red)'}; margin-left: 4px;">${p.change >= 0 ? '▲' : '▼'} ${Math.abs(p.change)}%</span>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
        <a href="#/market" style="display: block; text-align: center; font-size: 13px; font-weight: 600; color: var(--accent); margin-top: 10px; cursor: pointer;">View All Prices →</a>
      </div>
    `;
  }

  function renderMarketLoading() {
    return `
      <div class="glass-card animate-slide-up">
        <div class="section-title-sm" style="margin-bottom: 12px;">📈 Market Flash</div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text" style="width: 80%;"></div>
        <div class="skeleton skeleton-text" style="width: 70%;"></div>
      </div>
    `;
  }

  function renderDigestLoading() {
    return `
      <div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text" style="width: 90%;"></div>
        <div class="skeleton skeleton-text" style="width: 80%;"></div>
        <div class="skeleton skeleton-text" style="width: 60%;"></div>
      </div>
    `;
  }

  function renderFeatureCard(href, icon, title, desc, badgeClass) {
    return `
      <div class="glass-card glass-card-interactive animate-slide-up" data-link="${href}" 
           style="padding: 16px; margin-bottom: 0;">
        <div style="font-size: 28px; margin-bottom: 10px;">${icon}</div>
        <div style="font-size: 14px; font-weight: 700; margin-bottom: 4px;">${title}</div>
        <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">${desc}</div>
      </div>
    `;
  }

  async function loadWeather(container) {
    const engine = window.KisanEngine;
    const api = window.KisanAPI;
    if (!engine || !api) return;

    try {
      let { lat, lon } = engine.getGPS();

      if (!lat || !lon) {
        try {
          const pos = await engine.requestGPS();
          lat = pos.lat; lon = pos.lon;
        } catch (e) {
          // Default to Mysore, Karnataka
          lat = 12.2958; lon = 76.6394;
        }
      }

      const weather = await api.fetchFullWeather(lat, lon);
      const miniCard = container.querySelector('#weatherMiniCard');
      if (miniCard) {
        miniCard.innerHTML = renderWeatherMini(weather);
      }
    } catch (e) {
      console.warn('[Home] Weather load failed:', e);
    }
  }

  async function loadDigest(container) {
    const api = window.KisanAPI;
    if (!api) return;

    try {
      const text = await api.getDailyDigest();
      digestText = text || '🌾 Farm looks healthy today. Check weather before any spraying activity.';
      digestLoaded = true;
      window._lastDigest = digestText;

      const el = container.querySelector('#digestText');
      if (el) {
        el.innerHTML = `<div style="white-space: pre-line; font-size: 14px; line-height: 1.6;">${digestText}</div>
          <button class="btn btn-whatsapp btn-sm" style="margin-top: 12px; width: auto;" 
                  onclick="KisanWhatsApp.shareDailyDigest(window._lastDigest)">📱 Share on WhatsApp</button>`;
      }
    } catch (e) {
      digestLoaded = true;
      digestText = '🌾 AI digest is currently unavailable. Check your Gemini API key in Settings.';
      const el = container.querySelector('#digestText');
      if (el) el.textContent = digestText;
    }
  }

  async function loadMarket(container) {
    const api = window.KisanAPI;
    const engine = window.KisanEngine;
    if (!api || !engine) return;

    try {
      const state = engine.getFarmer().state || 'Karnataka';
      const prices = await api.getMandiPrices(state);
      engine.setMarketPrices(prices);

      // Re-render market section if still on home
      const marketSection = container.querySelector('.animate-slide-up:last-of-type');
    } catch (e) {
      console.warn('[Home] Market load failed:', e);
    }
  }

  // Register
  if (window.KisanRouter) window.KisanRouter.register('/', render);
})();
