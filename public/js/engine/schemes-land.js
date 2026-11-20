// Agro AI — Government Schemes, My Land & FRUITS, Applications & Official Portals
(function () {
  'use strict';

  function authHeaders() {
    const token = localStorage.getItem('agro_access_token') || localStorage.getItem('sb-access-token') || '';
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }

  function switchTab(tab) {
    document.querySelectorAll('.scheme-tab-btn').forEach((b) => {
      const active = b.dataset.tab === tab;
      b.classList.toggle('btn-primary', active);
      b.classList.toggle('btn-outline', !active);
    });
    document.querySelectorAll('.scheme-tab-pane').forEach((p) => {
      p.style.display = p.dataset.pane === tab ? 'block' : 'none';
    });
    if (tab === 'myland') loadMyLand();
    if (tab === 'apps') loadMyApplications();
    if (tab === 'portals') loadOfficialPortals();
  }

  async function loadMyLand() {
    const listEl = document.getElementById('myLandParcelsList');
    if (!listEl) return;
    try {
      const res = await fetch('/api/schemes/land', { headers: authHeaders() });
      const data = await res.json();
      const parcels = data.parcels || [];
      if (!parcels.length) {
        listEl.innerHTML = '<div class="card"><p class="muted" style="margin:0;">No land parcels saved yet. Add your farm parcel below.</p></div>';
        return;
      }
      listEl.innerHTML = parcels.map((p) =>
        '<div class="card" style="margin-bottom:10px;">' +
        '  <div style="display:flex;justify-content:space-between;align-items:center;">' +
        '    <strong>' + esc(p.district) + (p.taluk ? ', ' + esc(p.taluk) : '') + ' (' + esc(p.state) + ')</strong>' +
        '    <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;border-color:var(--danger);color:var(--danger);" onclick="AgroSchemesLand.deleteParcel(\'' + esc(p.id) + '\')">Delete</button>' +
        '  </div>' +
        '  <div class="muted" style="font-size:12.5px;margin-top:4px;">' +
        '    Area: ' + esc(p.total_acres) + ' ac · Crop: ' + esc(p.current_crop || '—') + ' (' + esc(p.crop_season || 'Kharif') + ') · Irrigation: ' + esc(p.irrigation_source) +
        (p.fruits_id ? ' · FRUITS ID: <strong>' + esc(p.fruits_id) + '</strong>' : '') +
        (p.survey_number ? ' · Survey: ' + esc(p.survey_number) : '') +
        '  </div>' +
        '</div>'
      ).join('');
    } catch (e) {
      listEl.innerHTML = '<div class="card"><p class="muted">Could not load land parcels. Sign in to save parcels.</p></div>';
    }
  }

  async function saveParcel(e) {
    if (e) e.preventDefault();
    const payload = {
      fruits_id: (document.getElementById('landFruitsId')?.value || '').trim() || null,
      state: document.getElementById('landState')?.value || 'Karnataka',
      district: (document.getElementById('landDistrict')?.value || '').trim(),
      taluk: (document.getElementById('landTaluk')?.value || '').trim() || null,
      village: (document.getElementById('landVillage')?.value || '').trim() || null,
      survey_number: (document.getElementById('landSurveyNo')?.value || '').trim() || null,
      total_acres: parseFloat(document.getElementById('landTotalAcres')?.value || '0') || 0,
      cultivable_acres: parseFloat(document.getElementById('landTotalAcres')?.value || '0') || 0,
      ownership_type: document.getElementById('landOwnership')?.value || 'owner',
      irrigation_source: document.getElementById('landIrrigation')?.value || 'rainfed',
      current_crop: (document.getElementById('landCrop')?.value || '').trim() || null,
      crop_season: document.getElementById('landSeason')?.value || 'Kharif',
    };
    if (!payload.district) {
      if (typeof window.showToast === 'function') window.showToast('Enter your district');
      return;
    }
    const res = await fetch('/api/schemes/land', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      if (typeof window.showToast === 'function') window.showToast('Land parcel saved to your Agro AI profile');
      loadMyLand();
    } else if (typeof window.showToast === 'function') {
      window.showToast('Sign in required to save land parcels');
    }
  }

  async function deleteParcel(id) {
    const res = await fetch('/api/schemes/land/' + encodeURIComponent(id), { method: 'DELETE', headers: authHeaders() });
    if (res.ok) loadMyLand();
  }

  async function loadMyApplications() {
    const el = document.getElementById('myApplicationsList');
    if (!el) return;
    try {
      const res = await fetch('/api/schemes/applications', { headers: authHeaders() });
      const data = await res.json();
      const apps = data.applications || [];
      if (!apps.length) {
        el.innerHTML = '<div class="card"><p class="muted" style="margin:0;">No saved applications yet. Add an application below to track documents and follow-up dates.</p></div>';
        return;
      }
      el.innerHTML = apps.map((a) =>
        '<div class="card" style="margin-bottom:10px;">' +
        '  <div style="font-weight:700;">' + esc(a.scheme_title) + '</div>' +
        '  <div class="muted" style="font-size:12.5px;">Status: <strong>' + esc(a.status) + '</strong> (' + esc(a.status_source) + ')' +
        (a.application_ref ? ' · Ref: ' + esc(a.application_ref) : '') + '</div>' +
        (a.official_portal_url ? '  <div style="margin-top:6px;"><a href="' + esc(a.official_portal_url) + '" target="_blank" rel="noopener">Open Official Portal ↗</a></div>' : '') +
        '</div>'
      ).join('');
    } catch (e) {
      el.innerHTML = '<div class="card"><p class="muted">Sign in to view your tracked applications.</p></div>';
    }
  }

  async function saveApplication(e) {
    if (e) e.preventDefault();
    const title = (document.getElementById('appSchemeTitle')?.value || '').trim();
    if (!title) return;
    const payload = {
      scheme_slug: title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 60) || 'custom-scheme',
      scheme_title: title,
      application_ref: (document.getElementById('appRefNo')?.value || '').trim() || null,
      status: document.getElementById('appStatusSel')?.value || 'preparing_documents',
      official_portal_url: (document.getElementById('appPortalUrl')?.value || '').trim() || null,
    };
    const res = await fetch('/api/schemes/applications', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      if (typeof window.showToast === 'function') window.showToast('Application tracker updated');
      loadMyApplications();
    }
  }

  async function loadOfficialPortals() {
    const el = document.getElementById('officialPortalsList');
    if (!el) return;
    try {
      const res = await fetch('/api/schemes/directory');
      const data = await res.json();
      el.innerHTML =
        '<div class="card" style="margin-bottom:12px;background:#FFFDF6;border-color:#E5DFCF;font-size:12.5px;">' +
        esc(data.official_record_notice) + '</div>' +
        (data.portals || []).map((p) =>
          '<div class="card" style="margin-bottom:10px;">' +
          '  <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">' +
          '    <strong>' + esc(p.name) + '</strong>' +
          '    <span class="pill pill-forest">' + esc(p.scope) + '</span>' +
          '  </div>' +
          '  <p class="muted" style="font-size:12.5px;margin:6px 0;">' + esc(p.purpose) + '</p>' +
          '  <a href="' + esc(p.url) + '" target="_blank" rel="noopener" style="font-weight:600;color:var(--forest);">Visit Official Portal ↗</a>' +
          '</div>'
        ).join('');
    } catch (e) {
      el.innerHTML = '<div class="card"><p class="muted">Could not load official portals.</p></div>';
    }
  }

  window.AgroSchemesLand = { switchTab, loadMyLand, saveParcel, deleteParcel, loadMyApplications, saveApplication, loadOfficialPortals };
})();
