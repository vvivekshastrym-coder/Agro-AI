// Agro AI — Privacy, Cookie Consent, Age Verification & Parental Consent UI
// Session replay is permanently disabled across all environments.
(function () {
  'use strict';

  try {
    Object.defineProperty(window, '__AGRO_SESSION_REPLAY_ENABLED__', {
      value: false,
      writable: false,
      configurable: false,
    });
  } catch (e) {
    window.__AGRO_SESSION_REPLAY_ENABLED__ = false;
  }

  const STORAGE_KEY = 'agro_privacy_consent_v1';

  function authHeaders() {
    const token = localStorage.getItem('agro_access_token') || localStorage.getItem('sb-access-token') || '';
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  function showConsentBannerIfNeeded() {
    if (localStorage.getItem(STORAGE_KEY)) return;
    if (document.getElementById('agroPrivacyBanner')) return;

    const bar = document.createElement('div');
    bar.id = 'agroPrivacyBanner';
    bar.setAttribute('role', 'dialog');
    bar.setAttribute('aria-label', 'Privacy and cookie preferences');
    bar.style.cssText =
      'position:fixed;left:16px;right:16px;bottom:76px;max-width:680px;margin:0 auto;z-index:90;' +
      'background:#fff;border:1px solid #E5DFCF;border-radius:20px;padding:16px 18px;' +
      'box-shadow:0 10px 30px rgba(21,58,32,0.16);font-size:13px;line-height:1.5;color:#1F2A1F;';
    bar.innerHTML =
      '<div style="font-weight:700;color:#1F4D2B;margin-bottom:4px;">Privacy &amp; Cookie Preferences</div>' +
      '<div style="margin-bottom:12px;">Agro AI uses strictly necessary cookies for authentication and security. ' +
      'Optional analytics and marketing are <strong>off by default</strong>, and session replay is permanently disabled. ' +
      '<a href="/privacy" target="_blank" style="color:#1F4D2B;font-weight:600;">Privacy Policy</a> · ' +
      '<a href="/cookies" target="_blank" style="color:#1F4D2B;font-weight:600;">Cookie Policy</a></div>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
      '  <button type="button" class="btn btn-primary" style="padding:9px 14px;font-size:13px;" id="agroBtnEssentialOnly">Essential Only</button>' +
      '  <button type="button" class="btn btn-outline" style="padding:9px 14px;font-size:13px;" id="agroBtnManagePrivacy">Manage Preferences</button>' +
      '</div>';
    document.body.appendChild(bar);

    document.getElementById('agroBtnEssentialOnly').onclick = function () {
      savePrivacyConsent(false, false);
      bar.remove();
    };
    document.getElementById('agroBtnManagePrivacy').onclick = function () {
      bar.remove();
      openPrivacySettingsModal();
    };
  }

  async function savePrivacyConsent(analytics, marketing) {
    const prefs = { essential: true, analytics: !!analytics, marketing: !!marketing, ts: Date.now() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    try {
      await fetch('/api/privacy/consent', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ analytics: !!analytics, marketing: !!marketing }),
      });
    } catch (e) {}
    if (typeof window.showToast === 'function') {
      window.showToast('Privacy preferences saved');
    }
  }

  function openPrivacySettingsModal() {
    let saved = { essential: true, analytics: false, marketing: false };
    try { saved = Object.assign(saved, JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')); } catch (e) {}

    const wrap = document.createElement('div');
    wrap.id = 'agroPrivacyModal';
    wrap.style.cssText = 'position:fixed;inset:0;z-index:100;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;padding:16px;';
    wrap.innerHTML =
      '<div style="background:#fff;border-radius:22px;max-width:460px;width:100%;padding:22px;box-shadow:0 16px 40px rgba(0,0,0,0.22);">' +
      '  <h3 class="display" style="margin:0 0 8px;font-size:19px;color:#1F4D2B;">Privacy &amp; Cookie Settings</h3>' +
      '  <p style="font-size:12.5px;color:#5B665B;margin:0 0 14px;">Session replay, heatmaps, and keystroke recording are permanently disabled.</p>' +
      '  <label style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #EEE;">' +
      '    <span><strong>Essential</strong><br><small style="color:#666;">Auth &amp; security (always active)</small></span>' +
      '    <input type="checkbox" checked disabled>' +
      '  </label>' +
      '  <label style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid #EEE;">' +
      '    <span><strong>Analytics</strong><br><small style="color:#666;">Opt-in performance metrics (no IP storage)</small></span>' +
      '    <input type="checkbox" id="agroToggleAnalytics" ' + (saved.analytics ? 'checked' : '') + '>' +
      '  </label>' +
      '  <label style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;margin-bottom:14px;">' +
      '    <span><strong>Marketing</strong><br><small style="color:#666;">Product updates (withdrawable anytime)</small></span>' +
      '    <input type="checkbox" id="agroToggleMarketing" ' + (saved.marketing ? 'checked' : '') + '>' +
      '  </label>' +
      '  <div style="display:flex;gap:8px;">' +
      '    <button type="button" class="btn btn-outline" style="flex:1;" id="agroPrivacyRejectBtn">Reject Non-Essential</button>' +
      '    <button type="button" class="btn btn-primary" style="flex:1;" id="agroPrivacySaveBtn">Save Preferences</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(wrap);
    wrap.onclick = function (e) { if (e.target === wrap) wrap.remove(); };
    document.getElementById('agroPrivacyRejectBtn').onclick = function () {
      savePrivacyConsent(false, false);
      wrap.remove();
    };
    document.getElementById('agroPrivacySaveBtn').onclick = function () {
      const a = document.getElementById('agroToggleAnalytics').checked;
      const m = document.getElementById('agroToggleMarketing').checked;
      savePrivacyConsent(a, m);
      wrap.remove();
    };
  }

  function openAgeVerificationModal() {
    const wrap = document.createElement('div');
    wrap.id = 'agroAgeModal';
    wrap.style.cssText = 'position:fixed;inset:0;z-index:100;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;padding:16px;';
    wrap.innerHTML =
      '<div style="background:#fff;border-radius:22px;max-width:460px;width:100%;padding:22px;box-shadow:0 16px 40px rgba(0,0,0,0.22);">' +
      '  <h3 class="display" style="margin:0 0 6px;font-size:19px;color:#1F4D2B;">Age &amp; Parental Consent Verification</h3>' +
      '  <p style="font-size:12.5px;color:#5B665B;margin:0 0 12px;">Enter your date of birth and country. We never collect Aadhaar or identity documents.</p>' +
      '  <label style="display:block;font-size:12px;font-weight:600;margin-bottom:4px;">Date of Birth</label>' +
      '  <input type="date" id="agroDobInput" class="field-input" style="margin-bottom:10px;width:100%;">' +
      '  <label style="display:block;font-size:12px;font-weight:600;margin-bottom:4px;">Country</label>' +
      '  <select id="agroCountryInput" class="field-input" style="margin-bottom:12px;width:100%;">' +
      '    <option value="IN" selected>India (IN — under 18 requires parental consent)</option>' +
      '    <option value="US">United States (US)</option>' +
      '    <option value="GB">United Kingdom (GB)</option>' +
      '    <option value="DE">Germany (DE)</option>' +
      '    <option value="FR">France (FR)</option>' +
      '    <option value="CA">Canada (CA)</option>' +
      '    <option value="AU">Australia (AU)</option>' +
      '    <option value="SG">Singapore (SG)</option>' +
      '  </select>' +
      '  <div id="agroAgeResultBox" style="font-size:12.5px;margin-bottom:10px;"></div>' +
      '  <div id="agroParentSection" style="display:none;border-top:1px solid #EEE;padding-top:10px;margin-top:8px;">' +
      '    <div style="font-weight:700;font-size:13px;color:#B4432E;margin-bottom:6px;">Parental / Guardian Consent Required</div>' +
      '    <input type="text" id="agroParentContact" class="field-input" placeholder="Parent email or +91 phone" style="margin-bottom:8px;width:100%;">' +
      '    <button type="button" class="btn btn-outline btn-block" id="agroReqParentBtn" style="margin-bottom:8px;">Send Parent Verification Code</button>' +
      '    <div id="agroVerifyCodeBox" style="display:none;">' +
      '      <input type="text" id="agroParentCode" class="field-input" placeholder="6-digit parent code" style="margin-bottom:8px;width:100%;">' +
      '      <label style="display:flex;gap:8px;align-items:center;font-size:12px;margin-bottom:8px;">' +
      '        <input type="checkbox" id="agroParentConfirmChk"> I confirm I am the parent/legal guardian and consent to minimal advisory data processing.' +
      '      </label>' +
      '      <div style="display:flex;gap:8px;">' +
      '        <button type="button" class="btn btn-primary" style="flex:1;" id="agroParentApproveBtn">Approve</button>' +
      '        <button type="button" class="btn btn-outline" style="flex:1;" id="agroParentRejectBtn">Reject</button>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div style="display:flex;gap:8px;margin-top:12px;">' +
      '    <button type="button" class="btn btn-outline" style="flex:1;" id="agroAgeCloseBtn">Close</button>' +
      '    <button type="button" class="btn btn-primary" style="flex:1;" id="agroAgeSubmitBtn">Verify Age</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(wrap);

    let lastConsentId = null;
    document.getElementById('agroAgeCloseBtn').onclick = function () { wrap.remove(); };
    document.getElementById('agroAgeSubmitBtn').onclick = async function () {
      const dob = document.getElementById('agroDobInput').value;
      const cc = document.getElementById('agroCountryInput').value;
      const box = document.getElementById('agroAgeResultBox');
      if (!dob) { box.textContent = 'Please select your date of birth.'; return; }
      try {
        const res = await fetch('/api/auth/age-verify', {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ date_of_birth: dob, country_code: cc }),
        });
        const data = await res.json();
        if (!res.ok) { box.textContent = (data.detail && data.detail.error && data.detail.error.message) || 'Verification failed.'; return; }
        box.textContent = 'Category: ' + data.age_category + ' · Status: ' + data.account_status;
        document.getElementById('agroParentSection').style.display = data.requires_parental_consent ? 'block' : 'none';
      } catch (e) { box.textContent = 'Network error verifying age.'; }
    };

    document.getElementById('agroReqParentBtn').onclick = async function () {
      const contact = document.getElementById('agroParentContact').value.trim();
      const box = document.getElementById('agroAgeResultBox');
      const res = await fetch('/api/auth/parental-consent/request', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ parent_contact: contact }),
      });
      const data = await res.json();
      if (!res.ok) { box.textContent = 'Could not send consent request.'; return; }
      lastConsentId = data.consent_id;
      document.getElementById('agroVerifyCodeBox').style.display = 'block';
      box.textContent = 'Consent request created (' + data.consent_id + ').' + (data.dev_verification_code ? ' Dev code: ' + data.dev_verification_code : '');
    };

    async function submitParentDecision(decision) {
      const code = document.getElementById('agroParentCode').value.trim();
      const confirmed = document.getElementById('agroParentConfirmChk').checked;
      const box = document.getElementById('agroAgeResultBox');
      if (!lastConsentId) return;
      const res = await fetch('/api/auth/parental-consent/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consent_id: lastConsentId, verification_code: code, decision: decision, parent_confirmed_adult: confirmed }),
      });
      const data = await res.json();
      if (!res.ok) { box.textContent = (data.detail && data.detail.error && data.detail.error.message) || 'Verification failed.'; return; }
      box.textContent = 'Consent ' + data.status + ' · Child account: ' + data.child_account_status;
    }
    document.getElementById('agroParentApproveBtn').onclick = function () { submitParentDecision('approved'); };
    document.getElementById('agroParentRejectBtn').onclick = function () { submitParentDecision('rejected'); };
  }

  async function cancelSubscription() {
    const res = await fetch('/api/plans/cancel', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ immediate: false, reason: 'User cancelled via web portal' }),
    });
    const data = await res.json();
    if (typeof window.showToast === 'function') {
      window.showToast(res.ok ? (data.message || 'Subscription cancelled') : ((data.detail && data.detail.error && data.detail.error.message) || 'No active subscription'));
    }
    return data;
  }

  window.AgroPrivacy = {
    openPrivacySettingsModal,
    openAgeVerificationModal,
    savePrivacyConsent,
    cancelSubscription,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showConsentBannerIfNeeded);
  } else {
    showConsentBannerIfNeeded();
  }
})();
