// KisanAI Settings Screen Page Renderer
(function() {
  let offlineMode = localStorage.getItem('kisanOfflineMode') === 'true';
  let pushNotif = true;

  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;

    let contentHtml = `
      <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
        <a href="#/profile" class="btn btn-outline" style="width: auto; padding: 6px 12px; min-height: unset; font-size: 13px;">← Back</a>
        <h1 style="font-size: 22px; margin-bottom: 0;">⚙️ Settings</h1>
      </div>

      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 15px; color: var(--accent); margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 4px;">Preferences</h3>
        
        <!-- Toggle Notifications -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; font-size: 13px;">
          <div>
            <span style="display: block; font-weight: 600; color: #ffffff;">Push Notifications</span>
            <span style="font-size: 11px; color: var(--text-muted);">Pest outbreaks & weather warnings</span>
          </div>
          <input type="checkbox" id="setNotifToggle" ${pushNotif ? 'checked' : ''} style="width: 20px; height: 20px; accent-color: var(--accent); cursor: pointer;">
        </div>

        <!-- Toggle Offline Mode -->
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <div>
            <span style="display: block; font-weight: 600; color: #ffffff;">Offline Cache Mode</span>
            <span style="font-size: 11px; color: var(--text-muted);">Store local database for offline usage</span>
          </div>
          <input type="checkbox" id="setOfflineToggle" ${offlineMode ? 'checked' : ''} style="width: 20px; height: 20px; accent-color: var(--accent); cursor: pointer;">
        </div>
      </div>

      <div class="glass-card" style="padding: 16px; margin-bottom: 16px;">
        <h3 style="font-size: 15px; color: var(--accent); margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 4px;">Security & System</h3>
        
        <div style="display: flex; flex-direction: column; gap: 12px; font-size: 13px;">
          <a href="#/language" style="display: flex; justify-content: space-between; color: #ffffff;">
            <span>App Language</span>
            <span style="color: var(--accent);">Change Language 🌐</span>
          </a>
          <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 8px;">
            <span>Biometric Setup</span>
            <span style="color: var(--text-muted);">Enabled (Fingerprint / Face ID)</span>
          </div>
          <div style="display: flex; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 8px;">
            <span>Version</span>
            <span style="color: var(--text-muted);">v1.0 (June 2026 Build)</span>
          </div>
        </div>
      </div>

      <div class="glass-card" style="padding: 16px; margin-bottom: 16px; text-align: center; border-color: rgba(245, 158, 11, 0.2);">
        <h4 style="font-size: 13px; color: var(--accent); margin-bottom: 4px;">🌾 KisanAI India Mission</h4>
        <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
          Developed with support from PM-KISAN, NABARD, and the Bhashini Translation API to make AI accessible to 600 million farmers.
        </p>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const notifToggle = container.querySelector('#setNotifToggle');
    if (notifToggle) {
      notifToggle.addEventListener('change', (e) => {
        pushNotif = e.target.checked;
        alert(pushNotif ? "Push notifications enabled." : "Push notifications disabled.");
      });
    }

    const offlineToggle = container.querySelector('#setOfflineToggle');
    if (offlineToggle) {
      offlineToggle.addEventListener('change', (e) => {
        offlineMode = e.target.checked;
        localStorage.setItem('kisanOfflineMode', offlineMode ? 'true' : 'false');
        alert(offlineMode ? "Offline Mode active! Disease patterns and weather cached locally." : "Offline Mode disabled.");
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/settings', render);
  }
})();
