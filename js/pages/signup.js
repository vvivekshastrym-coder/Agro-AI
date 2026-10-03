// KisanAI Sign Up Page Renderer
(function() {
  function render(container) {
    let contentHtml = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; margin-bottom: 4px; color: #ffffff;">🌾 Create Account</h1>
        <p style="font-size: 13.5px; color: var(--text-muted);">Join 600 Million Indian Farmers on KisanAI.</p>
      </div>

      <div class="glass-card" style="padding: 18px; margin-bottom: 24px;">
        <form id="signupForm" style="display: flex; flex-direction: column; gap: 12px;">
          <!-- Section 1: Farmer Details -->
          <h3 style="font-size: 14px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-bottom: 4px;">1. Personal Info</h3>
          <div>
            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Full Name</label>
            <input type="text" id="signName" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. Ramesh Patil" required>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Phone Number</label>
              <input type="tel" id="signPhone" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="9876543210" required>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Email (Optional)</label>
              <input type="email" id="signEmail" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="name@domain.com">
            </div>
          </div>

          <!-- Section 2: Farm Details -->
          <h3 style="font-size: 14px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-bottom: 4px; margin-top: 8px;">2. Farm Details</h3>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Village</label>
              <input type="text" id="signVillage" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. Mandya" required>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">District</label>
              <input type="text" id="signDistrict" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. Mandya" required>
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">State</label>
              <input type="text" id="signState" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="e.g. Karnataka" required>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">PIN Code</label>
              <input type="text" id="signPin" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="571401" required>
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Farm Size (Acres)</label>
              <input type="number" id="signAcreage" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="5" required>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Primary Crop</label>
              <select id="signCrop" class="btn btn-outline" style="background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px; color: var(--text); border: 1px solid var(--border);">
                <option value="wheat">Wheat (गेहूं)</option>
                <option value="rice">Rice/Paddy (धान)</option>
                <option value="cotton">Cotton (कपास)</option>
                <option value="sugarcane">Sugarcane (गन्ना)</option>
              </select>
            </div>
          </div>

          <!-- Section 3: Credentials -->
          <h3 style="font-size: 14px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-bottom: 4px; margin-top: 8px;">3. Password</h3>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Password</label>
              <input type="password" id="signPwd" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="••••••••" required>
            </div>
            <div>
              <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 2px;">Confirm Password</label>
              <input type="password" id="signConfirmPwd" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); padding: 8px 12px; font-size: 13px;" placeholder="••••••••" required>
            </div>
          </div>

          <button type="submit" class="btn btn-accent" style="margin-top: 12px;">Create Account</button>
        </form>

        <div style="text-align: center; font-size: 12.5px; border-top: 1px solid var(--border); padding-top: 14px; margin-top: 14px;">
          <span style="color: var(--text-muted);">Already have an account?</span>
          <a href="#/login" style="color: var(--accent); font-weight: bold; margin-left: 4px;">Sign In</a>
        </div>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const form = container.querySelector('#signupForm');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const pwd = container.querySelector('#signPwd').value;
        const confPwd = container.querySelector('#signConfirmPwd').value;

        if (pwd !== confPwd) {
          alert("Passwords do not match!");
          return;
        }

        // Store farmer metadata for profile screen
        const farmerProfile = {
          name: container.querySelector('#signName').value,
          phone: container.querySelector('#signPhone').value,
          email: container.querySelector('#signEmail').value || 'N/A',
          village: container.querySelector('#signVillage').value,
          district: container.querySelector('#signDistrict').value,
          state: container.querySelector('#signState').value,
          pincode: container.querySelector('#signPin').value,
          acreage: container.querySelector('#signAcreage').value,
          crop: container.querySelector('#signCrop').value
        };

        localStorage.setItem('kisanFarmerProfile', JSON.stringify(farmerProfile));
        localStorage.setItem('kisanAuth', 'true');
        window.location.hash = '#/otp';
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/signup', render);
  }
})();
