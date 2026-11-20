// ═══════════════════════════════════════════════════════════
// AGRO AI — DRONE SCOUT PLATFORM v2.0
// Single Source of Truth Backend Integration
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let droneData = null;
  let isLoading = false;

  function render(container) {
    container.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 6px;">🛸 Drone Scout Services</h1>
        <p style="font-size: 13px; color: var(--text-muted);">DGCA-verified agricultural drone operators for spraying & crop scouting</p>
      </div>

      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <label style="font-size: 12px; font-weight: 700; color: var(--text-muted);">YOUR FARM AREA (ACRES)</label>
        <div style="display: flex; gap: 10px; margin-top: 6px;">
          <input type="number" id="droneAcres" value="5.0" step="0.5" style="flex:1; padding:10px; border-radius:10px; border:1px solid var(--border); background:var(--surface-2); color:var(--text); font-size:14px;">
          <button id="calcDroneBtn" class="btn btn-primary" style="padding:10px 20px;">Recalculate</button>
        </div>
      </div>

      <div id="droneContent">${renderContent()}</div>
    `;

    attachListeners(container);
    if (!droneData) loadDrone(container, 5.0);
  }

  function renderContent() {
    if (isLoading) {
      return `
        <div class="glass-card" style="padding: 30px; text-align: center;">
          <div class="spinner" style="margin: 0 auto 12px;"></div>
          <p style="font-size: 13px; color: var(--text-muted);">Querying DGCA verified drone operators...</p>
        </div>
      `;
    }

    if (!droneData || !droneData.available || droneData.operators.length === 0) {
      return `
        <div class="glass-card" style="padding: 24px; text-align: center; border-left: 4px solid #F59E0B;">
          <div style="font-size: 40px; margin-bottom: 12px;">🛸</div>
          <h3 style="font-size: 16px; font-weight: 800; margin-bottom: 6px;">Live Drone Pricing Unavailable</h3>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px;">No verified operators available nearby right now.</p>
          <button class="btn btn-accent" onclick="alert('Drone spray quote requested!')" style="width: 100%; padding: 12px;">📝 Request Drone Spraying Quote</button>
        </div>
      `;
    }

    return `
      <div style="display: flex; flex-direction: column; gap: 14px;">
        ${droneData.operators.map(op => `
          <div class="glass-card" style="padding: 18px; border-left: 4px solid var(--accent);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
              <div>
                <span style="font-size: 10px; font-weight: 800; color: var(--accent); background: var(--accent)15; padding: 2px 6px; border-radius: 4px;">DGCA VERIFIED: ${op.dgca_registration}</span>
                <h3 style="font-size: 17px; font-weight: 900; margin-top: 4px;">${op.name}</h3>
                <div style="font-size: 12px; color: var(--text-muted);">${op.company} · ${op.drone_model} · ⭐ ${op.rating}</div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: 20px; font-weight: 900; color: var(--accent);">₹${op.cost_breakdown.estimated_total}</div>
                <div style="font-size: 11px; color: var(--text-muted);">₹${op.rate_per_acre}/acre</div>
              </div>
            </div>

            <!-- Cost Breakdown -->
            <div style="background: var(--surface-2); padding: 10px; border-radius: 10px; font-size: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px;">
              <div>Farm Area: <strong>${op.cost_breakdown.farm_area_acres} Acres</strong></div>
              <div>Min Charge: <strong>₹${op.min_booking_charge}</strong></div>
              <div>Distance: <strong>${op.distance_km} km</strong></div>
              <div>Travel Charge: <strong>₹${op.cost_breakdown.travel_charge}</strong></div>
            </div>

            <button class="btn btn-primary" onclick="alert('Drone spray slot booked with ${op.name}!')" style="width: 100%; padding: 10px; font-weight: 700;">⚡ Book Drone Spraying</button>
          </div>
        `).join('')}
      </div>
    `;
  }

  async function loadDrone(container, acres) {
    isLoading = true;
    render(container);
    try {
      droneData = await window.KisanAPI.getDroneOperators(12.9716, 77.5946, acres);
    } catch(e){}
    isLoading = false;
    render(container);
  }

  function attachListeners(container) {
    const calcBtn = container.querySelector('#calcDroneBtn');
    if (calcBtn) {
      calcBtn.onclick = () => {
        const acres = parseFloat(container.querySelector('#droneAcres').value) || 5.0;
        loadDrone(container, acres);
      };
    }
  }

  if (window.KisanRouter) window.KisanRouter.register('/drone', render);
})();
