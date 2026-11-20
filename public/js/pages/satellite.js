// KisanAI Satellite Twin Page Renderer
(function() {
  let viewMode = 'normal'; // 'normal' or 'ndvi'
  let locationSelected = false;
  let simulatedAlertSent = false;
  let coordsInput = '19.0760° N, 72.8777° E';
  let cropType = 'wheat';
  let ndviData = null; // Real NDVI data from backend API

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">🛰️ Digital Twin (Satellite)</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Monitor farm vegetation index (NDVI) using Sentinel-2 and Google Earth Engine. Predict stress 14 days before it is visible.
      </p>
    `;

    contentHtml += `
      <!-- Step 1: Farm Location & Crop -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--accent);">1. Choose Farm Location</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">
          <div>
            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">GPS Coordinates / Village</label>
            <input type="text" id="satCoordsInput" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" value="${coordsInput}">
          </div>
          <div>
            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Crop Type</label>
            <select id="satCropSelect" class="btn btn-outline" style="background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; color: var(--text); border: 1px solid var(--border);">
              <option value="wheat" ${cropType === 'wheat' ? 'selected' : ''}>Wheat (गेहूं)</option>
              <option value="rice" ${cropType === 'rice' ? 'selected' : ''}>Rice (धान)</option>
              <option value="cotton" ${cropType === 'cotton' ? 'selected' : ''}>Cotton (कपास)</option>
            </select>
          </div>
        </div>
        <button class="btn btn-primary" id="satScanBtn">Analyze Field Twin</button>
      </div>
    `;

    if (locationSelected) {
      contentHtml += `
        <!-- Step 2: Digital Twin Map Visualizer -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px; text-align: center;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="font-size: 15px; text-align: left; color: #ffffff;">Field Digital Twin</h3>
            <div style="display: flex; gap: 4px;">
              <button class="btn ${viewMode === 'normal' ? 'btn-primary' : 'btn-outline'}" id="toggleViewNormal" style="width: auto; padding: 4px 10px; min-height: unset; font-size: 11px;">Normal View</button>
              <button class="btn ${viewMode === 'ndvi' ? 'btn-accent' : 'btn-outline'}" id="toggleViewNdvi" style="width: auto; padding: 4px 10px; min-height: unset; font-size: 11px;">NDVI Heatmap</button>
            </div>
          </div>

          <!-- Interactive Field Grid Representation -->
          <div style="position: relative; width: 100%; height: 200px; border-radius: 12px; overflow: hidden; border: 1px solid var(--border); background: #000; display: flex; align-items: center; justify-content: center; margin-bottom: 12px;">
            ${renderFieldGrid()}
          </div>

          <div style="text-align: left; background: rgba(245, 158, 11, 0.08); padding: 12px; border-radius: 8px; border: 1px dashed rgba(245, 158, 11, 0.4); margin-bottom: 16px;">
            <h4 style="font-size: 13px; color: var(--accent); margin-bottom: 4px;">⚠️ Proactive Stress Alert (14-Day Warning)</h4>
            <p style="font-size: 12px; color: #e5e7eb; line-height: 1.4;">
              Sentinel-2 NDVI detects **chlorophyll depletion (0.42 NDVI)** in the South-East sector. This pattern indicates early **fungal stress** which will become visible to the eye in approx. 14 days.
            </p>
          </div>

          ${ndviData ? `
            <div style="display: flex; justify-content: space-between; align-items: center; background: var(--surface-2); padding: 10px 14px; border-radius: 8px; font-size: 12px; margin-bottom: 12px; text-align: left;">
              <div>
                <span style="font-size: 10px; font-weight: 800; color: var(--accent); display: block;">🛰️ LIVE SATELLITE TELEMETRY</span>
                <strong>${ndviData.provider || 'Sentinel-2 L2A'}</strong> · Mean NDVI: <strong style="color: #22c55e;">${ndviData.ndvi_mean}</strong> (${ndviData.health_category})
              </div>
              <div style="text-align: right; font-size: 11px; color: var(--text-muted);">
                Pass Date: <strong>${ndviData.last_satellite_pass}</strong>
              </div>
            </div>
          ` : ''}
        </div>

        <!-- Step 3: NDVI Trend Chart & Proactive alert simulation -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 15px; margin-bottom: 8px; color: #ffffff;">6-Month NDVI Timeline Trend</h3>
          <p style="font-size: 11.5px; color: var(--text-muted); margin-bottom: 12px;">Health trend showing proactive stress drop below baseline.</p>
          
          <!-- SVG Graph -->
          <div style="width: 100%; overflow-x: auto;">
            <svg viewBox="0 0 320 120" style="width: 100%; height: 120px; background: rgba(0,0,0,0.2); border-radius: 8px;">
              <!-- Grid lines -->
              <line x1="10" y1="20" x2="310" y2="20" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
              <line x1="10" y1="60" x2="310" y2="60" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
              <line x1="10" y1="100" x2="310" y2="100" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
              
              <!-- Baseline (Optimal NDVI 0.8) -->
              <line x1="20" y1="30" x2="300" y2="30" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="3,3" />
              <text x="250" y="25" fill="#22c55e" font-size="7" font-weight="600">Optimal (0.8)</text>

              <!-- Plot line (Normal then stress dip) -->
              <!-- Points: Jan(20,40) Feb(70,38) Mar(120,42) Apr(170,82 dip) May(220,60 recovery) Jun(270,35) -->
              <path d="M 30 40 L 80 38 L 130 44 L 180 88 L 230 65 L 280 40" fill="none" stroke="var(--accent)" stroke-width="2.5" />
              
              <!-- Stress dip indicator -->
              <circle cx="180" cy="88" r="4" fill="red" />
              <text x="182" y="102" fill="red" font-size="7" font-weight="700">Early Stress Dip</text>

              <!-- Labels -->
              <text x="30" y="115" fill="var(--text-muted)" font-size="8">Jan</text>
              <text x="80" y="115" fill="var(--text-muted)" font-size="8">Feb</text>
              <text x="130" y="115" fill="var(--text-muted)" font-size="8">Mar</text>
              <text x="180" y="115" fill="var(--text-muted)" font-size="8">Apr (Stress)</text>
              <text x="230" y="115" fill="var(--text-muted)" font-size="8">May</text>
              <text x="280" y="115" fill="var(--text-muted)" font-size="8">Jun</text>
            </svg>
          </div>

          <div style="margin-top: 16px; border-top: 1px solid var(--border); padding-top: 16px;">
            <button class="btn btn-accent" id="satSimulateAlertBtn">Simulate Auto-Alert (WhatsApp/SMS)</button>
          </div>

          ${simulatedAlertSent ? `
            <div style="margin-top: 12px; background: #075e54; color: white; padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15);">
              <div style="font-weight: 700; font-size: 11px; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">
                <span>💬 WhatsApp Alert Received</span>
                <span style="background: rgba(255,255,255,0.2); padding: 1px 4px; border-radius: 4px; font-size: 9px;">NOW</span>
              </div>
              <p style="font-size: 12px; line-height: 1.4; font-style: italic;">
                "KisanAI SatAlert: We detected chlorophyll drop (early stress) in the Southeast corner of your ${cropType.toUpperCase()} field (Coords: ${coordsInput}). Recommended treatment: Neem oil spray or carbendazim pesticide to avoid outbreak. Ask Kisan GPT for details."
              </p>
            </div>
          ` : ''}
        </div>
      `;
    }

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function renderFieldGrid() {
    if (viewMode === 'normal') {
      return `
        <div style="position: absolute; inset: 0; background: linear-gradient(135deg, #155e2b, #1e3a1e); display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(4, 1fr); padding: 4px; gap: 4px;">
          ${Array.from({length: 16}).map((_, i) => {
            const isStressed = [10, 11, 14, 15].includes(i);
            const bg = isStressed ? '#2c4a22' : '#3f7a3f';
            return `<div style="background: ${bg}; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; opacity: 0.85;">🌾</div>`;
          }).join('')}
        </div>
        <div style="position: absolute; bottom: 8px; left: 8px; background: rgba(0,0,0,0.6); padding: 2px 8px; border-radius: 4px; font-size: 10px;">Natural RGB View</div>
      `;
    } else {
      return `
        <div style="position: absolute; inset: 0; background: #000; display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(4, 1fr); padding: 4px; gap: 4px;">
          ${Array.from({length: 16}).map((_, i) => {
            const isStressed = [10, 11, 14, 15].includes(i);
            const bg = isStressed ? 'linear-gradient(135deg, #ef4444, #f59e0b)' : 'linear-gradient(135deg, #10b981, #047857)';
            const text = isStressed ? '0.42 (Stress)' : '0.81 (Healthy)';
            const color = isStressed ? '#ffffff' : 'rgba(255,255,255,0.7)';
            return `<div style="background: ${bg}; border-radius: 4px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 8px; font-weight: 700; color: ${color}; padding: 2px;">
              <span>🌾</span>
              <span>${text}</span>
            </div>`;
          }).join('')}
        </div>
        <div style="position: absolute; bottom: 8px; left: 8px; background: rgba(0,0,0,0.6); padding: 2px 8px; border-radius: 4px; font-size: 10px; color: var(--accent); font-weight: bold;">Sentinel-2 False-Color NDVI</div>
      `;
    }
  }

  function attachListeners(container) {
    const scanBtn = container.querySelector('#satScanBtn');
    if (scanBtn) {
      scanBtn.addEventListener('click', async () => {
        coordsInput = container.querySelector('#satCoordsInput').value;
        cropType = container.querySelector('#satCropSelect').value;
        locationSelected = true;

        // Fetch real NDVI data from backend
        try {
          ndviData = await window.KisanAPI.getNDVIAnalysis(12.9716, 77.5946);
        } catch (e) {
          console.warn('[Satellite] NDVI API fallback:', e);
          ndviData = null;
        }
        render(container);
      });
    }

    const toggleViewNormal = container.querySelector('#toggleViewNormal');
    if (toggleViewNormal) {
      toggleViewNormal.addEventListener('click', () => {
        viewMode = 'normal';
        render(container);
      });
    }

    const toggleViewNdvi = container.querySelector('#toggleViewNdvi');
    if (toggleViewNdvi) {
      toggleViewNdvi.addEventListener('click', () => {
        viewMode = 'ndvi';
        render(container);
      });
    }

    const alertBtn = container.querySelector('#satSimulateAlertBtn');
    if (alertBtn) {
      alertBtn.addEventListener('click', () => {
        simulatedAlertSent = true;
        render(container);
      });
    }
  }

  if (window.KisanRouter) {
    window.KisanRouter.register('/satellite', render);
  }
})();
