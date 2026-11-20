// KisanAI Soil DNA Lab Page Renderer
(function() {
  let orderState = 'idle'; // 'idle', 'ordered', 'report'
  let formData = { name: '', phone: '', address: '', pincode: '' };
  let trackingStep = 0; // 0: Order Placed, 1: Kit Shipped, 2: Sample Received, 3: Lab Analysis, 4: Report Generated
  let soilApiData = null; // Live soil report from backend API

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/more" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← ${t('back')}</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">🧪 Soil DNA Lab</h1>
      </div>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
        Soil microbiome DNA sequencing by post. Get a scientific soil health map and save up to 40% on fertilizer costs.
      </p>
    `;

    if (orderState === 'idle') {
      contentHtml += `
        <!-- Order Form Card -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <h3 style="font-size: 16px; margin-bottom: 12px; color: var(--accent);">Order Soil DNA Test Kit</h3>
          <p style="font-size: 12.5px; color: #e5e7eb; margin-bottom: 16px; line-height: 1.4;">
            Order our simple soil collection kit for **₹99** only (includes return postage). Scoop soil from 5 points on your farm, post it back, and get your DNA report.
          </p>

          <form id="soilOrderForm" style="display: flex; flex-direction: column; gap: 12px;">
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Full Name</label>
              <input type="text" id="soilName" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. Ramesh Kumar" required>
            </div>
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Phone Number</label>
              <input type="tel" id="soilPhone" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. 9876543210" required>
            </div>
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Delivery Address</label>
              <textarea id="soilAddress" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; min-height: 60px; resize: none;" placeholder="House No, Village, Post Office, District" required></textarea>
            </div>
            <div>
              <label style="font-size: 11.5px; color: var(--text-muted); display: block; margin-bottom: 4px;">Pincode</label>
              <input type="text" id="soilPincode" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. 302001" required>
            </div>

            <button type="submit" class="btn btn-primary" style="margin-top: 8px;">Order Kit (Pay ₹99 on Delivery)</button>
          </form>
        </div>

        <!-- Or Show Sample Report directly button -->
        <div style="text-align: center; margin-bottom: 16px;">
          <button class="btn btn-outline" id="viewSampleReportBtn" style="font-size: 13px; width: auto; padding: 8px 20px;">
            🔬 View Demo DNA Report
          </button>
        </div>
      `;
    } else if (orderState === 'ordered') {
      contentHtml += `
        <!-- Tracking order card -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <h3 style="font-size: 16px; color: var(--accent); margin: 0;">Order Status</h3>
            <span style="font-size: 11px; background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 8px; border-radius: 99px; font-weight: 600;">Active Order</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px; position: relative; padding-left: 20px; border-left: 2px solid var(--border);">
            ${renderTrackingSteps()}
          </div>

          <div style="display: flex; gap: 8px;">
            <button class="btn btn-outline" id="soilSimulateProgressBtn" style="font-size: 12.5px;">Simulate Delivery/Analysis</button>
            ${trackingStep === 4 ? `
              <button class="btn btn-accent" id="soilViewReportBtn" style="font-size: 12.5px;">View DNA Report</button>
            ` : ''}
          </div>
        </div>
      `;
    } else if (orderState === 'report') {
      contentHtml += `
        <!-- Soil DNA Report Card -->
        <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 style="font-size: 17px; color: #ffffff;">Genomic Analysis Report</h3>
            <button class="btn btn-outline" id="soilReportBackBtn" style="width: auto; padding: 4px 10px; min-height: unset; font-size: 11px;">Reset</button>
          </div>

          <div style="display: flex; align-items: center; gap: 12px; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); padding: 12px; border-radius: 12px; margin-bottom: 16px;">
            <div style="font-size: 24px; font-weight: 800; color: #22c55e; background: rgba(34,197,94,0.15); width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">78</div>
            <div>
              <h4 style="font-size: 14px; color: #ffffff; font-weight: bold;">Soil Biodiversity Score: Good</h4>
              <p style="font-size: 11.5px; color: var(--text-muted);">Rich microbiome, average fungal network.</p>
            </div>
          </div>

          ${soilApiData && soilApiData.metrics ? `
            <div class="glass-card" style="padding: 12px; margin-bottom: 16px; background: rgba(0,0,0,0.2); border-color: rgba(34,197,94,0.2);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 11px; font-weight: 800; color: var(--accent);">🔬 LAB TEST CARD (SAMPLE #${soilApiData.sample_id})</span>
                <span style="font-size: 10px; color: var(--text-muted);">${soilApiData.metadata?.lab || 'ICAR-KVK Soil Lab'}</span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; font-size: 11.5px;">
                <div style="background: var(--surface-2); padding: 8px; border-radius: 6px;">
                  <span style="font-size: 10px; color: var(--text-muted); display: block;">Soil pH</span>
                  <strong style="color: ${soilApiData.metrics.ph.color};">${soilApiData.metrics.ph.value}</strong> (${soilApiData.metrics.ph.status.split(' ')[0]})
                </div>
                <div style="background: var(--surface-2); padding: 8px; border-radius: 6px;">
                  <span style="font-size: 10px; color: var(--text-muted); display: block;">Nitrogen (N)</span>
                  <strong style="color: ${soilApiData.metrics.nitrogen_kg_ha.color};">${soilApiData.metrics.nitrogen_kg_ha.value} kg/ha</strong>
                </div>
                <div style="background: var(--surface-2); padding: 8px; border-radius: 6px;">
                  <span style="font-size: 10px; color: var(--text-muted); display: block;">Phosphorus (P)</span>
                  <strong style="color: ${soilApiData.metrics.phosphorus_kg_ha.color};">${soilApiData.metrics.phosphorus_kg_ha.value} kg/ha</strong>
                </div>
              </div>
            </div>
          ` : ''}

          <!-- Bacteria breakdown -->
          <div style="margin-bottom: 16px;">
            <h4 style="font-size: 13px; color: var(--accent); margin-bottom: 6px;">Beneficial Bacteria Levels</h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px;">
                  <span>Rhizobium (Nitrogen Fixer)</span>
                  <span style="color: #22c55e; font-weight: 600;">High (Optimal)</span>
                </div>
                <div style="background: rgba(255,255,255,0.05); height: 6px; border-radius: 3px; overflow: hidden;">
                  <div style="background: #22c55e; width: 85%; height: 100%;"></div>
                </div>
              </div>
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px;">
                  <span>Azotobacter (Bio-fertilizer)</span>
                  <span style="color: var(--accent); font-weight: 600;">Medium (Needs boost)</span>
                </div>
                <div style="background: rgba(255,255,255,0.05); height: 6px; border-radius: 3px; overflow: hidden;">
                  <div style="background: var(--accent); width: 50%; height: 100%;"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Fungal network -->
          <div style="margin-bottom: 16px; border-top: 1px solid var(--border); padding-top: 12px;">
            <h4 style="font-size: 13px; color: var(--accent); margin-bottom: 6px;">Mycorrhizae (Fungal Networks)</h4>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 2px;">
              <span>Glomus Fungal Network</span>
              <span style="color: #ef4444; font-weight: 600;">Low (Deficient)</span>
            </div>
            <div style="background: rgba(255,255,255,0.05); height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 4px;">
              <div style="background: #ef4444; width: 22%; height: 100%;"></div>
            </div>
            <p style="font-size: 11px; color: var(--text-muted); line-height: 1.3;">
              Low mycorrhizal count limits Phosphorus absorption from the soil. Adding chemical phosphate won't help unless biology is restored.
            </p>
          </div>

          <!-- Pathogen risk -->
          <div style="margin-bottom: 16px; border-top: 1px solid var(--border); padding-top: 12px;">
            <h4 style="font-size: 13px; color: #ef4444; margin-bottom: 4px;">Pathogen Risk Indicator</h4>
            <div style="display: flex; justify-content: space-between; font-size: 12px;">
              <span>Fusarium Fungal Spores</span>
              <span style="color: var(--accent); font-weight: 600;">Moderate Risk (3.2%)</span>
            </div>
          </div>

          <!-- Prescriptions -->
          <div style="border-top: 1px solid var(--border); padding-top: 14px; background: rgba(245,158,11,0.05); border: 1px dashed rgba(245,158,11,0.3); padding: 12px; border-radius: 12px;">
            <h4 style="font-size: 13.5px; color: var(--accent); margin-bottom: 6px; display: flex; align-items: center; gap: 4px;">🌱 Custom Bio-Prescription</h4>
            <ul style="font-size: 12px; color: #e5e7eb; padding-left: 16px; line-height: 1.5; display: flex; flex-direction: column; gap: 4px;">
              <li>Apply **VAM (Vesicular Arbuscular Mycorrhizae)** inoculum @ 4 kg per acre during soil prep.</li>
              <li>Spray **Azotobacter liquid formulation** with irrigation water to increase biological nitrogen.</li>
              <li>**Savings Impact:** You can safely reduce chemical Urea by **40%** and DAP by **30%** this season. Estimated savings: **₹1,800 - ₹2,500 per acre**.</li>
            </ul>
          </div>
        </div>
      `;
    }

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function renderTrackingSteps() {
    const steps = [
      { title: "Order Placed", desc: "₹99 Cash on Delivery order received" },
      { title: "Kit Dispatched", desc: "Dispatched via India Post Speed Post" },
      { title: "Sample Collected", desc: "Courier has picked up your soil sample" },
      { title: "DNA Sequencing", desc: "Sequencing bacterial & fungal genes at our lab" },
      { title: "Report Generated", desc: "DNA analysis report ready to view" }
    ];

    return steps.map((step, idx) => {
      let iconColor = 'var(--border)';
      let textColor = 'var(--text-muted)';
      let dotColor = '#2d6e3f';

      if (idx < trackingStep) {
        iconColor = '#22c55e';
        textColor = '#e5e7eb';
        dotColor = '#22c55e';
      } else if (idx === trackingStep) {
        iconColor = 'var(--accent)';
        textColor = '#ffffff';
        dotColor = 'var(--accent)';
      }

      return `
        <div style="position: relative;">
          <!-- Node Indicator -->
          <div style="position: absolute; left: -26px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: ${dotColor}; border: 2px solid var(--bg); z-index: 2;"></div>
          
          <h4 style="font-size: 13.5px; color: ${textColor}; font-weight: 700; margin-bottom: 2px;">${step.title}</h4>
          <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.3;">${step.desc}</p>
        </div>
      `;
    }).join('');
  }

  function attachListeners(container) {
    const form = container.querySelector('#soilOrderForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        formData.name = container.querySelector('#soilName').value;
        formData.phone = container.querySelector('#soilPhone').value;
        formData.address = container.querySelector('#soilAddress').value;
        formData.pincode = container.querySelector('#soilPincode').value;
        
        orderState = 'ordered';
        trackingStep = 1; // Mark kit shipped immediately
        render(container);
      });
    }

    const viewSampleBtn = container.querySelector('#viewSampleReportBtn');
    if (viewSampleBtn) {
      viewSampleBtn.addEventListener('click', async () => {
        try {
          soilApiData = await window.KisanAPI.getSoilReport('default_farmer', 'Tomato');
        } catch (e) {
          console.warn('[SoilDNA] Backend API fallback:', e);
        }
        orderState = 'report';
        render(container);
      });
    }

    const simulateProgressBtn = container.querySelector('#soilSimulateProgressBtn');
    if (simulateProgressBtn) {
      simulateProgressBtn.addEventListener('click', () => {
        if (trackingStep < 4) {
          trackingStep++;
        } else {
          trackingStep = 0; // reset
        }
        render(container);
      });
    }

    const viewReportBtn = container.querySelector('#soilViewReportBtn');
    if (viewReportBtn) {
      viewReportBtn.addEventListener('click', async () => {
        try {
          soilApiData = await window.KisanAPI.getSoilReport('default_farmer', 'Tomato');
        } catch (e) {
          console.warn('[SoilDNA] Backend API fallback:', e);
        }
        orderState = 'report';
        render(container);
      });
    }

    const reportBackBtn = container.querySelector('#soilReportBackBtn');
    if (reportBackBtn) {
      reportBackBtn.addEventListener('click', () => {
        orderState = 'idle';
        trackingStep = 0;
        render(container);
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/soil-dna', render);
  }
})();
