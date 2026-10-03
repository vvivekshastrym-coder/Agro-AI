// KisanAI Auto-Triggered Insurance Page Renderer
(function() {
  let policyState = 'setup'; // 'setup', 'active', 'payout'
  let cropType = 'cotton';
  let sumInsured = 50000;
  let simulatedDay = 12;
  let txnId = 'TXN' + Math.floor(Math.random() * 90000000 + 10000000);

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;
    const premium = Math.round(sumInsured * 0.02); // 2% premium

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">⚡ Auto-Triggered Insurance</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Parametric crop insurance powered by satellite data. Zero forms, zero surveyors, auto-claim & UPI payout within 24 hours.
      </p>
    `;

    if (policyState === 'setup') {
      contentHtml += `
        <!-- Policy Setup -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--accent);">Configure Parametric Policy</h3>
          
          <div style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 16px;">
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Select Crop</label>
              <select id="insCropSelect" class="btn btn-outline" style="background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; color: var(--text); border: 1px solid var(--border);">
                <option value="cotton" ${cropType === 'cotton' ? 'selected' : ''}>Cotton (कपास)</option>
                <option value="rice" ${cropType === 'rice' ? 'selected' : ''}>Paddy / Rice (धान)</option>
                <option value="groundnut" ${cropType === 'groundnut' ? 'selected' : ''}>Groundnut (मूंगफली)</option>
              </select>
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
                <span style="color: var(--text-muted);">Sum Insured (Coverage)</span>
                <span style="font-weight: 700; color: #ffffff;">₹<span id="sumInsuredVal">${sumInsured.toLocaleString()}</span></span>
              </div>
              <input type="range" id="insSumRange" min="20000" max="100000" step="5000" value="${sumInsured}" style="width: 100%; accent-color: var(--accent);">
            </div>

            <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border); padding: 12px; border-radius: 10px;">
              <h4 style="font-size: 12.5px; color: var(--accent); margin-bottom: 6px;">Trigger Thresholds:</h4>
              <ul style="font-size: 11.5px; color: #e5e7eb; padding-left: 16px; display: flex; flex-direction: column; gap: 4px;">
                <li>**Dry Spell:** Cumulative rainfall < 10mm for 20 consecutive days.</li>
                <li>**Excess Rain:** Single day precipitation > 120mm.</li>
              </ul>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 12px;">
              <div>
                <div style="font-size: 11px; color: var(--text-muted);">Policy Premium (2%)</div>
                <div style="font-size: 20px; font-weight: 800; color: #22c55e;">₹<span id="premiumVal">${premium.toLocaleString()}</span></div>
              </div>
              <button class="btn btn-accent" id="buyPolicyBtn" style="width: auto; padding: 10px 24px;">Activate Policy</button>
            </div>
          </div>
        </div>
      `;
    } else if (policyState === 'active') {
      contentHtml += `
        <!-- Active Policy Dashboard -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <h3 style="font-size: 16px; color: #ffffff;">Policy Status: <span style="color: #22c55e;">ACTIVE</span></h3>
            <span style="font-size: 11px; color: var(--text-muted);">No. KP-${txnId.slice(3,8)}</span>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;">
            <div style="background: rgba(255,255,255,0.02); padding: 10px; border-radius: 8px; border: 1px solid var(--border);">
              <span style="font-size: 11px; color: var(--text-muted); display: block;">Insured Crop</span>
              <strong style="font-size: 14px; color: #ffffff;">${cropType.toUpperCase()}</strong>
            </div>
            <div style="background: rgba(255,255,255,0.02); padding: 10px; border-radius: 8px; border: 1px solid var(--border);">
              <span style="font-size: 11px; color: var(--text-muted); display: block;">Coverage Amount</span>
              <strong style="font-size: 14px; color: #ffffff;">₹${sumInsured.toLocaleString()}</strong>
            </div>
          </div>

          <!-- Live Weather Stream -->
          <div style="background: rgba(0,0,0,0.15); padding: 12px; border-radius: 10px; margin-bottom: 16px; border: 1px solid rgba(245, 158, 11, 0.15);">
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px;">
              <span style="color: var(--accent); font-weight: 600;">📡 Live Weather Feed:</span>
              <span style="color: var(--text-muted);">Day ${simulatedDay}/20</span>
            </div>
            <p style="font-size: 12.5px; color: #e5e7eb; line-height: 1.4;">
              Rainfall has been **0mm** for the past **${simulatedDay} days**. Weather sensors suggest high risk of drought condition.
            </p>
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px;">
            <button class="btn btn-outline" id="insSimulateDayBtn" style="font-size: 13px;">Simulate Another Dry Day (+1 Day)</button>
            <button class="btn btn-accent" id="insSimulateTriggerBtn" style="font-size: 13px;">Simulate Extreme Dry Spell Trigger (Day 20)</button>
          </div>
        </div>
      `;
    } else if (policyState === 'payout') {
      contentHtml += `
        <!-- Payout Confirmed / Receipt -->
        <div class="glass-card" style="padding: 20px 16px; margin-bottom: 16px; border-color: rgba(34, 197, 94, 0.3); text-align: center;">
          <div style="width: 56px; height: 56px; background: rgba(34,197,94,0.15); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px auto; color: #22c55e; font-size: 28px;">✓</div>
          <h3 style="font-size: 18px; margin-bottom: 4px; color: #ffffff;">Auto-Claim Triggered!</h3>
          <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;">Sentinel-2 and OpenWeather verified crop drought stress.</p>

          <!-- UPI Receipt layout -->
          <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: left; max-width: 340px; margin: 0 auto 20px auto; font-family: monospace;">
            <div style="text-align: center; border-bottom: 1px dashed var(--border); padding-bottom: 10px; margin-bottom: 10px;">
              <span style="font-size: 11px; color: var(--text-muted); display: block;">UPI PAYOUT RECEIPT</span>
              <strong style="font-size: 18px; color: #22c55e;">₹${sumInsured.toLocaleString()}.00</strong>
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px; font-size: 11.5px; color: #e5e7eb;">
              <div style="display: flex; justify-content: space-between;">
                <span>Beneficiary:</span>
                <span>Farmer Account</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>Bank Partner:</span>
                <span>SBI / PMFBY Syndicate</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>Transaction ID:</span>
                <span>${txnId}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span>Status:</span>
                <span style="color: #22c55e; font-weight: bold;">SUCCESS</span>
              </div>
            </div>
          </div>

          <button class="btn btn-primary" id="insResetBtn">Configure New Policy</button>
        </div>
      `;
    }

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const sumRange = container.querySelector('#insSumRange');
    if (sumRange) {
      sumRange.addEventListener('input', (e) => {
        sumInsured = parseInt(e.target.value, 10);
        container.querySelector('#sumInsuredVal').textContent = sumInsured.toLocaleString();
        container.querySelector('#premiumVal').textContent = Math.round(sumInsured * 0.02).toLocaleString();
      });
    }

    const buyBtn = container.querySelector('#buyPolicyBtn');
    if (buyBtn) {
      buyBtn.addEventListener('click', async () => {
        cropType = container.querySelector('#insCropSelect').value;
        try {
          const status = await window.KisanAPI.getInsuranceStatus('default_farmer', cropType, 3.5);
          if (status && status.policy_number) {
            console.log('[Insurance] Live backend PMFBY policy:', status);
          }
        } catch (e) {
          console.warn('[Insurance] Backend API fallback:', e);
        }
        policyState = 'active';
        simulatedDay = 12;
        render(container);
      });
    }

    const simulateDayBtn = container.querySelector('#insSimulateDayBtn');
    if (simulateDayBtn) {
      simulateDayBtn.addEventListener('click', () => {
        if (simulatedDay < 20) {
          simulatedDay++;
        }
        if (simulatedDay === 20) {
          policyState = 'payout';
        }
        render(container);
      });
    }

    const simulateTriggerBtn = container.querySelector('#insSimulateTriggerBtn');
    if (simulateTriggerBtn) {
      simulateTriggerBtn.addEventListener('click', () => {
        policyState = 'payout';
        render(container);
      });
    }

    const resetBtn = container.querySelector('#insResetBtn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        policyState = 'setup';
        txnId = 'TXN' + Math.floor(Math.random() * 90000000 + 10000000);
        render(container);
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/insurance', render);
  }
})();
