// KisanAI KisanScore Credit Page Renderer
(function() {
  let scoreState = 'setup'; // 'setup', 'calculating', 'result', 'applied'
  let phone = '';
  let aadhaar = '';
  let kisanScore = 745;
  let selectedOffer = null;

  const offers = [
    {
      id: 1,
      bank: "SBI Krishi Mitra Loan",
      maxAmount: 150000,
      interest: 7.2,
      duration: "12 months",
      badge: "Government Partner"
    },
    {
      id: 2,
      bank: "Samunnati Smallholder Credit",
      maxAmount: 80000,
      interest: 8.5,
      duration: "9 months",
      badge: "Instant Payout"
    }
  ];

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">💳 KisanScore Credit</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Unlock low-interest bank loans using your UPI receipt history, satellite crop intelligence, and soil health scores.
      </p>
    `;

    if (scoreState === 'setup') {
      contentHtml += `
        <!-- Aadhaar & Consent Form -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--accent);">Check Loan Eligibility</h3>
          
          <form id="creditCheckForm" style="display: flex; flex-direction: column; gap: 12px;">
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Aadhaar-Linked Phone Number</label>
              <input type="tel" id="credPhone" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. 9876543210" required>
            </div>
            
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Aadhaar Number</label>
              <input type="text" id="credAadhaar" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="XXXX-XXXX-XXXX" required>
            </div>

            <!-- Authorizations checkboxes -->
            <div style="margin-top: 8px; display: flex; flex-direction: column; gap: 10px;">
              <label style="display: flex; align-items: flex-start; gap: 10px; font-size: 12px; color: #ffffff; cursor: pointer;">
                <input type="checkbox" checked required style="margin-top: 2px; accent-color: var(--accent);">
                <span>Sync UPI inputs & seed purchases history (₹15,400 trans.)</span>
              </label>
              <label style="display: flex; align-items: flex-start; gap: 10px; font-size: 12px; color: #ffffff; cursor: pointer;">
                <input type="checkbox" checked required style="margin-top: 2px; accent-color: var(--accent);">
                <span>Authorize Sentinel-2 Satellite acreage verification (5.4 acres detected)</span>
              </label>
              <label style="display: flex; align-items: flex-start; gap: 10px; font-size: 12px; color: #ffffff; cursor: pointer;">
                <input type="checkbox" checked style="margin-top: 2px; accent-color: var(--accent);">
                <span>Include Soil DNA biological health score (+78 BioScore)</span>
              </label>
            </div>

            <button type="submit" class="btn btn-primary" style="margin-top: 12px;">Build KisanScore & Check Loans</button>
          </form>
        </div>
      `;
    } else if (scoreState === 'calculating') {
      contentHtml += `
        <!-- Loading simulation -->
        <div class="glass-card" style="padding: 24px 16px; text-align: center; margin-bottom: 16px;">
          <div style="font-size: 36px; margin-bottom: 12px; animation: spin 2s linear infinite;">⏳</div>
          <h3 style="font-size: 16px; margin-bottom: 8px; color: #ffffff;">Calculating KisanScore</h3>
          <div id="creditLoaderProgress" style="font-size: 12.5px; color: var(--text-muted); font-style: italic;">
            Connecting to PM-KISAN database...
          </div>
        </div>
      `;

      // Fetch real credit profile from backend while showing loading animation
      (async () => {
        const loader = document.getElementById('creditLoaderProgress');
        try {
          if (loader) loader.innerText = 'Parsing satellite NDVI vegetative crop history...';
          const profile = await window.KisanAPI.getCreditProfile('default_farmer', 3.5);
          if (loader) loader.innerText = 'Analyzing UPI fertilizer transactions...';
          await new Promise(r => setTimeout(r, 800));

          // Use real backend data
          if (profile && profile.credit_score) {
            kisanScore = profile.credit_score;
            // Map backend pre_approved_loans to offers format
            if (profile.pre_approved_loans && profile.pre_approved_loans.length > 0) {
              offers = profile.pre_approved_loans.map((loan, idx) => ({
                id: idx + 1,
                bank: loan.scheme || loan.bank,
                maxAmount: loan.max_amount || 80000,
                interest: parseFloat(profile.interest_rate_effective) || 4.0,
                duration: (loan.tenure_months || 12) + ' months',
                badge: loan.interest_subvention || loan.subsidy_pct || 'Government Partner'
              }));
            }
          }
        } catch (e) {
          console.warn('[Credit] API fallback to demo data:', e);
        }
        scoreState = 'result';
        const appContainer = document.getElementById('app');
        if (appContainer) render(appContainer);
      })();
    } else if (scoreState === 'result') {
      // Score ranges: 300 to 900. 745 is excellent.
      const angle = ((kisanScore - 300) / 600) * 180; // 0 to 180 degrees

      contentHtml += `
        <!-- KisanScore gauge visual -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px; text-align: center;">
          <h3 style="font-size: 15px; margin-bottom: 8px; color: #ffffff;">Your Alternative KisanScore</h3>

          <!-- Gauge SVG -->
          <div style="width: 200px; height: 110px; position: relative; margin: 0 auto 10px auto;">
            <svg width="200" height="110" viewBox="0 0 200 110">
              <!-- Background semi-circle -->
              <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="15" stroke-linecap="round" />
              <!-- Score arc (gradient color) -->
              <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#gaugeGrad)" stroke-width="15" stroke-linecap="round" stroke-dasharray="251.2" stroke-dashoffset="${251.2 - (251.2 * ((kisanScore - 300) / 600))}" />
              
              <!-- Gradient definition -->
              <defs>
                <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#ef4444" />
                  <stop offset="50%" stop-color="#f59e0b" />
                  <stop offset="100%" stop-color="#22c55e" />
                </linearGradient>
              </defs>
            </svg>
            <div style="position: absolute; bottom: 8px; left: 0; right: 0; text-align: center;">
              <span style="font-size: 26px; font-weight: 800; color: #ffffff; display: block; line-height: 1;">${kisanScore}</span>
              <span style="font-size: 11px; color: #22c55e; font-weight: bold; letter-spacing: 0.05em; text-transform: uppercase;">EXCELLENT</span>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: rgba(0,0,0,0.15); padding: 8px; border-radius: 8px; text-align: left; font-size: 11.5px; border: 1px solid var(--border);">
            <div>
              <span style="color: var(--text-muted); display: block; font-size: 10px;">Satellite Verification</span>
              <strong style="color: #22c55e;">+80 pts</strong>
            </div>
            <div style="border-left: 1px solid var(--border); padding-left: 8px;">
              <span style="color: var(--text-muted); display: block; font-size: 10px;">UPI Purchase History</span>
              <strong style="color: #22c55e;">+110 pts</strong>
            </div>
            <div style="border-left: 1px solid var(--border); padding-left: 8px;">
              <span style="color: var(--text-muted); display: block; font-size: 10px;">Soil DNA Report</span>
              <strong style="color: #22c55e;">+45 pts</strong>
            </div>
          </div>
        </div>

        <!-- Available Loan Offers -->
        <h3 style="font-size: 15px; color: #ffffff; margin-bottom: 12px;">Low-Interest Offers Pre-Approved</h3>
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px;">
          ${offers.map(off => `
            <div class="glass-card" style="padding: 14px; border-color: rgba(34, 197, 94, 0.2);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                  <h4 style="font-size: 14px; color: #ffffff; font-weight: bold;">${off.bank}</h4>
                  <span style="font-size: 11px; background: rgba(245,158,11,0.15); color: var(--accent); padding: 1px 6px; border-radius: 4px; font-weight: 500;">${off.badge}</span>
                </div>
                <div style="text-align: right;">
                  <span style="font-size: 16px; font-weight: 800; color: #22c55e; display: block;">${off.interest}% p.a.</span>
                  <span style="font-size: 11px; color: var(--text-muted); text-decoration: line-through;">Standard: 12.5%</span>
                </div>
              </div>

              <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 10px; margin-top: 8px;">
                <div>
                  <span style="font-size: 10.5px; color: var(--text-muted); display: block;">Max Pre-Approved</span>
                  <strong style="font-size: 14px; color: #ffffff;">₹${off.maxAmount.toLocaleString()}</strong>
                </div>
                <button class="btn btn-accent apply-loan-btn" data-id="${off.id}" style="width: auto; padding: 6px 16px; min-height: unset; font-size: 12.5px;">Apply Now</button>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } else if (scoreState === 'applied') {
      contentHtml += `
        <!-- Application submitted status -->
        <div class="glass-card" style="padding: 24px 16px; text-align: center; border-color: rgba(34, 197, 94, 0.3); margin-bottom: 16px;">
          <div style="width: 52px; height: 52px; background: rgba(34,197,94,0.15); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px auto; color: #22c55e; font-size: 26px;">✓</div>
          <h3 style="font-size: 18px; margin-bottom: 4px; color: #ffffff;">Application Submitted!</h3>
          <p style="font-size: 12.5px; color: var(--text-muted); line-height: 1.4; max-width: 320px; margin: 0 auto 16px auto;">
            Your loan request for **₹${selectedOffer.maxAmount.toLocaleString()}** under **${selectedOffer.bank}** has been sent to our bank partner with your verified KisanScore certificate.
          </p>

          <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: 10px; padding: 12px; text-align: left; max-width: 300px; margin: 0 auto 20px auto; font-size: 12px; color: #e5e7eb; display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Application Status:</span>
              <strong style="color: var(--accent);">Provisionally Approved</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Interest Rate:</span>
              <strong style="color: #22c55e;">${selectedOffer.interest}% p.a.</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Verification Hash:</span>
              <strong style="font-family: monospace;">KS-${Math.floor(Math.random()*89999+10000)}</strong>
            </div>
          </div>

          <button class="btn btn-primary" id="creditResetBtn">Back to Credit Portal</button>
        </div>
      `;
    }

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const form = container.querySelector('#creditCheckForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        phone = container.querySelector('#credPhone').value;
        aadhaar = container.querySelector('#credAadhaar').value;
        scoreState = 'calculating';
        render(container);
      });
    }

    const applyBtns = container.querySelectorAll('.apply-loan-btn');
    applyBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        selectedOffer = offers.find(o => o.id === id);
        scoreState = 'applied';
        render(container);
      });
    });

    const resetBtn = container.querySelector('#creditResetBtn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        scoreState = 'setup';
        selectedOffer = null;
        render(container);
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/credit', render);
  }
})();
