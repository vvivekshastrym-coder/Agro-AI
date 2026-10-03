// KisanAI Blockchain Farm Passport Page Renderer
(function() {
  let activeBatchId = 'B-WHT-983';
  let cropName = 'Premium Sharbati Wheat';
  let timeline = [
    {
      id: 1,
      type: "Sowing",
      date: "2025-11-10",
      notes: "Sown Sharbati Wheat (HD-2967 certified seed). Seed Purity: 99.8%",
      hash: "0x3f5c9e2b109c8530b1ff931a"
    },
    {
      id: 2,
      type: "Soil Prep",
      date: "2025-11-12",
      notes: "Applied Azotobacter bio-fertilizer and organic cow manure compost.",
      hash: "0x4a7e93bd8c221e05f01193ac"
    },
    {
      id: 3,
      type: "Spraying",
      date: "2026-01-14",
      notes: "Neem oil biopesticide spray applied. Zero synthetic chemicals used.",
      hash: "0x9c3bf79a32c25114b01e389d"
    },
    {
      id: 4,
      type: "Harvest",
      date: "2026-04-22",
      notes: "Harvested & bagged in certified jute crop bags at Mandya cooperative.",
      hash: "0xe2b5c73a119d85cf08b291c9"
    }
  ];

  let passportLoaded = false;

  async function loadPassportData(container) {
    if (passportLoaded) return;
    try {
      const data = await window.KisanAPI.getFarmPassport('default_farmer', activeBatchId);
      if (data && data.passport_id) {
        passportLoaded = true;
        if (data.crop) cropName = data.crop;
        if (data.traceability_chain && data.traceability_chain.length > 0) {
          timeline = data.traceability_chain.map((item, idx) => ({
            id: idx + 1,
            type: item.step,
            date: item.date,
            notes: item.result,
            hash: "0x" + Math.random().toString(16).substr(2, 24)
          }));
        }
        render(container);
      }
    } catch (e) {
      console.warn('[Passport] Backend API fallback:', e);
    }
  }

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;
    if (!passportLoaded) loadPassportData(container);

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">🔗 Blockchain Farm Passport</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Generate unique QR codes on your crop bags. Let consumers trace crop purity, seed origin, and pesticide-free timeline on a public ledger.
      </p>
    `;

    contentHtml += `
      <!-- QR and Batch Summary Card -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
        <!-- QR Code Visual -->
        <div style="background: #ffffff; padding: 10px; border-radius: 12px; display: inline-flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: var(--shadow); margin: 0 auto;">
          ${renderQRCode()}
          <span style="font-size: 9.5px; font-weight: 700; color: #0b130e; margin-top: 6px; font-family: monospace;">BATCH: ${activeBatchId}</span>
        </div>

        <div style="flex: 1; min-width: 220px;">
          <span style="font-size: 11px; color: var(--accent); font-weight: bold; text-transform: uppercase;">ACTIVE PASSPORT</span>
          <h3 style="font-size: 18px; margin: 2px 0 6px 0; color: #ffffff;">${cropName}</h3>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4; margin-bottom: 8px;">
            Print this QR code on crop bags. Consumers scan to view the verified soil, pesticide, and origin report.
          </p>
          <span style="font-size: 11px; display: inline-block; background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 8px; border-radius: 4px; font-weight: 600;">✓ Pesticide-Free Certified</span>
        </div>
      </div>

      <!-- Timeline Block -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 16px; color: #ffffff; margin-bottom: 14px;">Ledger Timeline Logs</h3>
        
        <div style="display: flex; flex-direction: column; gap: 16px; position: relative; padding-left: 20px; border-left: 2px solid var(--border);">
          ${renderTimelineSteps()}
        </div>
      </div>

      <!-- Add Event Form -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 15px; margin-bottom: 12px; color: var(--accent);">Add Event to Passport (New Block)</h3>
        
        <form id="passportEventForm" style="display: flex; flex-direction: column; gap: 12px;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Event Type</label>
              <select id="passEventType" class="btn btn-outline" style="background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; color: var(--text); border: 1px solid var(--border);">
                <option value="Sowing">Sowing (बुआई)</option>
                <option value="Soil Prep">Soil Prep (मिट्टी की तैयारी)</option>
                <option value="Irrigation">Irrigation (सिंचाई)</option>
                <option value="Fertilization">Fertilization (उर्वरक प्रयोग)</option>
                <option value="Spraying">Biopesticide Spray (छिड़काव)</option>
                <option value="Harvest">Harvest (कटाई)</option>
              </select>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Date</label>
              <input type="date" id="passEventDate" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; color: var(--text);" value="${new Date().toISOString().split('T')[0]}" required>
            </div>
          </div>

          <div>
            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;">Event Notes / Details</label>
            <textarea id="passEventNotes" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; min-height: 50px; resize: none;" placeholder="e.g. Applied organic neem oil pesticide." required></textarea>
          </div>

          <button type="submit" class="btn btn-primary">Broadcast Event & Mine Block</button>
        </form>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function renderQRCode() {
    // Generate a beautiful simulated QR grid using inline SVG
    return `
      <svg width="100" height="100" viewBox="0 0 100 100" style="background: white;">
        <!-- Top-left positioning square -->
        <rect x="5" y="5" width="25" height="25" fill="#000" />
        <rect x="9" y="9" width="17" height="17" fill="#fff" />
        <rect x="13" y="13" width="9" height="9" fill="#000" />

        <!-- Top-right positioning square -->
        <rect x="70" y="5" width="25" height="25" fill="#000" />
        <rect x="74" y="9" width="17" height="17" fill="#fff" />
        <rect x="78" y="78" width="9" height="9" fill="#000" />

        <!-- Bottom-left positioning square -->
        <rect x="5" y="70" width="25" height="25" fill="#000" />
        <rect x="9" y="74" width="17" height="17" fill="#fff" />
        <rect x="13" y="78" width="9" height="9" fill="#000" />

        <!-- Random data dots grid -->
        <rect x="35" y="5" width="5" height="15" fill="#000" />
        <rect x="45" y="10" width="10" height="5" fill="#000" />
        <rect x="60" y="15" width="5" height="10" fill="#000" />
        
        <rect x="35" y="35" width="15" height="15" fill="#000" />
        <rect x="55" y="30" width="5" height="10" fill="#000" />
        <rect x="65" y="45" width="15" height="5" fill="#000" />
        
        <rect x="5" y="35" width="10" height="5" fill="#000" />
        <rect x="20" y="45" width="5" height="15" fill="#000" />

        <rect x="35" y="60" width="20" height="5" fill="#000" />
        <rect x="65" y="60" width="5" height="20" fill="#000" />
        <rect x="40" y="75" width="15" height="5" fill="#000" />
        <rect x="75" y="75" width="20" height="20" fill="#000" />
        <rect x="79" y="79" width="12" height="12" fill="#fff" />
        <rect x="83" y="83" width="4" height="4" fill="#000" />

        <rect x="55" y="85" width="15" height="5" fill="#000" />
        <rect x="35" y="90" width="10" height="5" fill="#000" />
      </svg>
    `;
  }

  function renderTimelineSteps() {
    return timeline.map(event => {
      return `
        <div style="position: relative; margin-bottom: 4px;">
          <!-- Node Dot -->
          <div style="position: absolute; left: -26px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent); border: 2px solid var(--bg); z-index: 2;"></div>
          
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
            <strong style="font-size: 13.5px; color: #ffffff;">${event.type}</strong>
            <span style="font-size: 11px; color: var(--accent);">${event.date}</span>
          </div>
          <p style="font-size: 12px; color: #e5e7eb; line-height: 1.4; margin-top: 2px;">${event.notes}</p>
          <span style="font-size: 10px; font-family: monospace; color: var(--text-muted); word-break: break-all; display: block; margin-top: 2px;">Txn: ${event.hash}</span>
        </div>
      `;
    }).join('');
  }

  function attachListeners(container) {
    const form = container.querySelector('#passportEventForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const type = container.querySelector('#passEventType').value;
        const date = container.querySelector('#passEventDate').value;
        const notes = container.querySelector('#passEventNotes').value;

        // Generate a new timeline item
        const newId = timeline.length + 1;
        const hash = "0x" + Math.random().toString(16).substr(2, 24);
        
        timeline.push({ id: newId, type, date, notes, hash });
        
        // Render again to update
        render(container);
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/passport', render);
  }
})();
