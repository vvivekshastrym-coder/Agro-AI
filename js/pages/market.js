// ═══════════════════════════════════════════════════════════
// AGRO AI — INPUT MARKETPLACE & MANDI v2.0
// Single Source of Truth Backend Integration
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let activeTab = 'inputs'; // inputs | mandi
  let inputsData = null;
  let mandiData = null;
  let isLoading = false;

  function render(container) {
    container.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 6px;">🛒 Market & Agri Inputs</h1>
        <p style="font-size: 13px; color: var(--text-muted);">Verified input marketplace & live Mandi price transparency</p>
      </div>

      <!-- Tab Switcher -->
      <div style="display: flex; gap: 8px; margin-bottom: 16px; background: var(--surface-2); padding: 4px; border-radius: 12px;">
        <button id="tabInputs" class="btn ${activeTab === 'inputs' ? 'btn-primary' : 'btn-outline'}" style="flex: 1; padding: 10px; font-size: 13px; font-weight: 700; border: none;">🌱 Genuine Inputs</button>
        <button id="tabMandi" class="btn ${activeTab === 'mandi' ? 'btn-primary' : 'btn-outline'}" style="flex: 1; padding: 10px; font-size: 13px; font-weight: 700; border: none;">📊 Live Mandi Rates</button>
      </div>

      <div id="marketContent">${renderContent()}</div>
    `;

    attachListeners(container);
    if (!inputsData && activeTab === 'inputs') loadInputs(container);
    if (!mandiData && activeTab === 'mandi') loadMandi(container);
  }

  function renderContent() {
    if (isLoading) {
      return `
        <div class="glass-card" style="padding: 30px; text-align: center;">
          <div class="spinner" style="margin: 0 auto 12px;"></div>
          <p style="font-size: 13px; color: var(--text-muted);">Fetching live data from backend API...</p>
        </div>
      `;
    }

    return activeTab === 'inputs' ? renderInputs() : renderMandi();
  }

  function renderInputs() {
    if (!inputsData || !inputsData.products || inputsData.products.length === 0) {
      return `
        <div class="glass-card" style="padding: 24px; text-align: center;">
          <p style="font-size: 14px; color: var(--text-muted);">No products currently available for selected query.</p>
        </div>
      `;
    }

    return `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        ${inputsData.products.map(p => `
          <div class="glass-card" style="padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
              <div>
                <span style="font-size: 10px; font-weight: 800; color: var(--accent); background: var(--accent)15; padding: 2px 6px; border-radius: 4px;">${p.category.toUpperCase()}</span>
                <h3 style="font-size: 15px; font-weight: 800; margin-top: 4px;">${p.title}</h3>
                <div style="font-size: 12px; color: var(--text-muted);">${p.brand} · ${p.pack_size}</div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: 18px; font-weight: 900; color: var(--text);">₹${p.current_price}</div>
                <div style="font-size: 11px; color: var(--text-muted);"><del>₹${p.mrp}</del> (${p.discount_pct}% OFF)</div>
              </div>
            </div>

            <!-- Price Per Unit Comparison -->
            <div style="background: var(--surface-2); padding: 8px 12px; border-radius: 8px; font-size: 12px; display: flex; justify-content: space-between; margin-bottom: 10px;">
              <span>Unit Price: <strong>₹${p.price_per_unit}/${p.unit}</strong></span>
              <span>Stock: <strong>${p.stock_count}</strong></span>
            </div>

            <!-- Seller & Source Transparency Badge -->
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">
              <span>🏪 ${p.seller.name} (${p.seller.distance_km} km)</span>
              <span style="background: var(--surface-2); padding: 2px 6px; border-radius: 4px;">LIVE DATA · ${p.metadata.data_source}</span>
            </div>

            <button class="btn btn-primary" onclick="alert('Order placed with ${p.seller.name}!')" style="width: 100%; padding: 8px; font-size: 13px; font-weight: 700;">🛒 Buy Now</button>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderMandi() {
    if (!mandiData || !mandiData.records || mandiData.records.length === 0) {
      return `
        <div class="glass-card" style="padding: 24px; text-align: center;">
          <p style="font-size: 14px; color: var(--text-muted);">Live data unavailable for mandi prices.</p>
        </div>
      `;
    }

    return `
      <div class="glass-card" style="padding: 16px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: var(--text-muted);">
          <span>🟢 LIVE MANDI DATA</span>
          <span>Source: ${mandiData.source}</span>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 10px;">
        ${mandiData.records.map(r => `
          <div class="glass-card" style="padding: 14px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-size: 15px; font-weight: 800;">${r.commodity}</div>
              <div style="font-size: 12px; color: var(--text-muted);">${r.market_name}, ${r.district} (${r.variety})</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 17px; font-weight: 900; color: var(--accent);">₹${r.modal_price}</div>
              <div style="font-size: 11px; color: var(--text-muted);">per ${r.unit} (₹${r.min_price} - ₹${r.max_price})</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  async function loadInputs(container) {
    isLoading = true;
    render(container);
    try {
      inputsData = await window.KisanAPI.getInputMarketplace();
    } catch(e){}
    isLoading = false;
    render(container);
  }

  async function loadMandi(container) {
    isLoading = true;
    render(container);
    try {
      mandiData = await window.KisanAPI.getMandiPrices();
    } catch(e){}
    isLoading = false;
    render(container);
  }

  function attachListeners(container) {
    const tabInputs = container.querySelector('#tabInputs');
    const tabMandi = container.querySelector('#tabMandi');

    if (tabInputs) {
      tabInputs.onclick = () => {
        activeTab = 'inputs';
        render(container);
      };
    }
    if (tabMandi) {
      tabMandi.onclick = () => {
        activeTab = 'mandi';
        render(container);
      };
    }
  }

  if (window.KisanRouter) window.KisanRouter.register('/market', render);
})();
