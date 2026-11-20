// ═══════════════════════════════════════════════════════════
// AGRO AI — CENTRAL AI ENGINE v2.0
// The brain of the entire application.
// All modules read from and write to this engine.
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  const ENGINE_VERSION = '2.0';
  const STORAGE_KEY = 'agroai_engine_v2';

  // ── Default State ──────────────────────────────────────────
  const DEFAULT_STATE = {
    version: ENGINE_VERSION,
    farmer: {
      name: '',
      phone: '',
      whatsapp_number: '',
      email: '',
      village: '',
      taluk: '',
      district: '',
      state: 'Karnataka',
      pincode: '',
      language: 'en',
      photo: null,
      upi_id: '',
      bank_name: '',
    },
    farm: {
      name: 'My Farm',
      acres: 0,
      owned_acres: 0,
      leased_acres: 0,
      crops: [],
      soil: { ph: null, nitrogen: null, phosphorus: null, potassium: null, organic_carbon: null, moisture: null },
      gps: { lat: null, lon: null },
      location_name: '',
      health_score: 87,
      boundary: null,
      irrigation_method: '',
      soil_type: '',
    },
    settings: {
      gemini_api_key: '',
      openweather_api_key: '',
      notifications_enabled: true,
      whatsapp_enabled: true,
      whatsapp_categories: {
        diagnosis: true,
        weather: true,
        market: true,
        daily_digest: true,
        gpt_responses: false,
        orders: true,
        payments: true,
      },
      dark_mode: true,
      preferred_language: 'en',
    },
    weather: null,
    weather_updated_at: null,
    market: { prices: [], alerts: [], updated_at: null },
    diagnoses: [],
    gpt_sessions: [],
    notifications: [],
    soil_reports: [],
  };

  // ── State ──────────────────────────────────────────────────
  let state = loadState();
  const subscribers = {};
  let saveTimer = null;

  // ── Persistence ────────────────────────────────────────────
  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        return deepMerge(JSON.parse(JSON.stringify(DEFAULT_STATE)), parsed);
      }
    } catch (e) { console.warn('[AgroEngine] Load error:', e); }
    return JSON.parse(JSON.stringify(DEFAULT_STATE));
  }

  function saveState() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (e) { console.warn('[AgroEngine] Save error:', e); }
    }, 200);
  }

  function deepMerge(target, source) {
    if (!source || typeof source !== 'object') return target;
    const result = { ...target };
    for (const key in source) {
      if (source[key] !== null && typeof source[key] === 'object' && !Array.isArray(source[key])) {
        result[key] = deepMerge(target[key] || {}, source[key]);
      } else {
        result[key] = source[key];
      }
    }
    return result;
  }

  // ── Event Bus ──────────────────────────────────────────────
  function on(event, callback) {
    if (!subscribers[event]) subscribers[event] = [];
    subscribers[event].push(callback);
    return () => { subscribers[event] = (subscribers[event] || []).filter(fn => fn !== callback); };
  }

  function dispatch(event, data) {
    (subscribers[event] || []).forEach(fn => { try { fn(data); } catch (e) {} });
    (subscribers['*'] || []).forEach(fn => { try { fn(event, data); } catch (e) {} });
  }

  // ── State Access ───────────────────────────────────────────
  function get(path) {
    if (!path) return state;
    return path.split('.').reduce((obj, key) => (obj && obj[key] !== undefined ? obj[key] : undefined), state);
  }

  function set(path, value, silent) {
    const parts = path.split('.');
    let current = state;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || typeof current[parts[i]] !== 'object') current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    saveState();
    if (!silent) dispatch('state.changed', { path, value });
  }

  function patch(path, partial) {
    const current = get(path) || {};
    set(path, { ...current, ...partial });
  }

  // ── Context Builder for GPT ────────────────────────────────
  function getFullContext() {
    const { farmer, farm, weather, diagnoses, market } = state;
    const lang = farmer.language || 'en';
    const lastDiag = diagnoses[0];
    const soil = farm.soil;

    let ctx = `=== FARMER PROFILE ===\n`;
    ctx += `Name: ${farmer.name || 'Farmer'}\n`;
    ctx += `Location: ${farm.location_name || `${farmer.village || ''}, ${farmer.district || ''}, ${farmer.state || 'India'}`}\n`;
    ctx += `Farm: ${farm.acres || '?'} acres | Crops: ${(farm.crops || []).join(', ') || 'Not specified'}\n`;
    ctx += `Language preference: ${lang}\n`;

    if (weather) {
      ctx += `\n=== CURRENT WEATHER ===\n`;
      ctx += `Temp: ${weather.temp}°C (feels ${weather.feels_like}°C) | ${weather.condition}\n`;
      ctx += `Humidity: ${weather.humidity}% | Wind: ${weather.wind_speed} km/h | Rain: ${weather.rain_1h || 0}mm\n`;
      if (weather.forecast?.length) {
        ctx += `Forecast: ${weather.forecast.slice(0, 3).map(f => `${f.day}: ${f.condition} ${f.temp_max}°/${f.temp_min}°`).join(', ')}\n`;
      }
    }

    if (lastDiag) {
      ctx += `\n=== LAST DIAGNOSIS (${new Date(lastDiag.date).toLocaleDateString('en-IN')}) ===\n`;
      ctx += `Crop: ${lastDiag.crop} | Disease: ${lastDiag.disease}\n`;
      ctx += `Severity: ${lastDiag.severity} | Confidence: ${lastDiag.confidence}%\n`;
      if (lastDiag.treatment) ctx += `Treatment: ${lastDiag.treatment}\n`;
    }

    if (soil.ph) {
      ctx += `\n=== SOIL DATA ===\n`;
      ctx += `pH: ${soil.ph} | N: ${soil.nitrogen} | P: ${soil.phosphorus} | K: ${soil.potassium}\n`;
      if (soil.organic_carbon) ctx += `Organic Carbon: ${soil.organic_carbon}%\n`;
    }

    if (market.prices?.length) {
      ctx += `\n=== TODAY'S MARKET ===\n`;
      ctx += market.prices.slice(0, 5).map(p => `${p.commodity}: ₹${p.modal_price}/q`).join(' | ') + '\n';
    }

    return ctx;
  }

  // ── Farm Health Score ──────────────────────────────────────
  function computeHealthScore() {
    let score = 90;
    const lastDiag = state.diagnoses[0];
    if (lastDiag) {
      const ageMs = Date.now() - new Date(lastDiag.date).getTime();
      const ageDays = ageMs / 86400000;
      if (ageDays < 7) {
        if (lastDiag.severity === 'severe') score -= 35;
        else if (lastDiag.severity === 'moderate') score -= 20;
        else if (lastDiag.severity === 'mild') score -= 8;
      }
    }
    if (state.weather?.humidity > 85) score -= 5;
    if (state.farm.soil.ph && (state.farm.soil.ph < 5.5 || state.farm.soil.ph > 7.5)) score -= 5;
    score = Math.max(25, Math.min(100, score));
    state.farm.health_score = score;
    saveState();
    return score;
  }

  // ── Diagnosis Management ───────────────────────────────────
  function addDiagnosis(report) {
    const record = { ...report, id: 'diag_' + Date.now(), date: new Date().toISOString() };
    state.diagnoses.unshift(record);
    if (state.diagnoses.length > 50) state.diagnoses = state.diagnoses.slice(0, 50);
    saveState();
    computeHealthScore();
    dispatch('diagnosis.complete', record);
    dispatch('engine.updated', { section: 'diagnoses' });
    return record;
  }

  // ── GPS ────────────────────────────────────────────────────
  function requestGPS() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject('Geolocation not supported');
      navigator.geolocation.getCurrentPosition(
        pos => {
          const { latitude: lat, longitude: lon } = pos.coords;
          set('farm.gps.lat', lat, true);
          set('farm.gps.lon', lon, true);
          saveState();
          dispatch('gps.updated', { lat, lon });
          resolve({ lat, lon });
        },
        err => reject(err),
        { timeout: 10000, enableHighAccuracy: true }
      );
    });
  }

  // ── GPT Session ────────────────────────────────────────────
  function addGptMessage(msg) {
    if (!state.gpt_sessions[0]) {
      state.gpt_sessions.unshift({ id: 'sess_' + Date.now(), messages: [], created_at: new Date().toISOString() });
    }
    state.gpt_sessions[0].messages.push({ ...msg, ts: new Date().toISOString() });
    if (state.gpt_sessions[0].messages.length > 200) {
      state.gpt_sessions[0].messages = state.gpt_sessions[0].messages.slice(-200);
    }
    if (state.gpt_sessions.length > 5) state.gpt_sessions = state.gpt_sessions.slice(0, 5);
    saveState();
  }

  function getGptMessages() {
    return state.gpt_sessions[0]?.messages || [];
  }

  function newGptSession() {
    state.gpt_sessions.unshift({ id: 'sess_' + Date.now(), messages: [], created_at: new Date().toISOString() });
    if (state.gpt_sessions.length > 5) state.gpt_sessions = state.gpt_sessions.slice(0, 5);
    saveState();
  }

  // ── Notifications ──────────────────────────────────────────
  function addNotification(notif) {
    const record = { ...notif, id: 'n_' + Date.now(), ts: new Date().toISOString(), read: false };
    state.notifications.unshift(record);
    if (state.notifications.length > 100) state.notifications = state.notifications.slice(0, 100);
    saveState();
    dispatch('notification.added', record);
    return record;
  }

  function markNotificationsRead() {
    state.notifications.forEach(n => n.read = true);
    saveState();
    dispatch('notifications.cleared', null);
  }

  function getUnreadCount() {
    return state.notifications.filter(n => !n.read).length;
  }

  // ── Auto-init ──────────────────────────────────────────────
  function init() {
    // Compute initial health score
    computeHealthScore();
    console.log('🌾 AgroAI Engine v2.0 initialized | Health:', state.farm.health_score);
  }

  init();

  // ── Public API ─────────────────────────────────────────────
  window.KisanEngine = {
    // Core
    get, set, patch, on, dispatch,
    getFullContext, computeHealthScore,
    getState: () => state,

    // Farmer
    getFarmer: () => state.farmer,
    setFarmer: (data) => { patch('farmer', data); dispatch('farmer.updated', data); },

    // Farm
    getFarm: () => state.farm,
    setFarm: (data) => { patch('farm', data); dispatch('farm.updated', data); },

    // Settings
    getSettings: () => state.settings,
    setSettings: (data) => { patch('settings', data); dispatch('settings.updated', data); },
    getApiKey: (service) => service === 'gemini' ? state.settings.gemini_api_key : state.settings.openweather_api_key,

    // Weather
    getWeather: () => state.weather,
    setWeather: (data) => {
      state.weather = data;
      state.weather_updated_at = Date.now();
      saveState();
      dispatch('weather.updated', data);
    },
    isWeatherStale: () => !state.weather_updated_at || (Date.now() - state.weather_updated_at) > 1800000,

    // Market
    getMarket: () => state.market,
    setMarketPrices: (prices) => {
      state.market.prices = prices;
      state.market.updated_at = Date.now();
      saveState();
      dispatch('market.updated', prices);
    },
    addMarketAlert: (alert) => {
      state.market.alerts.push({ ...alert, id: 'a_' + Date.now() });
      saveState();
    },

    // Diagnoses
    getDiagnoses: () => state.diagnoses,
    getLastDiagnosis: () => state.diagnoses[0] || null,
    addDiagnosis,

    // GPT
    getGptMessages,
    addGptMessage,
    newGptSession,

    // Notifications
    addNotification,
    markNotificationsRead,
    getUnreadCount,
    getNotifications: () => state.notifications,

    // Soil
    getSoil: () => state.farm.soil,
    setSoil: (data) => {
      patch('farm.soil', data);
      dispatch('soil.updated', data);
    },

    // GPS
    requestGPS,
    getGPS: () => state.farm.gps,
  };
})();
