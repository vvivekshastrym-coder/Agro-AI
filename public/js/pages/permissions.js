// KisanAI Permissions Screen Page Renderer
(function() {
  const permList = [
    {
      id: "camera",
      icon: "📷",
      title: "Camera Access",
      desc: "Used by AI Crop Doctor to capture leaf photos and diagnose diseases instantly."
    },
    {
      id: "location",
      icon: "📍",
      title: "Location Services",
      desc: "Used to fetch hyperlocal village-level weather forecasts and calculate distance to nearest mandis."
    },
    {
      id: "mic",
      icon: "🎙️",
      title: "Microphone",
      desc: "Required for voice input so you can speak to Kisan GPT in your native dialect."
    },
    {
      id: "notif",
      icon: "🔔",
      title: "Push Notifications",
      desc: "Used for emergency pest alerts, rainfall warnings, and auto-insurance claim updates."
    },
    {
      id: "satellite",
      icon: "🛰️",
      title: "Satellite Integration",
      desc: "Allows coordinates lookup to compile your Sentinel-2 NDVI vegetative index timeline."
    }
  ];

  function render(container) {
    let contentHtml = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; margin-bottom: 4px; color: #ffffff;">🔒 App Permissions</h1>
        <p style="font-size: 13.5px; color: var(--text-muted);">Please grant permission access to unlock full AI functionality.</p>
      </div>

      <!-- Permissions list -->
      <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; max-height: 360px; overflow-y: auto; padding-right: 4px;">
        ${permList.map(perm => `
          <div class="glass-card" style="padding: 14px; display: flex; align-items: flex-start; gap: 12px; margin-bottom: 0;">
            <div style="font-size: 24px; background: rgba(255,255,255,0.03); width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid var(--border); flex-shrink: 0;">
              ${perm.icon}
            </div>
            <div>
              <h4 style="font-size: 14px; color: #ffffff; font-weight: bold; margin-bottom: 2px;">${perm.title}</h4>
              <p style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">${perm.desc}</p>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Action buttons -->
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <button class="btn btn-primary" id="permAllowBtn">Grant All & Continue</button>
        <button class="btn btn-outline" id="permSkipBtn" style="border-color: rgba(255,255,255,0.1); color: var(--text-muted);">Skip for Now</button>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const allowBtn = container.querySelector('#permAllowBtn');
    if (allowBtn) {
      allowBtn.addEventListener('click', () => {
        alert("All permissions granted! Welcome to KisanAI.");
        localStorage.setItem('kisanPermissions', 'granted');
        window.location.hash = '#/';
      });
    }

    const skipBtn = container.querySelector('#permSkipBtn');
    if (skipBtn) {
      skipBtn.addEventListener('click', () => {
        localStorage.setItem('kisanPermissions', 'skipped');
        window.location.hash = '#/';
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/permissions', render);
  }
})();
