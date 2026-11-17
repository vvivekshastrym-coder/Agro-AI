// Agro AI — web vs app feature access (client side).
// UI convenience only: the backend enforces app-only APIs (backend/app/auth/feature_access.py).
// Platform is detected from the Capacitor native runtime, never from screen width.
(function () {
  'use strict';

  const isNativeApp = Boolean(
    (window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function' && window.Capacitor.isNativePlatform()) ||
    window.location.protocol === 'capacitor:'
  );

  // mode: full | basic | limited | preview | information | redirect | blocked
  const FEATURE_ACCESS = {
    agroGPT:          { web: 'basic',       app: 'full' },
    cropDiagnosis:    { web: 'limited',     app: 'full' },
    weather:          { web: 'full',        app: 'full' },
    mandi:            { web: 'full',        app: 'full' },
    googleMaps:       { web: 'blocked',     app: 'full' },
    logisticsBooking: { web: 'redirect',    app: 'full' },
    liveTracking:     { web: 'blocked',     app: 'full' },
    digitalTwin:      { web: 'preview',     app: 'full' },
    droneOperations:  { web: 'information', app: 'full' }
  };

  // App views that need the mobile app on the web (view id -> feature + copy)
  const APP_ONLY_VIEWS = {
    logistics: {
      feature: 'logisticsBooking',
      title: 'Vehicle booking & live tracking',
      bullets: ['Book vehicles and manage drivers', 'Live goods and vehicle tracking on a map', 'Real-time delivery notifications']
    }
  };

  function accessFor(feature) {
    const f = FEATURE_ACCESS[feature];
    return f ? (isNativeApp ? f.app : f.web) : 'blocked';
  }

  function needsApp(view) {
    const v = APP_ONLY_VIEWS[view];
    if (!v || isNativeApp) return null;
    const mode = accessFor(v.feature);
    return (mode === 'redirect' || mode === 'blocked') ? v : null;
  }

  function showAppUpgrade(view) {
    const v = APP_ONLY_VIEWS[view];
    const host = document.getElementById('appOnlyBody');
    if (!v || !host) return;
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    host.innerHTML =
      '<div style="text-align:center;font-size:44px;">📱</div>' +
      '<h2 class="display" style="text-align:center;margin:8px 0 6px;">Unlock the full Agro AI experience</h2>' +
      '<p class="muted" style="text-align:center;margin:0 0 16px;">' + esc(v.title) + ' is available in the Agro AI mobile app.</p>' +
      '<ul style="margin:0 0 18px;padding-left:20px;line-height:1.8;">' +
        v.bullets.map((b) => '<li>' + esc(b) + '</li>').join('') + '</ul>' +
      '<button class="btn btn-primary btn-block" disabled>Download Agro AI App</button>' +
      '<p class="muted" style="text-align:center;font-size:12.5px;margin-top:10px;">Available on Google Play when published.</p>' +
      '<button class="btn btn-outline btn-block" style="margin-top:14px;" onclick="go(\'home\')">Back to Home</button>';
  }

  window.AgroFeatureAccess = { isNativeApp, FEATURE_ACCESS, accessFor, needsApp, showAppUpgrade };
})();
