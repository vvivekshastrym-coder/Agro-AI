// KisanAI Profile Screen Page Renderer
(function() {
  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    // Load custom farmer profile if exists
    let farmer = {
      name: 'Vivek',
      phone: '9876543210',
      email: 'vivek@agri.in',
      village: 'Mandya Village',
      district: 'Mandya',
      state: 'Karnataka',
      pincode: '571401',
      acreage: '5.4',
      crop: 'wheat'
    };

    const cached = localStorage.getItem('kisanFarmerProfile');
    if (cached) {
      try {
        farmer = JSON.parse(cached);
      } catch (e) {
        console.error(e);
      }
    }

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
        <h1 style="font-size: 24px; color: #ffffff; margin: 0;">👤 Profile</h1>
        <button class="btn btn-outline" id="profileSettingsBtn" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">⚙️ Settings</button>
      </div>

      <!-- Farmer details summary card -->
      <div class="glass-card" style="padding: 16px; display: flex; gap: 16px; align-items: center; margin-bottom: 16px;">
        <div style="font-size: 40px; background: var(--border); width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 2px solid var(--accent);">👨‍🌾</div>
        <div>
          <h3 style="font-size: 18px; color: #ffffff; font-weight: bold; margin-bottom: 2px;">${farmer.name}</h3>
          <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">📍 ${farmer.village}, ${farmer.district}</p>
          <span style="font-size: 11px; background: rgba(34,197,94,0.15); color: #22c55e; padding: 2px 8px; border-radius: 99px; font-weight: 600;">Verified Farmer</span>
        </div>
      </div>

      <!-- Farm stats -->
      <div class="grid-2" style="grid-template-columns: 1fr 1fr; margin-bottom: 16px; gap: 10px;">
        <div class="glass-card" style="padding: 12px; margin-bottom: 0; text-align: center;">
          <span style="font-size: 11px; color: var(--text-muted); display: block;">Farm Size</span>
          <strong style="font-size: 16px; color: #ffffff;">${farmer.acreage} Acres</strong>
        </div>
        <div class="glass-card" style="padding: 12px; margin-bottom: 0; text-align: center;">
          <span style="font-size: 11px; color: var(--text-muted); display: block;">Primary Crop</span>
          <strong style="font-size: 16px; color: var(--accent);">${farmer.crop.toUpperCase()}</strong>
        </div>
      </div>

      <!-- Achievements -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 15px; color: #ffffff; margin-bottom: 10px;">Achievements</h3>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <span style="font-size: 11px; background: rgba(34,197,94,0.15); color: #22c55e; padding: 4px 10px; border-radius: 12px; font-weight: bold;">🌱 Soil Protector</span>
          <span style="font-size: 11px; background: rgba(245,158,11,0.15); color: var(--accent); padding: 4px 10px; border-radius: 12px; font-weight: bold;">💧 Water Savior</span>
          <span style="font-size: 11px; background: rgba(59,130,246,0.15); color: #3b82f6; padding: 4px 10px; border-radius: 12px; font-weight: bold;">📈 Top Vendor</span>
        </div>
      </div>

      <!-- Crop history -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 15px; color: #ffffff; margin-bottom: 10px;">Crop Cycle History</h3>
        <div style="display: flex; flex-direction: column; gap: 10px;">
          <div style="display: flex; justify-content: space-between; font-size: 12.5px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">
            <span>Sugarcane (Kharif 2025)</span>
            <span style="color: #22c55e; font-weight: 600;">85 Tons (Sold)</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 12.5px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">
            <span>Rice / Paddy (Rabi 2024)</span>
            <span style="color: #22c55e; font-weight: 600;">45 Quintals (Sold)</span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 12.5px; padding-bottom: 4px;">
            <span>Cotton (Kharif 2024)</span>
            <span style="color: #22c55e; font-weight: 600;">32 Quintals (Sold)</span>
          </div>
        </div>
      </div>

      <!-- Controls -->
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <button class="btn btn-outline" id="profileDarkBtn">Toggle Dark Mode</button>
        <button class="btn btn-primary" id="profileLogoutBtn" style="background: transparent; border: 1px solid rgba(239,68,68,0.25); color: #ef4444;">Log Out</button>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const logoutBtn = container.querySelector('#profileLogoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('kisanAuth');
        window.location.hash = '#/login';
      });
    }

    const settingsBtn = container.querySelector('#profileSettingsBtn');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', () => {
        window.location.hash = '#/settings';
      });
    }

    const darkBtn = container.querySelector('#profileDarkBtn');
    if (darkBtn) {
      darkBtn.addEventListener('click', () => {
        const isDark = document.body.style.backgroundColor === 'rgb(11, 19, 14)';
        if (isDark) {
          // Switch to light green theme
          document.body.style.backgroundColor = '#f4f6f4';
          document.body.style.color = '#111827';
          alert("Switched to Light Mode!");
        } else {
          // Switch to default dark slate green
          document.body.style.backgroundColor = '#0b130e';
          document.body.style.color = '#f3f4f6';
          alert("Switched to Dark Mode!");
        }
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/profile', render);
  }
})();
