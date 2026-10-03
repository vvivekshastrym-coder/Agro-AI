// ═══════════════════════════════════════════════════════════
// AGRO AI — SINGLE SOURCE OF TRUTH API CLIENT v3.0
// All requests route through the backend API.
// No secret API keys or AI calls exist on the frontend.
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  const BACKEND_BASE = 'http://localhost:8000/api';
  const WS_BASE = 'ws://localhost:8000';

  // Helper for standard HTTP request with error handling
  async function apiFetch(endpoint, options = {}) {
    const url = `${BACKEND_BASE}${endpoint}`;
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        let errData = {};
        try { errData = await res.json(); } catch(e){}
        const errorDetail = errData.detail?.error || errData.detail || { message: `HTTP ${res.status} Error`, code: 'HTTP_ERROR', retryable: true };
        throw errorDetail;
      }
      return await res.json();
    } catch (err) {
      console.error(`[AgroAPI Error] ${endpoint}:`, err);
      throw err.message ? err : { message: 'Connection to Agro AI backend failed. Please try again.', code: 'NETWORK_ERROR', retryable: true };
    }
  }

  // ── LEAF DIAGNOSIS API ────────────────────────────────────
  async function diagnoseCrop(file, cropHint = '', language = 'en', farmerId = 'default_farmer') {
    const formData = new FormData();
    formData.append('image', file);
    if (cropHint) formData.append('crop', cropHint);
    formData.append('language', language);
    formData.append('farmer_id', farmerId);

    const url = `${BACKEND_BASE}/diagnosis/analyze`;
    const res = await fetch(url, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      let errData = {};
      try { errData = await res.json(); } catch(e){}
      throw errData.detail?.error || { message: 'Failed to analyze crop image', code: 'DIAGNOSIS_ERROR', retryable: true };
    }

    return await res.json();
  }

  async function attachDiagnosisContext(reportId, farmerId = 'default_farmer') {
    return await apiFetch('/agro-gpt/context/diagnosis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_id: reportId, farmer_id: farmerId })
    });
  }

  // ── AGRO GPT API ──────────────────────────────────────────
  async function agroGptChat(message, conversationId = null, language = 'en', farmerId = 'default_farmer', context = null) {
    return await apiFetch('/agro-gpt/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: message,
        language: language,
        farmer_id: farmerId,
        context: context
      })
    });
  }

  async function agroGptChatStream(message, conversationId = null, language = 'en', farmerId = 'default_farmer', onChunk = null) {
    const url = `${BACKEND_BASE}/agro-gpt/chat/stream`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        message: message,
        language: language,
        farmer_id: farmerId
      })
    });

    if (!res.ok) {
      throw new Error('Streaming failed');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data:')) {
          try {
            const parsed = JSON.parse(line.slice(5).trim());
            if (parsed.text && onChunk) {
              onChunk(parsed.text);
            }
          } catch(e){}
        }
      }
    }
  }

  // ── LOGISTICS API — Search & Trip Management ──────────────

  /** Search for available verified drivers for a route.
   *  pickup_lat/lon and dest_lat/lon MUST be real GPS coordinates.
   *  Never pass hardcoded or invented coordinates. */
  async function searchLogistics(params) {
    return await apiFetch('/logistics/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
  }

  /** Create a confirmed trip booking.
   *  All coordinates must be real — from GPS or geocoder. */
  async function createTrip(tripData) {
    return await apiFetch('/logistics/trips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tripData)
    });
  }

  /** Get full trip details including latest driver location. */
  async function getTripDetails(tripId) {
    return await apiFetch(`/logistics/trips/${tripId}`);
  }

  /** Farmer's trip history. */
  async function getFarmerTrips(farmerId) {
    return await apiFetch(`/logistics/trips?farmer_id=${encodeURIComponent(farmerId)}`);
  }

  /** Cancel a trip (only valid before IN_TRANSIT). */
  async function cancelTrip(tripId, actorId, note = '') {
    return await apiFetch(`/logistics/trips/${tripId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: actorId, note })
    });
  }

  /** Farmer rates a completed trip. rating must be 1.0–5.0. */
  async function rateTrip(tripId, farmerId, rating, review = '') {
    return await apiFetch(`/logistics/trips/${tripId}/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ farmer_id: farmerId, rating, review })
    });
  }

  /** Public share-token trip tracking (no auth). */
  async function trackTripPublic(tripId, token) {
    return await apiFetch(`/logistics/trips/${tripId}/track?token=${encodeURIComponent(token)}`);
  }

  // ── LOGISTICS API — Driver Operations ─────────────────────

  /** Find verified online drivers near a location.
   *  lat/lon must be real GPS coordinates. */
  async function getNearbyDrivers(lat, lon, vehicleType = null, radiusKm = 50) {
    let url = `/logistics/drivers/nearby?lat=${lat}&lon=${lon}&radius_km=${radiusKm}`;
    if (vehicleType) url += `&vehicle_type=${encodeURIComponent(vehicleType)}`;
    return await apiFetch(url);
  }

  /** Push driver GPS heartbeat.
   *  lat/lon must be real device GPS — never invented. */
  async function pushDriverLocation(data) {
    // data: { driver_id, trip_id?, lat, lon, accuracy_m?, heading_deg?, speed_kmh? }
    return await apiFetch('/logistics/drivers/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  }

  /** Get a specific driver's current status and freshness. */
  async function getDriverStatus(driverId) {
    return await apiFetch(`/logistics/drivers/${driverId}/status`);
  }

  /** Register as an Agro AI driver (pending verification). */
  async function registerDriver(data) {
    return await apiFetch('/logistics/drivers/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  }

  /** Driver's own trip list. */
  async function getDriverTrips(driverId) {
    return await apiFetch(`/logistics/drivers/my-trips?driver_id=${encodeURIComponent(driverId)}`);
  }

  /** Driver accepts a trip request. */
  async function acceptTrip(tripId, driverId, lat = null, lon = null) {
    return await apiFetch(`/logistics/trips/${tripId}/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: driverId, lat, lon })
    });
  }

  /** Driver rejects a trip request. */
  async function rejectTrip(tripId, driverId, note = '') {
    return await apiFetch(`/logistics/trips/${tripId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: driverId, note })
    });
  }

  /** Driver marks arrival at pickup. */
  async function driverArrived(tripId, driverId, lat = null, lon = null) {
    return await apiFetch(`/logistics/trips/${tripId}/arrive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: driverId, lat, lon })
    });
  }

  /** Start trip (loading / in-transit). */
  async function startTrip(tripId, actorId) {
    return await apiFetch(`/logistics/trips/${tripId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: actorId })
    });
  }

  /** Complete a trip. */
  async function completeTrip(tripId, actorId) {
    return await apiFetch(`/logistics/trips/${tripId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: actorId })
    });
  }

  // ── LOGISTICS API — WebSocket real-time tracking ──────────

  /**
   * Connect to the real-time trip tracking WebSocket.
   * Returns a connection object with { send, close, isOpen }.
   *
   * onMessage(event) receives parsed JSON objects:
   *   { event: 'LOCATION_UPDATE', lat, lon, freshness, ... }
   *   { event: 'TRIP_ACCEPTED', status, ... }
   *   etc.
   *
   * onStale() is called if no message received for staleSecs seconds.
   */
  function connectTripWebSocket(tripId, { onMessage, onOpen, onClose, onStale, staleSecs = 30 } = {}) {
    let ws = null;
    let staleTimer = null;
    let isOpen = false;

    function resetStaleTimer() {
      clearTimeout(staleTimer);
      if (onStale && staleSecs > 0) {
        staleTimer = setTimeout(() => {
          if (isOpen && onStale) onStale();
        }, staleSecs * 1000);
      }
    }

    try {
      ws = new WebSocket(`${WS_BASE}/ws/trip/${tripId}`);

      ws.onopen = () => {
        isOpen = true;
        resetStaleTimer();
        if (onOpen) onOpen();
        // keep-alive ping every 20s
        ws._pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 20000);
      };

      ws.onmessage = (ev) => {
        resetStaleTimer();
        if (ev.data === 'pong') return;
        try {
          const data = JSON.parse(ev.data);
          if (onMessage) onMessage(data);
        } catch(e) {}
      };

      ws.onclose = () => {
        isOpen = false;
        clearTimeout(staleTimer);
        clearInterval(ws._pingInterval);
        if (onClose) onClose();
      };

      ws.onerror = () => {
        isOpen = false;
        if (onClose) onClose();
      };
    } catch(e) {
      console.error('[WS] Failed to connect:', e);
    }

    return {
      send: (msg) => ws && ws.readyState === WebSocket.OPEN && ws.send(msg),
      close: () => ws && ws.close(),
      get isOpen() { return isOpen; }
    };
  }

  // ── GEOCODING — Nominatim (free, no key required) ─────────

  /**
   * Forward geocode: text address → { lat, lon, display_name }
   * Uses Nominatim (OpenStreetMap). Result is ESTIMATED coordinates
   * — user should confirm on map before submitting a booking.
   */
  async function geocodeAddress(address) {
    if (!address || !address.trim()) return null;
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=5&countrycodes=in`;
      const res = await fetch(url, {
        headers: { 'Accept-Language': 'en', 'User-Agent': 'AgroAI-Logistics/3.0' }
      });
      const data = await res.json();
      if (!data || data.length === 0) return null;
      return data.map(r => ({
        lat: parseFloat(r.lat),
        lon: parseFloat(r.lon),
        display_name: r.display_name,
        source: 'Nominatim (OpenStreetMap)',
        status: 'geocoded'
      }));
    } catch(e) {
      console.error('[Geocode] Error:', e);
      return null;
    }
  }

  /**
   * Reverse geocode: GPS coords → human-readable address string.
   * Uses Nominatim. Returns display_name string or null.
   */
  async function reverseGeocode(lat, lon) {
    if (lat == null || lon == null) return null;
    try {
      const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`;
      const res = await fetch(url, {
        headers: { 'Accept-Language': 'en', 'User-Agent': 'AgroAI-Logistics/3.0' }
      });
      const data = await res.json();
      return data && data.display_name ? data.display_name : null;
    } catch(e) {
      console.error('[ReverseGeocode] Error:', e);
      return null;
    }
  }

  // ── MARKETPLACE & MANDI API ────────────────────────────────
  async function getInputMarketplace(category = '', query = '', lat = 12.9716, lon = 77.5946) {
    return await apiFetch(`/market/inputs?category=${encodeURIComponent(category)}&query=${encodeURIComponent(query)}&lat=${lat}&lon=${lon}`);
  }

  async function getMandiPrices(state = 'Karnataka', commodity = '') {
    return await apiFetch(`/market/mandi?state=${encodeURIComponent(state)}&commodity=${encodeURIComponent(commodity)}`);
  }

  // ── DRONE SCOUT API ───────────────────────────────────────
  async function getDroneOperators(lat = 12.9716, lon = 77.5946, acres = 5.0) {
    return await apiFetch(`/drone/operators?lat=${lat}&lon=${lon}&acres=${acres}`);
  }

  // ── WEATHER API ───────────────────────────────────────────
  async function getCurrentWeather(lat = null, lon = null, query = '') {
    if (query && query.trim()) {
      return await apiFetch(`/weather/current?q=${encodeURIComponent(query.trim())}`);
    }
    const targetLat = lat !== null ? lat : 12.9716;
    const targetLon = lon !== null ? lon : 77.5946;
    return await apiFetch(`/weather/current?lat=${targetLat}&lon=${targetLon}`);
  }

  // Alias used by home.js & weather.js
  async function fetchFullWeather(lat = null, lon = null, query = '') {
    return await getCurrentWeather(lat, lon, query);
  }

  // ── DAILY AI DIGEST ───────────────────────────────────────
  async function getDailyDigest(farmerId = 'default_farmer', language = 'en') {
    const data = await apiFetch(`/agro-gpt/daily-digest?farmer_id=${encodeURIComponent(farmerId)}&language=${encodeURIComponent(language)}`);
    return data.digest || data.text || '';
  }

  // ── MANDI PRICES (normalized to array for engine) ─────────
  async function getMandiPricesArray(state = 'Karnataka', commodity = '') {
    const data = await getMandiPrices(state, commodity);
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.records)) return data.records;
    return [];
  }

  // ── SOIL DNA API ──────────────────────────────────────────
  async function getSoilReport(farmerId = 'default_farmer', crop = 'Tomato') {
    return await apiFetch(`/agri/soil/report?farmer_id=${encodeURIComponent(farmerId)}&crop=${encodeURIComponent(crop)}`);
  }

  // ── SATELLITE DIGITAL TWIN API ────────────────────────────
  async function getNDVIAnalysis(lat = 12.9716, lon = 77.5946) {
    return await apiFetch(`/satellite/ndvi?lat=${lat}&lon=${lon}`);
  }

  // ── KISAN CREDIT API ──────────────────────────────────────
  async function getCreditProfile(farmerId = 'default_farmer', acres = 3.5) {
    return await apiFetch(`/agri/credit/profile?farmer_id=${encodeURIComponent(farmerId)}&acres=${acres}`);
  }

  // ── CARBON CREDITS API ────────────────────────────────────
  async function getCarbonSummary(farmerId = 'default_farmer', acres = 3.5) {
    return await apiFetch(`/agri/carbon/summary?farmer_id=${encodeURIComponent(farmerId)}&acres=${acres}`);
  }

  // ── CROP INSURANCE API ────────────────────────────────────
  async function getInsuranceStatus(farmerId = 'default_farmer', crop = 'Tomato', acres = 3.5) {
    return await apiFetch(`/agri/insurance/status?farmer_id=${encodeURIComponent(farmerId)}&crop=${encodeURIComponent(crop)}&acres=${acres}`);
  }

  // ── FARM PASSPORT API ─────────────────────────────────────
  async function getFarmPassport(farmerId = 'default_farmer', batchId = 'BATCH-2026-TOM-01') {
    return await apiFetch(`/agri/passport/trace?farmer_id=${encodeURIComponent(farmerId)}&batch_id=${encodeURIComponent(batchId)}`);
  }

  // Expose unified client
  window.KisanAPI = {
    // Diagnosis
    diagnoseCrop,
    attachDiagnosisContext,
    // Agro GPT
    agroGptChat,
    agroGptChatStream,
    // Logistics — Farmer
    searchLogistics,
    createTrip,
    getTripDetails,
    getFarmerTrips,
    cancelTrip,
    rateTrip,
    trackTripPublic,
    // Logistics — Driver
    getNearbyDrivers,
    pushDriverLocation,
    getDriverStatus,
    registerDriver,
    getDriverTrips,
    acceptTrip,
    rejectTrip,
    driverArrived,
    startTrip,
    completeTrip,
    // Logistics — Real-time
    connectTripWebSocket,
    // Geocoding (Nominatim, free, no key)
    geocodeAddress,
    reverseGeocode,
    // Market
    getInputMarketplace,
    getMandiPrices,
    getMandiPricesArray,
    // Drone
    getDroneOperators,
    // Weather
    getCurrentWeather,
    fetchFullWeather,
    // AI
    getDailyDigest,
    // Agri
    getSoilReport,
    getNDVIAnalysis,
    getCreditProfile,
    getCarbonSummary,
    getInsuranceStatus,
    getFarmPassport
  };

  console.log('⚡ KisanAPI v3.0 loaded | Real-Data-Only Logistics + Geocoding');
})();
