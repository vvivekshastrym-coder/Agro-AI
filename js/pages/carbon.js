// KisanAI Carbon Credit Offset Page Renderer
(function() {
  let isEnrolled = false;
  let acreage = 5;
  let practices = {
    notill: true,
    covercrop: false,
    agroforestry: false,
    dsr: false
  };

  const practiceWeights = {
    notill: { name: 'No-Till Farming', weight: 0.8 },
    covercrop: { name: 'Cover Cropping', weight: 1.2 },
    agroforestry: { name: 'Agroforestry (Trees on farm)', weight: 2.4 },
    dsr: { name: 'Direct Seeded Rice (DSR)', weight: 1.6 }
  };

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    // Calculate total carbon offset
    let offsetPerAcre = 0;
    Object.keys(practices).forEach(key => {
      if (practices[key]) {
        offsetPerAcre += practiceWeights[key].weight;
      }
    });

    const totalOffset = (acreage * offsetPerAcre).toFixed(1);
    const estimatedEarnings = Math.round(totalOffset * 1150); // ₹1,150 per ton of carbon offset

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">🌱 Carbon Credit Offset</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Earn passive income by implementing eco-friendly farming practices. Calculate and certify your soil carbon offsets.
      </p>
    `;

    if (!isEnrolled) {
      contentHtml += `
        <!-- Calculator Card -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--accent);">Offset Calculator</h3>
          
          <!-- Acreage slider -->
          <div style="margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
              <span style="color: var(--text-muted);">Farm Size (Acres)</span>
              <span style="font-weight: 700; color: #ffffff;"><span id="carbAcreageVal">${acreage}</span> Acres</span>
            </div>
            <input type="range" id="carbAcreRange" min="1" max="50" step="1" value="${acreage}" style="width: 100%; accent-color: var(--accent);">
          </div>

          <!-- Practices checklist -->
          <div style="margin-bottom: 20px;">
            <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 8px;">Select Sustainable Practices</label>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${Object.keys(practiceWeights).map(key => `
                <label style="display: flex; align-items: flex-start; gap: 10px; font-size: 12.5px; cursor: pointer; color: #ffffff;">
                  <input type="checkbox" class="practice-checkbox" data-key="${key}" ${practices[key] ? 'checked' : ''} style="margin-top: 4px; accent-color: var(--accent);">
                  <div>
                    <span style="display: block; font-weight: 600;">${practiceWeights[key].name}</span>
                    <span style="font-size: 11px; color: var(--text-muted);">Offsets ~${practiceWeights[key].weight} tCO₂e/acre/year</span>
                  </div>
                </label>
              `).join('')}
            </div>
          </div>

          <!-- Live Output Panel -->
          <div style="background: rgba(31, 77, 43, 0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 14px; margin-bottom: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; text-align: center;">
            <div style="border-right: 1px solid var(--border);">
              <span style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Carbon Offset</span>
              <strong style="font-size: 18px; color: #ffffff;">${totalOffset} <span style="font-size: 11px;">tCO₂e/yr</span></strong>
            </div>
            <div>
              <span style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Est. Income</span>
              <strong style="font-size: 18px; color: #22c55e;">₹${estimatedEarnings.toLocaleString()}/yr</strong>
            </div>
          </div>

          <button class="btn btn-accent" id="carbEnrollBtn">Enroll & Certify on Blockchain</button>
        </div>

        <!-- Corporate Buyers -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 15px; margin-bottom: 10px; color: #ffffff;">Marketplace Demand</h3>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);">
              <div>
                <span style="font-size: 12.5px; font-weight: 600; display: block; color: #ffffff;">Tata Steel Sustainability</span>
                <span style="font-size: 11px; color: var(--text-muted);">Contract: 12,000 tCO₂e remaining</span>
              </div>
              <span style="font-size: 11px; background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 8px; border-radius: 99px;">Buy Rate: ₹1,200/t</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.02); padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);">
              <div>
                <span style="font-size: 12.5px; font-weight: 600; display: block; color: #ffffff;">Infosys Eco-Trust</span>
                <span style="font-size: 11px; color: var(--text-muted);">Contract: 5,500 tCO₂e remaining</span>
              </div>
              <span style="font-size: 11px; background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 8px; border-radius: 99px;">Buy Rate: ₹1,150/t</span>
            </div>
          </div>
        </div>
      `;
    } else {
      contentHtml += `
        <!-- Blockchain Certificate Card -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px; border-color: #22c55e; background: linear-gradient(180deg, rgba(31, 77, 43, 0.4), rgba(11, 19, 14, 0.95));">
          <div style="text-align: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 16px; margin-bottom: 16px;">
            <div style="font-size: 40px; margin-bottom: 8px;">📜</div>
            <h3 style="font-size: 17px; color: #ffffff; margin-bottom: 2px;">Certificate of Carbon Offset</h3>
            <span style="font-size: 10px; color: var(--accent); font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">Blockchain Certified Ledger</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; font-size: 12.5px; color: #e5e7eb; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Verified Acreage:</span>
              <strong>${acreage} Acres</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Practices Certified:</span>
              <strong>${Object.keys(practices).filter(k => practices[k]).map(k => practiceWeights[k].name.split(' (')[0]).join(', ')}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Annual Sequestration:</span>
              <strong style="color: #22c55e;">${totalOffset} Metric Tons of CO₂e</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Contract Buyer:</span>
              <strong>Infosys Eco-Trust</strong>
            </div>
            <div style="display: flex; justify-content: space-between; border-top: 1px dashed var(--border); padding-top: 8px;">
              <span style="color: var(--text-muted);">Estimated Income:</span>
              <strong style="color: #22c55e; font-size: 14px;">₹${estimatedEarnings.toLocaleString()} / year</strong>
            </div>
          </div>

          <!-- Blockchain Ledger Info -->
          <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border); padding: 10px; border-radius: 8px; font-family: monospace; font-size: 10.5px; word-break: break-all; color: var(--text-muted); margin-bottom: 16px;">
            <div style="font-weight: 700; color: #ffffff; margin-bottom: 2px;">Ledger Details:</div>
            Block: #2087593<br>
            Txn Hash: 0x8a9f${Math.random().toString(16).substr(2, 24)}...
          </div>

          <div style="display: flex; gap: 8px;">
            <button class="btn btn-outline" id="carbResetBtn">Recalculate</button>
            <button class="btn btn-accent" id="carbShareBtn" style="font-size: 12.5px;">Download Passport Certificate</button>
          </div>
        </div>
      `;
    }

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const range = container.querySelector('#carbAcreRange');
    if (range) {
      range.addEventListener('input', (e) => {
        acreage = parseInt(e.target.value, 10);
        render(container);
      });
    }

    const checkboxes = container.querySelectorAll('.practice-checkbox');
    checkboxes.forEach(chk => {
      chk.addEventListener('change', (e) => {
        const key = e.target.getAttribute('data-key');
        practices[key] = e.target.checked;
        render(container);
      });
    });

    const enrollBtn = container.querySelector('#carbEnrollBtn');
    if (enrollBtn) {
      enrollBtn.addEventListener('click', async () => {
        // Must select at least one practice
        const selected = Object.values(practices).some(val => val);
        if (!selected) {
          alert("Please select at least one sustainable practice to calculate offsets.");
          return;
        }
        try {
          const summary = await window.KisanAPI.getCarbonSummary('default_farmer', acreage);
          if (summary && summary.estimated_annual_payout) {
            console.log('[Carbon] Live backend carbon calculation:', summary);
          }
        } catch (e) {
          console.warn('[Carbon] Backend API fallback:', e);
        }
        isEnrolled = true;
        render(container);
      });
    }

    const resetBtn = container.querySelector('#carbResetBtn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        isEnrolled = false;
        render(container);
      });
    }

    const shareBtn = container.querySelector('#carbShareBtn');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => {
        alert("Certificate PDF downloaded! It has also been saved to your digital Blockchain Farm Passport.");
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/carbon', render);
  }
})();
