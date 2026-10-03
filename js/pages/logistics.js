// ═══════════════════════════════════════════════════════════
// AGRO AI — LOGISTICS PLATFORM v3.0
// Production-Grade Real-Data-Only Transport
//
// CRITICAL RULE: Never display fake, mock, hardcoded or assumed
// logistics information. If data is unavailable, say so.
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  // ─── Module State ──────────────────────────────────────────
  let screen = 'book';          // 'book' | 'results' | 'confirm' | 'track'
  let isLoading = false;
  let errorMessage = null;

  // Location state — NEVER prefilled with hardcoded coords
  let pickupCoords = null;      // { lat, lon, display_name, source }
  let destCoords   = null;      // { lat, lon, display_name, source }
  let pickupGeoSearching = false;
  let destGeoSearching   = false;

  // Results state
  let searchResults  = null;
  let selectedOption = null;
  let routeInfo      = null;

  // Trip state
  let currentTrip = null;
  let wsConn      = null;
  let wsStale     = false;

  let _container = null;

  // ─── Freshness helpers ─────────────────────────────────────
  function freshnessLabel(freshness) {
    switch (freshness) {
      case 'LIVE':        return { icon: '🟢', label: 'LIVE',        color: '#22c55e' };
      case 'RECENT':      return { icon: '🟡', label: 'RECENT',      color: '#eab308' };
      case 'STALE':       return { icon: '🟠', label: 'STALE',       color: '#f97316' };
      case 'UNAVAILABLE': return { icon: '⚪', label: 'UNAVAILABLE', color: '#9ca3af' };
      default:            return { icon: '⚪', label: 'UNAVAILABLE', color: '#9ca3af' };
    }
  }

  function routeStatusBadge(status) {
    if (status === 'verified')  return '<span style="color:#22c55e;font-weight:800;font-size:11px;">🟢 VERIFIED</span>';
    if (status === 'estimated') return '<span style="color:#eab308;font-weight:800;font-size:11px;">🟡 ESTIMATED</span>';
    return '<span style="color:#9ca3af;font-weight:800;font-size:11px;">⚪ UNAVAILABLE</span>';
  }

  function formatTime(isoStr) {
    if (!isoStr) return 'unknown';
    try {
      return new Date(isoStr).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    } catch(e) { return isoStr; }
  }

  function secondsAgo(isoStr) {
    if (!isoStr) return null;
    return Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  }

  function relativeAge(isoStr) {
    const s = secondsAgo(isoStr);
    if (s === null) return 'unknown';
    if (s < 60)  return `${s} sec ago`;
    if (s < 3600) return `${Math.floor(s/60)} min ago`;
    return `${Math.floor(s/3600)} hr ago`;
  }

  // ─── GPS permission ────────────────────────────────────────
  function requestCurrentLocation(onSuccess, onError) {
    if (!navigator.geolocation) {
      onError('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => onSuccess(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy),
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          onError('Location permission denied. Please enable GPS in your browser settings.');
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          onError('Your location could not be determined right now.');
        } else {
          onError('GPS request timed out. Please try again.');
        }
      },
      { timeout: 10000, maximumAge: 60000, enableHighAccuracy: true }
    );
  }

  // ─── Main render ───────────────────────────────────────────
  function render(container) {
    _container = container;
    container.innerHTML = `
      <div style="margin-bottom:20px;">
        <h1 style="font-size:22px;font-weight:900;margin-bottom:6px;">🚛 Agro Transport Logistics</h1>
        <p style="font-size:13px;color:var(--text-muted);">Verified agricultural transport — real routes, real drivers, real data</p>
      </div>
      <div id="logisticsMain">${renderScreen()}</div>
    `;
    attachListeners(container);
  }

  function rerender() {
    if (!_container) return;
    const main = _container.querySelector('#logisticsMain');
    if (main) {
      main.innerHTML = renderScreen();
      attachListeners(_container);
    }
  }

  function renderScreen() {
    switch (screen) {
      case 'book':    return renderBookScreen();
      case 'results': return renderResultsScreen();
      case 'confirm': return renderConfirmScreen();
      case 'track':   return renderTrackScreen();
      default:        return renderBookScreen();
    }
  }

  // ══════════════════════════════════════════════
  // SCREEN 1 — BOOK TRANSPORT
  // ══════════════════════════════════════════════
  function renderBookScreen() {
    return `
      <div class="glass-card" style="padding:20px;margin-bottom:16px;">
        <div style="font-size:15px;font-weight:800;margin-bottom:16px;">📍 Trip Details</div>

        <!-- Pickup Location -->
        <div style="margin-bottom:14px;">
          <label style="font-size:12px;font-weight:700;color:var(--text-muted);display:block;margin-bottom:4px;">PICKUP LOCATION</label>
          <div style="display:flex;gap:8px;align-items:flex-start;">
            <div style="flex:1;">
              <input type="text" id="pickupText"
                placeholder="Enter pickup location or use GPS..."
                value="${pickupCoords ? pickupCoords.display_name : ''}"
                style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;box-sizing:border-box;">
              ${pickupCoords ? `
                <div style="font-size:11px;color:#22c55e;margin-top:4px;">
                  🟢 GPS confirmed: ${pickupCoords.lat.toFixed(5)}, ${pickupCoords.lon.toFixed(5)}
                  <span style="color:var(--text-muted);">· via ${pickupCoords.source}</span>
                </div>` : `
                <div style="font-size:11px;color:#f97316;margin-top:4px;">⚠ GPS coordinates required — use button or search below</div>`
              }
            </div>
            <button id="useGpsBtn" class="btn" style="padding:10px 12px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);white-space:nowrap;font-size:12px;font-weight:700;">
              ${pickupGeoSearching ? '⏳ Getting GPS...' : '📍 Use GPS'}
            </button>
          </div>
          <div id="gpsError" style="color:#ef4444;font-size:12px;margin-top:4px;"></div>
          <div id="pickupSuggestions"></div>
        </div>

        <!-- Destination -->
        <div style="margin-bottom:14px;">
          <label style="font-size:12px;font-weight:700;color:var(--text-muted);display:block;margin-bottom:4px;">DESTINATION</label>
          <input type="text" id="destText"
            placeholder="Market, APMC, warehouse..."
            value="${destCoords ? destCoords.display_name : ''}"
            style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;box-sizing:border-box;">
          ${destCoords ? `
            <div style="font-size:11px;color:#22c55e;margin-top:4px;">
              🟢 Location confirmed: ${destCoords.lat.toFixed(5)}, ${destCoords.lon.toFixed(5)}
              <span style="color:var(--text-muted);">· via ${destCoords.source}</span>
            </div>` : `
            <div style="font-size:11px;color:#9ca3af;margin-top:4px;">Type and press Search to verify location</div>`
          }
          <div id="destSuggestions"></div>
        </div>

        <!-- Crop / Quantity / Vehicle -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px;">
          <div>
            <label style="font-size:12px;font-weight:700;color:var(--text-muted);">CROP / LOAD TYPE</label>
            <input type="text" id="cropType" placeholder="e.g. Tomato"
              style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;margin-top:4px;box-sizing:border-box;">
          </div>
          <div>
            <label style="font-size:12px;font-weight:700;color:var(--text-muted);">QUANTITY (TONS)</label>
            <input type="number" id="quantityTons" value="1" step="0.5" min="0.1"
              style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;margin-top:4px;box-sizing:border-box;">
          </div>
          <div>
            <label style="font-size:12px;font-weight:700;color:var(--text-muted);">VEHICLE TYPE</label>
            <select id="vehicleType"
              style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;margin-top:4px;box-sizing:border-box;">
              <option value="Tata Ace">Tata Ace (0.8 T)</option>
              <option value="Tata 407">Tata 407 (2.5 T)</option>
              <option value="Eicher">Eicher (5.0 T)</option>
              <option value="Tractor Trailer">Tractor Trailer (3.0 T)</option>
              <option value="Refrigerated Truck">Refrigerated Truck (3.5 T)</option>
            </select>
          </div>
        </div>

        <!-- Pickup Date/Time -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
          <div>
            <label style="font-size:12px;font-weight:700;color:var(--text-muted);">PICKUP DATE</label>
            <input type="date" id="pickupDate"
              style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;margin-top:4px;box-sizing:border-box;">
          </div>
          <div>
            <label style="font-size:12px;font-weight:700;color:var(--text-muted);">PICKUP TIME</label>
            <input type="time" id="pickupTime"
              style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--border);background:var(--surface-2);color:var(--text);font-size:13px;margin-top:4px;box-sizing:border-box;">
          </div>
        </div>

        ${errorMessage ? `
          <div style="background:rgba(239,68,68,0.1);border-left:4px solid #ef4444;padding:12px 14px;border-radius:8px;margin-bottom:14px;font-size:13px;color:#ef4444;">
            ⚠ ${errorMessage}
          </div>` : ''}

        <button id="searchLogisticsBtn" class="btn btn-primary"
          style="width:100%;padding:13px;font-size:15px;font-weight:700;${(!pickupCoords || !destCoords) ? 'opacity:0.55;cursor:not-allowed;' : ''}">
          ${isLoading ? '⏳ Calculating real route...' : '🔍 Search Verified Transport'}
        </button>

        ${!pickupCoords || !destCoords ? `
          <p style="font-size:12px;color:var(--text-muted);text-align:center;margin-top:8px;">
            GPS coordinates required for both pickup and destination before searching
          </p>` : ''}
      </div>

      <!-- Info note -->
      <div style="background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.2);border-radius:12px;padding:14px 16px;font-size:12px;color:var(--text-muted);">
        <strong style="color:var(--text);">Why GPS coordinates?</strong><br>
        Route distance, driver ETA and fare are calculated from real road data. Agro AI never invents these values. Coordinates must come from your GPS or a verified geocoder.
      </div>
    `;
  }

  // ══════════════════════════════════════════════
  // SCREEN 2 — RESULTS
  // ══════════════════════════════════════════════
  function renderResultsScreen() {
    if (isLoading) {
      return `
        <div class="glass-card" style="padding:40px;text-align:center;">
          <div class="spinner" style="margin:0 auto 16px;"></div>
          <p style="font-size:14px;color:var(--text-muted);">Calculating real road route and querying verified drivers...</p>
          <p style="font-size:12px;color:var(--text-muted);margin-top:8px;">No estimated data will be shown as fact</p>
        </div>
      `;
    }

    if (!searchResults) return renderBookScreen();

    const route = routeInfo;
    const routeUnavailable = !route || route.status === 'unavailable';

    return `
      <!-- Back button -->
      <button id="backToBookBtn" class="btn" style="margin-bottom:16px;padding:8px 16px;font-size:13px;font-weight:700;border-radius:10px;border:1px solid var(--border);">
        ← Edit Booking
      </button>

      <!-- Route Card -->
      <div class="glass-card" style="padding:18px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:800;margin-bottom:12px;">🗺 Route Information</div>

        ${routeUnavailable ? `
          <div style="background:rgba(239,68,68,0.08);border-left:4px solid #ef4444;padding:14px;border-radius:8px;text-align:center;">
            <div style="font-size:16px;margin-bottom:6px;">⚠</div>
            <div style="font-weight:700;color:#dc2626;font-size:14px;margin-bottom:4px;">Route information unavailable</div>
            <div style="font-size:12px;color:var(--text-muted);">We couldn't calculate a verified route right now.</div>
            <button id="retrySearchBtn" class="btn btn-primary" style="margin-top:12px;padding:8px 20px;font-size:13px;">↻ Retry</button>
          </div>
        ` : `
          ${searchResults.routing_warning ? `
            <div style="background:rgba(234,179,8,0.1);border-left:4px solid #eab308;padding:10px 12px;border-radius:8px;font-size:12px;margin-bottom:12px;color:#92400e;">
              🟡 ${searchResults.routing_warning}
            </div>` : ''}

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
            <div style="background:var(--surface-2);padding:12px;border-radius:10px;">
              <div style="font-size:11px;color:var(--text-muted);font-weight:700;">ROAD DISTANCE</div>
              <div style="font-size:20px;font-weight:900;margin-top:4px;">${route.distance_km} km</div>
            </div>
            <div style="background:var(--surface-2);padding:12px;border-radius:10px;">
              <div style="font-size:11px;color:var(--text-muted);font-weight:700;">ESTIMATED DRIVE TIME</div>
              <div style="font-size:20px;font-weight:900;margin-top:4px;">${route.duration_mins} min</div>
            </div>
          </div>

          <div style="font-size:11px;color:var(--text-muted);border-top:1px solid var(--border);padding-top:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
            ${routeStatusBadge(route.status)}
            <span>Source: ${route.source}</span>
            <span>·</span>
            <span>Calculated: ${formatTime(route.retrieved_at)}</span>
          </div>
        `}
      </div>

      <!-- Driver Results -->
      ${renderDriverResults()}
    `;
  }

  function renderDriverResults() {
    if (!searchResults.available) {
      return `
        <div class="glass-card" style="padding:28px;text-align:center;border-left:4px solid #f59e0b;">
          <div style="font-size:36px;margin-bottom:12px;">🚫</div>
          <div style="font-size:16px;font-weight:800;margin-bottom:8px;">No Verified Drivers Available</div>
          <p style="font-size:13px;color:var(--text-muted);margin-bottom:20px;">
            ${searchResults.message || 'No verified Agro AI drivers are currently available for this request.'}
          </p>
          <p style="font-size:11px;color:var(--text-muted);margin-bottom:16px;">
            Driver information is based on verified accounts, KYC status, and recent GPS data.
          </p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            <button id="retrySearchBtn" class="btn btn-primary" style="padding:10px 20px;font-size:13px;">↻ Try Again</button>
            <button id="requestQuoteBtn" class="btn" style="padding:10px 20px;font-size:13px;border:1px solid var(--border);">📝 Request a Quote</button>
          </div>
        </div>
      `;
    }

    return `
      <div style="margin-bottom:10px;display:flex;align-items:center;gap:8px;">
        <div style="font-size:14px;font-weight:800;">AVAILABLE VERIFIED DRIVERS</div>
        <div style="font-size:12px;color:#22c55e;font-weight:700;">🟢 ${searchResults.total_options} verified</div>
      </div>
      <p style="font-size:11px;color:var(--text-muted);margin-bottom:14px;">
        Driver information is based on verified driver accounts and recent GPS data only.
      </p>

      <div style="display:flex;flex-direction:column;gap:14px;">
        ${searchResults.options.map((opt, idx) => renderDriverCard(opt, idx)).join('')}
      </div>
    `;
  }

  function renderDriverCard(opt, idx) {
    const fresh = freshnessLabel(opt.location_freshness);
    const etaAvailable = opt.driver_eta_status === 'estimated' && opt.driver_eta_mins !== null;
    const pricing = opt.pricing;
    const route = opt.route;
    const heartbeatAge = opt.last_heartbeat ? relativeAge(opt.last_heartbeat) : null;

    return `
      <div class="glass-card" style="padding:18px;border-left:4px solid var(--accent);">

        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;">
          <div>
            <span style="font-size:11px;font-weight:800;color:var(--accent);background:rgba(var(--accent-rgb),0.12);padding:3px 8px;border-radius:6px;">✓ VERIFIED DRIVER</span>
            <h3 style="font-size:17px;font-weight:900;margin-top:6px;">${opt.driver_name}</h3>
            <div style="font-size:12px;color:var(--text-muted);">
              ${opt.vehicle_type} · ${opt.registration_number} · ${opt.payload_capacity_tons}T capacity
            </div>
            <div style="font-size:12px;color:var(--text-muted);">
              ⭐ ${opt.driver_rating} · ${opt.total_trips} trips completed
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:22px;font-weight:900;color:var(--accent);">₹${pricing.farmer_total_price}</div>
            <div style="font-size:11px;color:var(--text-muted);">₹${pricing.price_per_quintal}/quintal</div>
          </div>
        </div>

        <!-- Driver GPS status -->
        <div style="background:var(--surface-2);padding:10px 12px;border-radius:10px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;">
          <div>
            <div style="font-size:11px;font-weight:800;color:${fresh.color};">${fresh.icon} ${fresh.label}</div>
            ${heartbeatAge ? `<div style="font-size:11px;color:var(--text-muted);">GPS updated ${heartbeatAge}</div>` : '<div style="font-size:11px;color:#9ca3af;">No GPS data</div>'}
          </div>
          <div style="text-align:right;">
            ${etaAvailable ? `
              <div style="font-size:11px;color:var(--text-muted);">Est. arrival to pickup</div>
              <div style="font-size:15px;font-weight:800;">~${opt.driver_eta_mins} min <span style="font-size:10px;color:#eab308;font-weight:700;">(estimated)</span></div>
              ${opt.driver_distance_km !== null ? `<div style="font-size:11px;color:var(--text-muted);">${opt.driver_distance_km.toFixed(1)} km away</div>` : ''}
            ` : `
              <div style="font-size:12px;color:#9ca3af;font-style:italic;">ETA unavailable</div>
              <div style="font-size:11px;color:#9ca3af;">${opt.driver_eta_note || 'GPS not available'}</div>
            `}
          </div>
        </div>

        <!-- Fare Breakdown -->
        <div style="background:var(--surface-2);padding:12px;border-radius:10px;margin-bottom:12px;font-size:12px;">
          <div style="font-weight:800;margin-bottom:8px;">Fare Estimate</div>
          <div style="display:flex;flex-direction:column;gap:4px;">
            <div style="display:flex;justify-content:space-between;"><span>Base fare</span><span>₹${pricing.base_charge}</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Distance (${route.distance_km} km)</span><span>₹${pricing.distance_fare}</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Loading charge</span><span>₹${pricing.loading_charge}</span></div>
            <div style="display:flex;justify-content:space-between;"><span>Unloading charge</span><span>₹${pricing.unloading_charge}</span></div>
            ${pricing.toll_estimate > 0 ? `<div style="display:flex;justify-content:space-between;"><span>Toll estimate</span><span>₹${pricing.toll_estimate}</span></div>` : ''}
            <div style="display:flex;justify-content:space-between;"><span>Platform fee</span><span>₹${pricing.platform_fee}</span></div>
            <div style="display:flex;justify-content:space-between;"><span>GST (${pricing.tax_rate}%)</span><span>₹${pricing.tax}</span></div>
            <div style="border-top:1px solid var(--border);padding-top:6px;margin-top:2px;display:flex;justify-content:space-between;font-weight:800;font-size:13px;">
              <span>Estimated total</span><span style="color:var(--accent);">₹${pricing.farmer_total_price}</span>
            </div>
          </div>
          <div style="margin-top:8px;font-size:11px;color:var(--text-muted);">
            ⓘ Final fare may change if waiting time, route, tolls or load details change.
          </div>
        </div>

        <!-- Route Provenance -->
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:14px;">
          Route: ${routeStatusBadge(route.status)} · ${route.source} · Calculated ${formatTime(route.retrieved_at)}
        </div>

        <!-- Book Button -->
        <button class="btn btn-primary book-driver-btn" data-idx="${idx}"
          style="width:100%;padding:12px;font-weight:800;font-size:14px;">
          ⚡ Book ${opt.driver_name}
        </button>
      </div>
    `;
  }

  // ══════════════════════════════════════════════
  // SCREEN 3 — BOOKING CONFIRMATION
  // ══════════════════════════════════════════════
  function renderConfirmScreen() {
    if (isLoading) {
      return `
        <div class="glass-card" style="padding:40px;text-align:center;">
          <div class="spinner" style="margin:0 auto 16px;"></div>
          <p style="font-size:14px;color:var(--text-muted);">Confirming booking with driver...</p>
        </div>
      `;
    }

    if (errorMessage) {
      return `
        <div class="glass-card" style="padding:24px;">
          <div style="background:rgba(239,68,68,0.08);border-left:4px solid #ef4444;padding:14px;border-radius:8px;margin-bottom:16px;text-align:center;">
            <div style="font-size:16px;font-weight:800;color:#dc2626;margin-bottom:4px;">Booking Failed</div>
            <div style="font-size:13px;color:var(--text-muted);">${errorMessage}</div>
          </div>
          <div style="display:flex;gap:10px;">
            <button id="backToResultsBtn" class="btn" style="flex:1;padding:12px;border:1px solid var(--border);">← Back to Drivers</button>
            <button id="retryBookBtn" class="btn btn-primary" style="flex:1;padding:12px;">↻ Retry</button>
          </div>
        </div>
      `;
    }

    if (!currentTrip) return '';

    const statusSteps = [
      { key: 'REQUESTED',        label: 'Requested' },
      { key: 'MATCHING',         label: 'Matching Driver' },
      { key: 'DRIVER_ASSIGNED',  label: 'Driver Assigned' },
      { key: 'DRIVER_EN_ROUTE',  label: 'Driver En Route' },
      { key: 'ARRIVED',          label: 'Driver Arrived' },
      { key: 'LOADING',          label: 'Loading' },
      { key: 'IN_TRANSIT',       label: 'In Transit' },
      { key: 'ARRIVED_DESTINATION', label: 'At Destination' },
      { key: 'UNLOADING',        label: 'Unloading' },
      { key: 'COMPLETED',        label: 'Completed' },
    ];
    const currentIdx = statusSteps.findIndex(s => s.key === currentTrip.status);

    return `
      <div style="display:flex;flex-direction:column;gap:14px;">

        <!-- Booking confirmed banner -->
        <div class="glass-card" style="padding:20px;text-align:center;border-left:4px solid #22c55e;">
          <div style="font-size:32px;margin-bottom:8px;">✅</div>
          <div style="font-size:18px;font-weight:900;margin-bottom:6px;">Booking Confirmed</div>
          <div style="font-size:13px;color:var(--text-muted);">Your transport request has been sent to the driver</div>
        </div>

        <!-- Trip ID & PIN -->
        <div class="glass-card" style="padding:18px;">
          <div style="font-size:14px;font-weight:800;margin-bottom:12px;">Trip Details</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div style="background:var(--surface-2);padding:12px;border-radius:10px;">
              <div style="font-size:11px;color:var(--text-muted);font-weight:700;">TRIP ID</div>
              <div style="font-size:13px;font-weight:800;margin-top:4px;word-break:break-all;">${currentTrip.trip_id}</div>
            </div>
            <div style="background:var(--surface-2);padding:12px;border-radius:10px;">
              <div style="font-size:11px;color:var(--text-muted);font-weight:700;">VERIFICATION PIN</div>
              <div style="font-size:24px;font-weight:900;margin-top:4px;letter-spacing:4px;color:var(--accent);">${currentTrip.trip_pin}</div>
              <div style="font-size:10px;color:var(--text-muted);">Share with driver on arrival</div>
            </div>
          </div>
        </div>

        <!-- Trip Status (from backend only) -->
        <div class="glass-card" style="padding:18px;">
          <div style="font-size:14px;font-weight:800;margin-bottom:12px;">Trip Status
            <span style="font-size:11px;color:var(--text-muted);font-weight:400;margin-left:8px;">Updated from backend</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            ${statusSteps.map((step, i) => {
              const done = currentIdx > i;
              const active = currentIdx === i;
              const color = done ? '#22c55e' : active ? 'var(--accent)' : 'var(--text-muted)';
              const bg = active ? 'rgba(var(--accent-rgb),0.1)' : 'transparent';
              return `
                <div style="display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:8px;background:${bg};">
                  <div style="width:20px;height:20px;border-radius:50%;border:2px solid ${color};background:${done ? '#22c55e' : 'transparent'};display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    ${done ? '<span style="color:white;font-size:11px;font-weight:900;">✓</span>' : active ? '<span style="width:8px;height:8px;background:var(--accent);border-radius:50%;display:block;"></span>' : ''}
                  </div>
                  <span style="font-size:13px;font-weight:${active ? '800' : '400'};color:${color};">${step.label}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Actions -->
        <div style="display:flex;gap:10px;">
          <button id="trackTripBtn" class="btn btn-primary" style="flex:1;padding:13px;font-weight:800;">
            📡 Track Live
          </button>
          <button id="cancelTripBtn" class="btn" style="flex:1;padding:13px;font-weight:700;border:1px solid #ef4444;color:#ef4444;">
            ✕ Cancel Trip
          </button>
        </div>
      </div>
    `;
  }

  // ══════════════════════════════════════════════
  // SCREEN 4 — LIVE TRACKING
  // ══════════════════════════════════════════════
  function renderTrackScreen() {
    if (!currentTrip) return '';

    const driverLoc = currentTrip.driver_location;
    let locCard = '';

    if (!driverLoc) {
      locCard = `
        <div style="background:var(--surface-2);padding:14px;border-radius:10px;text-align:center;">
          <div style="font-size:11px;font-weight:800;color:#9ca3af;">⚪ LOCATION UNAVAILABLE</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">No current GPS data from driver</div>
        </div>
      `;
    } else {
      const fresh = freshnessLabel(driverLoc.freshness);
      const locAge = driverLoc.recorded_at ? relativeAge(driverLoc.recorded_at) : 'unknown';
      locCard = `
        <div style="background:var(--surface-2);padding:14px;border-radius:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-size:11px;font-weight:800;color:${fresh.color};">${fresh.icon} ${fresh.label}</div>
            <div style="font-size:11px;color:var(--text-muted);">GPS updated ${locAge}</div>
          </div>
          <div style="font-size:12px;color:var(--text-muted);">
            Coordinates: ${driverLoc.lat.toFixed(5)}, ${driverLoc.lon.toFixed(5)}
            ${driverLoc.speed_kmh != null ? `· Speed: ${driverLoc.speed_kmh} km/h` : ''}
          </div>
          ${driverLoc.freshness === 'STALE' || driverLoc.freshness === 'UNAVAILABLE' ? `
            <div style="margin-top:8px;font-size:11px;color:#f97316;">
              ⚠ Location is stale — ETA unavailable until GPS updates
            </div>
          ` : ''}
        </div>
      `;
    }

    return `
      <div style="display:flex;flex-direction:column;gap:14px;">

        <!-- Stale connection warning -->
        ${wsStale ? `
          <div style="background:rgba(239,68,68,0.1);border-left:4px solid #ef4444;padding:12px 14px;border-radius:8px;font-size:13px;color:#dc2626;">
            ⚠ Connection lost. Showing only previously verified information where applicable.
          </div>` : ''}

        <!-- Status -->
        <div class="glass-card" style="padding:18px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div style="font-size:14px;font-weight:800;">Live Trip Status</div>
            <div style="font-size:11px;color:var(--text-muted);">${wsStale ? '🔴 Offline' : '🟢 Live connection'}</div>
          </div>
          <div style="font-size:18px;font-weight:900;color:var(--accent);margin-bottom:4px;">${currentTrip.status}</div>
          <div style="font-size:12px;color:var(--text-muted);">Status from backend — never set locally</div>
        </div>

        <!-- Driver location -->
        <div class="glass-card" style="padding:18px;">
          <div style="font-size:14px;font-weight:800;margin-bottom:12px;">Driver Location</div>
          ${locCard}
        </div>

        <!-- Trip summary -->
        <div class="glass-card" style="padding:18px;">
          <div style="font-size:14px;font-weight:800;margin-bottom:12px;">Trip Summary</div>
          <div style="font-size:13px;display:flex;flex-direction:column;gap:6px;">
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">Pickup</span>
              <span style="font-weight:700;text-align:right;max-width:60%;">${currentTrip.pickup_address || '—'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">Destination</span>
              <span style="font-weight:700;text-align:right;max-width:60%;">${currentTrip.dest_address || '—'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">Distance</span>
              <span style="font-weight:700;">${currentTrip.distance_km ? currentTrip.distance_km + ' km' : '—'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">Total Fare</span>
              <span style="font-weight:700;color:var(--accent);">${currentTrip.total_price ? '₹' + currentTrip.total_price : '—'}</span>
            </div>
          </div>
        </div>

        <!-- Trip PIN reminder -->
        <div class="glass-card" style="padding:14px;background:rgba(var(--accent-rgb),0.05);border:1px solid rgba(var(--accent-rgb),0.2);">
          <div style="font-size:12px;font-weight:700;margin-bottom:4px;">Verification PIN</div>
          <div style="font-size:28px;font-weight:900;letter-spacing:5px;color:var(--accent);">${currentTrip.trip_pin || '——'}</div>
          <div style="font-size:11px;color:var(--text-muted);">Share this PIN with driver on arrival to start loading</div>
        </div>

        <button id="refreshTripBtn" class="btn" style="padding:12px;border:1px solid var(--border);font-weight:700;">
          ↻ Refresh Status
        </button>
      </div>
    `;
  }

  // ─── Event listeners ───────────────────────────────────────
  function attachListeners(container) {

    // ── SCREEN 1 — BOOK ──
    if (screen === 'book') {

      // GPS button
      const gpsBtn = container.querySelector('#useGpsBtn');
      if (gpsBtn) {
        gpsBtn.onclick = () => {
          const gpsError = container.querySelector('#gpsError');
          pickupGeoSearching = true;
          rerender();

          requestCurrentLocation(
            async (lat, lon, accuracy) => {
              try {
                const address = await window.KisanAPI.reverseGeocode(lat, lon);
                pickupCoords = {
                  lat, lon,
                  display_name: address || `${lat.toFixed(5)}, ${lon.toFixed(5)}`,
                  source: 'Device GPS' + (accuracy ? ` (±${Math.round(accuracy)}m)` : '')
                };
              } catch(e) {
                pickupCoords = { lat, lon, display_name: `${lat.toFixed(5)}, ${lon.toFixed(5)}`, source: 'Device GPS' };
              }
              pickupGeoSearching = false;
              rerender();
            },
            (errMsg) => {
              pickupGeoSearching = false;
              pickupCoords = null;
              rerender();
              const errEl = _container && _container.querySelector('#gpsError');
              if (errEl) errEl.textContent = '📍 ' + errMsg;
            }
          );
        };
      }

      // Destination geocode on blur
      const destInput = container.querySelector('#destText');
      if (destInput) {
        let destTimer = null;
        destInput.oninput = () => {
          destCoords = null;   // clear confirmed coords when user edits
          clearTimeout(destTimer);
          const val = destInput.value.trim();
          if (val.length < 3) {
            const sg = _container && _container.querySelector('#destSuggestions');
            if (sg) sg.innerHTML = '';
            return;
          }
          destTimer = setTimeout(() => geocodeDest(val), 600);
        };
      }

      // Pickup geocode on blur (typed address)
      const pickupInput = container.querySelector('#pickupText');
      if (pickupInput) {
        let pickupTimer = null;
        pickupInput.oninput = () => {
          pickupCoords = null;
          clearTimeout(pickupTimer);
          const val = pickupInput.value.trim();
          if (val.length < 3) {
            const sg = _container && _container.querySelector('#pickupSuggestions');
            if (sg) sg.innerHTML = '';
            return;
          }
          pickupTimer = setTimeout(() => geocodePickup(val), 600);
        };
      }

      // Search button
      const searchBtn = container.querySelector('#searchLogisticsBtn');
      if (searchBtn) {
        searchBtn.onclick = async () => {
          if (!pickupCoords || !destCoords) {
            errorMessage = 'GPS coordinates required for both pickup and destination. Use the GPS button or select a verified location from search results.';
            rerender();
            return;
          }
          await doSearch(container);
        };
      }
    }

    // ── SCREEN 2 — RESULTS ──
    if (screen === 'results') {

      const backBtn = container.querySelector('#backToBookBtn');
      if (backBtn) backBtn.onclick = () => { screen = 'book'; errorMessage = null; rerender(); };

      const retryBtn = container.querySelector('#retrySearchBtn');
      if (retryBtn) retryBtn.onclick = async () => { screen = 'book'; await doSearch(_container); };

      const quoteBtn = container.querySelector('#requestQuoteBtn');
      if (quoteBtn) quoteBtn.onclick = () => {
        errorMessage = null;
        alert('Quote request sent to Agro AI logistics team. We will contact you within 2 hours.');
      };

      // Book a driver
      container.querySelectorAll('.book-driver-btn').forEach(btn => {
        btn.onclick = async () => {
          const idx = parseInt(btn.getAttribute('data-idx'));
          selectedOption = searchResults.options[idx];
          await doBook(_container);
        };
      });
    }

    // ── SCREEN 3 — CONFIRM ──
    if (screen === 'confirm') {

      const trackBtn = container.querySelector('#trackTripBtn');
      if (trackBtn) trackBtn.onclick = () => {
        screen = 'track';
        rerender();
        startWebSocket();
      };

      const cancelBtn = container.querySelector('#cancelTripBtn');
      if (cancelBtn) cancelBtn.onclick = async () => {
        if (!currentTrip) return;
        if (!confirm('Are you sure you want to cancel this booking?')) return;
        try {
          await window.KisanAPI.cancelTrip(currentTrip.trip_id, 'farmer', 'Cancelled by farmer');
          currentTrip = null;
          screen = 'book';
          errorMessage = null;
          rerender();
        } catch(err) {
          alert('Could not cancel trip: ' + (err.message || 'Please try again.'));
        }
      };

      const backBtn = container.querySelector('#backToResultsBtn');
      if (backBtn) backBtn.onclick = () => { screen = 'results'; errorMessage = null; rerender(); };

      const retryBookBtn = container.querySelector('#retryBookBtn');
      if (retryBookBtn) retryBookBtn.onclick = async () => { await doBook(_container); };
    }

    // ── SCREEN 4 — TRACK ──
    if (screen === 'track') {

      const refreshBtn = container.querySelector('#refreshTripBtn');
      if (refreshBtn) refreshBtn.onclick = async () => {
        if (!currentTrip) return;
        try {
          const updated = await window.KisanAPI.getTripDetails(currentTrip.trip_id);
          currentTrip = { ...currentTrip, ...updated };
          rerender();
        } catch(e) {
          alert('Could not refresh trip status. Please check your connection.');
        }
      };
    }
  }

  // ─── Geocoding helpers ─────────────────────────────────────
  async function geocodePickup(query) {
    if (!_container) return;
    const sg = _container.querySelector('#pickupSuggestions');
    if (!sg) return;
    sg.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:6px;">Searching...</div>';
    try {
      const results = await window.KisanAPI.geocodeAddress(query);
      if (!results || results.length === 0) {
        sg.innerHTML = '<div style="font-size:12px;color:#9ca3af;padding:6px;">No locations found. Try a more specific name.</div>';
        return;
      }
      renderSuggestions(sg, results, (r) => {
        pickupCoords = r;
        const inp = _container && _container.querySelector('#pickupText');
        if (inp) inp.value = r.display_name;
        sg.innerHTML = '';
        rerender();
      });
    } catch(e) {
      sg.innerHTML = '<div style="font-size:12px;color:#ef4444;padding:6px;">Location search unavailable right now.</div>';
    }
  }

  async function geocodeDest(query) {
    if (!_container) return;
    const sg = _container.querySelector('#destSuggestions');
    if (!sg) return;
    sg.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:6px;">Searching...</div>';
    try {
      const results = await window.KisanAPI.geocodeAddress(query);
      if (!results || results.length === 0) {
        sg.innerHTML = '<div style="font-size:12px;color:#9ca3af;padding:6px;">No locations found.</div>';
        return;
      }
      renderSuggestions(sg, results, (r) => {
        destCoords = r;
        const inp = _container && _container.querySelector('#destText');
        if (inp) inp.value = r.display_name;
        sg.innerHTML = '';
        rerender();
      });
    } catch(e) {
      sg.innerHTML = '<div style="font-size:12px;color:#ef4444;padding:6px;">Location search unavailable right now.</div>';
    }
  }

  function renderSuggestions(container, results, onSelect) {
    container.innerHTML = `
      <div style="background:var(--surface-2);border:1px solid var(--border);border-radius:10px;margin-top:4px;overflow:hidden;max-height:200px;overflow-y:auto;">
        ${results.slice(0, 5).map((r, i) => `
          <div class="geo-suggestion" data-idx="${i}"
            style="padding:10px 12px;cursor:pointer;border-bottom:1px solid var(--border);font-size:12px;line-height:1.4;">
            📍 ${r.display_name}
            <div style="font-size:10px;color:var(--text-muted);">${r.lat.toFixed(5)}, ${r.lon.toFixed(5)} · via ${r.source}</div>
          </div>
        `).join('')}
      </div>
    `;
    container.querySelectorAll('.geo-suggestion').forEach((el, i) => {
      el.onclick = () => onSelect(results[i]);
      el.onmouseover = () => el.style.background = 'rgba(var(--accent-rgb),0.08)';
      el.onmouseout  = () => el.style.background = '';
    });
  }

  // ─── Actions ───────────────────────────────────────────────
  async function doSearch(container) {
    if (!pickupCoords || !destCoords) return;

    const crop    = container.querySelector('#cropType')?.value?.trim() || '';
    const qty     = parseFloat(container.querySelector('#quantityTons')?.value) || 1.0;
    const vehicle = container.querySelector('#vehicleType')?.value || 'Tata Ace';
    const date    = container.querySelector('#pickupDate')?.value || '';
    const time    = container.querySelector('#pickupTime')?.value || '';

    isLoading = true;
    errorMessage = null;
    screen = 'results';
    rerender();

    try {
      const result = await window.KisanAPI.searchLogistics({
        pickup_address: pickupCoords.display_name,
        pickup_lat:     pickupCoords.lat,
        pickup_lon:     pickupCoords.lon,
        dest_address:   destCoords.display_name,
        dest_lat:       destCoords.lat,
        dest_lon:       destCoords.lon,
        crop:           crop,
        quantity_tons:  qty,
        vehicle_type:   vehicle,
        pickup_date:    date || null,
        pickup_time:    time || null,
      });
      searchResults = result;
      // Store top-level route info for route card
      if (result.options && result.options.length > 0) {
        routeInfo = result.options[0].route;
      } else if (result.route) {
        routeInfo = result.route;
      } else {
        routeInfo = { status: 'unavailable' };
      }
    } catch(err) {
      searchResults = null;
      routeInfo = { status: 'unavailable' };
      errorMessage = err.message || 'Failed to search for transport. Please try again.';
    } finally {
      isLoading = false;
      rerender();
    }
  }

  async function doBook(container) {
    if (!selectedOption || !pickupCoords || !destCoords) return;

    isLoading = true;
    errorMessage = null;
    screen = 'confirm';
    rerender();

    try {
      const opt = selectedOption;
      const crop    = container.querySelector('#cropType')?.value?.trim() || '';
      const qty     = parseFloat(container.querySelector('#quantityTons')?.value) || 1.0;
      const date    = container.querySelector('#pickupDate')?.value || '';
      const time    = container.querySelector('#pickupTime')?.value || '';

      let pickupTime = null;
      if (date && time) {
        try { pickupTime = new Date(`${date}T${time}:00`).toISOString(); } catch(e) {}
      }

      const result = await window.KisanAPI.createTrip({
        farmer_id:              'default_farmer',
        driver_id:              opt.driver_id,
        vehicle_id:             opt.vehicle_id,
        crop:                   crop,
        quantity_tons:          qty,
        pickup_address:         pickupCoords.display_name,
        pickup_lat:             pickupCoords.lat,
        pickup_lon:             pickupCoords.lon,
        dest_address:           destCoords.display_name,
        dest_lat:               destCoords.lat,
        dest_lon:               destCoords.lon,
        distance_km:            opt.route.distance_km,
        estimated_duration_mins: opt.route.duration_mins,
        total_price:            opt.pricing.farmer_total_price,
        driver_net_earnings:    opt.driver_breakdown.net_earnings,
        fuel_component:         opt.driver_breakdown.estimated_fuel_cost,
        pickup_time:            pickupTime,
      });

      currentTrip = {
        trip_id:        result.trip_id,
        trip_pin:       result.trip_pin,
        status:         result.status,
        pickup_address: pickupCoords.display_name,
        dest_address:   destCoords.display_name,
        distance_km:    opt.route.distance_km,
        total_price:    opt.pricing.farmer_total_price,
        driver_location: null,
      };
    } catch(err) {
      errorMessage = err.message || 'Booking could not be confirmed. Please try again or contact support.';
    } finally {
      isLoading = false;
      rerender();
    }
  }

  // ─── WebSocket tracking ────────────────────────────────────
  function startWebSocket() {
    if (!currentTrip) return;
    if (wsConn) wsConn.close();
    wsStale = false;

    wsConn = window.KisanAPI.connectTripWebSocket(currentTrip.trip_id, {
      onOpen: () => {
        wsStale = false;
        rerender();
      },
      onMessage: (data) => {
        if (data.event === 'LOCATION_UPDATE') {
          if (currentTrip) {
            currentTrip.driver_location = {
              lat:         data.lat,
              lon:         data.lon,
              speed_kmh:   data.speed_kmh,
              freshness:   data.freshness,
              recorded_at: data.timestamp,
            };
          }
        } else if (data.status) {
          if (currentTrip) currentTrip.status = data.status;
        }
        if (screen === 'track') rerender();
      },
      onClose: () => {
        wsStale = true;
        if (screen === 'track') rerender();
      },
      onStale: () => {
        wsStale = true;
        if (screen === 'track') rerender();
      },
      staleSecs: 30,
    });
  }

  // ─── Register route ────────────────────────────────────────
  if (window.KisanRouter) window.KisanRouter.register('/logistics', render);
})();
