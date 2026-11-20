// ═══════════════════════════════════════════════════════════
// AGRO AI — HYPERLOCAL WEATHER v2.0
// Single Source of Truth Backend Integration
// Real-time GPS & Search across all Indian districts & towns
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let weatherData = null;
  let isLoading = false;
  let searchQuery = '';

  function render(container) {
    container.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 6px;">🌤️ Hyperlocal Weather</h1>
        <p style="font-size: 13px; color: var(--text-muted);">Real-time live weather data & AI spray window advisories across India</p>
      </div>

      <!-- Location Search & GPS Row -->
      <div class="glass-card" style="padding: 14px; margin-bottom: 16px;">
        <div style="display: flex; gap: 8px;">
          <input type="text" id="weatherLocationInput" placeholder="Search village, town, or district (e.g. Mysuru, Hassan, Mandya)..." value="${escapeHtml(searchQuery)}" style="flex: 1; height: 42px; border-radius: 10px; padding: 0 14px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 13px;">
          <button id="searchWeatherBtn" class="btn btn-primary btn-sm" style="padding: 0 16px; font-weight: 700;">🔍 Search</button>
          <button id="gpsWeatherBtn" class="btn btn-outline btn-sm" title="Use My Current GPS Location" style="padding: 0 12px; font-size: 16px;">📍</button>
        </div>
      </div>

      <div id="weatherContent">${renderContent()}</div>
    `;

    attachListeners(container);
    if (!weatherData && !isLoading) loadWeather(container);
  }

  function renderContent() {
    if (isLoading) {
      return `
        <div class="glass-card" style="padding: 36px 20px; text-align: center;">
          <div class="spinner" style="margin: 0 auto 14px;"></div>
          <p style="font-size: 14px; font-weight: 600; color: var(--text);">Fetching live weather metrics...</p>
          <p style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Connecting to OpenWeather API via Agro AI Backend</p>
        </div>
      `;
    }

    if (!weatherData || !weatherData.available) {
      return `
        <div class="glass-card" style="padding: 24px; text-align: center; border-left: 4px solid #EF4444;">
          <div style="font-size: 36px; margin-bottom: 10px;">⚠️</div>
          <h3 style="font-size: 16px; font-weight: 800; color: #DC2626; margin-bottom: 6px;">Live Weather Unavailable</h3>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">${weatherData?.message || 'Unable to retrieve live weather data.'}</p>
          <button id="retryWeatherBtn" class="btn btn-primary btn-sm" style="padding: 8px 18px;">🔄 Retry</button>
        </div>
      `;
    }

    const w = weatherData;
    const sprayBorderColor = w.spray_favorable ? 'var(--accent)' : '#EF4444';

    return `
      <!-- Main Weather Summary Card -->
      <div class="glass-card" style="padding: 22px; margin-bottom: 16px; background: linear-gradient(135deg, rgba(34, 197, 94, 0.12), rgba(6, 13, 7, 0.4)); border: 1px solid var(--border-bright);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px;">
          <div>
            <div style="font-size: 16px; font-weight: 800; color: var(--text); display: flex; align-items: center; gap: 6px;">
              📍 ${escapeHtml(w.city)}, ${w.country}
            </div>
            <div style="font-size: 40px; font-weight: 900; margin: 4px 0; color: var(--text); letter-spacing: -0.04em;">
              ${w.temp}°C
            </div>
            <div style="font-size: 13px; color: var(--text-secondary); text-transform: capitalize;">
              ${w.condition} · Feels like ${w.feels_like}°C
            </div>
          </div>
          <div style="text-align: right;">
            <span style="font-size: 10px; font-weight: 800; background: var(--surface-2); padding: 4px 8px; border-radius: 6px; color: var(--accent); display: inline-block;">
              ● LIVE DATA · ${w.metadata?.source || 'OpenWeatherMap'}
            </span>
          </div>
        </div>

        <!-- Metric Grid -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; background: var(--surface-1); padding: 14px; border-radius: 14px; font-size: 13px; margin-top: 14px;">
          <div>💧 Humidity<br><strong>${w.humidity}%</strong></div>
          <div>💨 Wind Speed<br><strong>${w.wind_speed} km/h</strong></div>
          <div>🌧️ Rainfall<br><strong>${w.rain_1h} mm</strong></div>
        </div>
      </div>

      <!-- AI Spray Window Advisory Card -->
      <div class="glass-card" style="padding: 18px; margin-bottom: 16px; border-left: 4px solid ${sprayBorderColor};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h3 style="font-size: 15px; font-weight: 800; margin: 0;">🚜 AI Spray Window Advisory</h3>
          <span class="badge ${w.spray_favorable ? 'badge-success' : 'badge-danger'}">
            ${w.spray_favorable ? '● Spray Window Open' : '● Spraying Not Recommended'}
          </span>
        </div>
        <p style="font-size: 13px; line-height: 1.5; color: var(--text); margin: 0;">
          ${w.spray_advisory || 'Check wind speed and rainfall before spraying.'}
        </p>
      </div>
    `;
  }

  async function loadWeather(container, query = '', lat = null, lon = null) {
    isLoading = true;
    render(container);
    try {
      if (query && query.trim()) {
        weatherData = await window.KisanAPI.getCurrentWeather(null, null, query.trim());
      } else if (lat !== null && lon !== null) {
        weatherData = await window.KisanAPI.getCurrentWeather(lat, lon);
      } else {
        // Default to Mysore / Bangalore coordinates
        weatherData = await window.KisanAPI.getCurrentWeather(12.2958, 76.6394);
      }
    } catch (e) {
      weatherData = { available: false, message: 'Could not connect to weather service.' };
    } finally {
      isLoading = false;
      render(container);
    }
  }

  function attachListeners(container) {
    const searchBtn = container.querySelector('#searchWeatherBtn');
    const input = container.querySelector('#weatherLocationInput');
    const gpsBtn = container.querySelector('#gpsWeatherBtn');
    const retryBtn = container.querySelector('#retryWeatherBtn');

    const doSearch = () => {
      if (!input) return;
      searchQuery = input.value.trim();
      loadWeather(container, searchQuery);
    };

    if (searchBtn) searchBtn.onclick = doSearch;
    if (input) {
      input.onkeydown = (e) => {
        if (e.key === 'Enter') doSearch();
      };
    }

    if (gpsBtn) {
      gpsBtn.onclick = () => {
        if (navigator.geolocation) {
          gpsBtn.innerHTML = '⏳';
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              searchQuery = '';
              loadWeather(container, '', pos.coords.latitude, pos.coords.longitude);
            },
            (err) => {
              alert('Could not access GPS location. Please type your town or district name in the search box.');
              gpsBtn.innerHTML = '📍';
            },
            { timeout: 8000 }
          );
        } else {
          alert('Geolocation is not supported by your browser.');
        }
      };
    }

    if (retryBtn) {
      retryBtn.onclick = () => loadWeather(container, searchQuery);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  if (window.KisanRouter) window.KisanRouter.register('/weather', render);
})();

