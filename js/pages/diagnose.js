// ═══════════════════════════════════════════════════════════
// AGRO AI — LEAF DIAGNOSIS v2.0
// Single Source of Truth Backend Integration
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let selectedFile = null;
  let imageDataUrl = null;
  let analysisState = 'idle'; // idle | analyzing | low_confidence | done | error
  let lastReport = null;
  let errorMessage = null;

  function render(container) {
    container.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 6px;">🔬 Leaf Diagnosis</h1>
        <p style="font-size: 13px; color: var(--text-muted);">Upload a clear photo of an affected leaf for instant AI analysis via Backend API</p>
      </div>

      <div id="diagContent">${renderContent()}</div>
    `;

    attachListeners(container);
  }

  function renderContent() {
    if (analysisState === 'idle') return renderIdle();
    if (analysisState === 'analyzing') return renderAnalyzing();
    if (analysisState === 'low_confidence') return renderLowConfidence();
    if (analysisState === 'done') return renderResult();
    if (analysisState === 'error') return renderError();
    return renderIdle();
  }

  function renderIdle() {
    return `
      <div class="glass-card" style="padding: 16px;">
        ${imageDataUrl ? `
          <div style="position: relative; border-radius: 16px; overflow: hidden; margin-bottom: 16px; border: 1px solid var(--border); max-height: 300px;">
            <img src="${imageDataUrl}" style="width: 100%; height: 100%; object-fit: cover; display: block;" alt="Crop leaf">
            <button id="removeImg" style="position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7); border: none; color: #fff; width: 32px; height: 32px; border-radius: 50%; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center;">✕</button>
          </div>
          <button class="btn btn-accent" id="analyzeBtn" style="width:100%; padding:14px; font-size:16px;">🔬 Analyze Leaf Image via Backend</button>
          <button class="btn btn-outline" id="retakeBtn" style="width:100%; margin-top: 8px;">📷 Select Different Photo</button>
        ` : `
          <div class="upload-zone" id="dropZone" style="padding: 30px 16px; text-align: center; border: 2px dashed var(--border); border-radius: 16px; background: var(--surface-1);">
            <div style="font-size: 48px; margin-bottom: 12px;">🍃</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 6px;">Upload Crop Leaf Photo</div>
            <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px;">Clear, well-lit close-up photo works best (JPG, PNG)</div>
            <input type="file" id="fileInput" accept="image/*" style="display:none;">
            <input type="file" id="cameraInput" accept="image/*" capture="environment" style="display:none;">
            <div style="display: flex; gap: 10px; justify-content: center;">
              <button class="btn btn-primary" id="galleryBtn" style="padding: 10px 20px;">🖼️ Gallery</button>
              <button class="btn btn-outline" id="cameraBtn" style="padding: 10px 20px;">📷 Camera</button>
            </div>
          </div>
        `}
      </div>
    `;
  }

  function renderAnalyzing() {
    return `
      <div class="glass-card" style="padding: 40px 20px; text-align: center;">
        <div class="spinner" style="margin: 0 auto 20px; width: 60px; height: 60px;"></div>
        <h2 style="font-size: 18px; margin-bottom: 8px;">Analyzing Image on Agro AI Backend...</h2>
        <p style="font-size: 13px; color: var(--text-muted);">Running vision model analysis & safety validation</p>
      </div>
    `;
  }

  function renderLowConfidence() {
    return `
      <div class="glass-card" style="padding: 24px; text-align: center; border-left: 4px solid #F59E0B;">
        <div style="font-size: 48px; margin-bottom: 12px;">🔍</div>
        <h2 style="font-size: 18px; font-weight: 800; color: #D97706; margin-bottom: 8px;">Low Confidence Diagnosis</h2>
        <p style="font-size: 14px; color: var(--text); margin-bottom: 16px;">The image is not clear enough for a reliable diagnosis.</p>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 24px;">Please upload a clear, focused photo of one affected leaf under good lighting.</p>
        <button class="btn btn-primary" id="tryAgainBtn" style="width: 100%; padding: 12px;">📷 Upload Clearer Photo</button>
      </div>
    `;
  }

  function renderError() {
    return `
      <div class="glass-card" style="padding: 24px; text-align: center; border-left: 4px solid #EF4444;">
        <div style="font-size: 48px; margin-bottom: 12px;">⚠️</div>
        <h2 style="font-size: 18px; font-weight: 800; color: #DC2626; margin-bottom: 8px;">Diagnosis Failed</h2>
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">${errorMessage || 'Backend error during diagnosis.'}</p>
        <button class="btn btn-primary" id="tryAgainBtn" style="width: 100%; padding: 12px;">🔄 Retry Upload</button>
      </div>
    `;
  }

  function renderResult() {
    if (!lastReport) return renderIdle();
    const r = lastReport;
    const isHealthy = r.disease?.toLowerCase().includes('healthy');
    const severityColor = r.severity === 'critical' ? '#EF4444' : r.severity === 'moderate' ? '#F59E0B' : '#10B981';

    return `
      <div class="glass-card" style="padding: 20px; margin-bottom: 16px; border-left: 4px solid ${severityColor};">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <div>
            <span style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--accent); letter-spacing: 0.5px;">CROP: ${r.crop || 'Detected Crop'}</span>
            <h2 style="font-size: 20px; font-weight: 900; margin-top: 2px;">${r.disease}</h2>
            ${r.scientific_name ? `<div style="font-size: 12px; font-style: italic; color: var(--text-muted);">${r.scientific_name}</div>` : ''}
          </div>
          <div style="text-align: right;">
            <span style="background: ${severityColor}22; color: ${severityColor}; font-size: 12px; font-weight: 800; padding: 4px 10px; border-radius: 20px; display: inline-block;">
              ${(r.confidence * 100).toFixed(0)}% Confidence
            </span>
          </div>
        </div>

        <!-- Ask Agro GPT Callout -->
        <button id="askGptWithContextBtn" class="btn btn-accent" style="width: 100%; padding: 12px; margin: 16px 0; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 8px;">
          💬 Ask Agro GPT about this diagnosis
        </button>

        <!-- Treatments -->
        ${(r.organic_treatment && r.organic_treatment.length > 0) ? `
          <div style="margin-top: 16px;">
            <div style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 6px;">🌿 Organic Treatment</div>
            <ul style="padding-left: 18px; font-size: 13px; color: var(--text-secondary);">
              ${r.organic_treatment.map(t => `<li style="margin-bottom: 4px;">${t}</li>`).join('')}
            </ul>
          </div>
        ` : ''}

        ${(r.chemical_treatment && r.chemical_treatment.length > 0) ? `
          <div style="margin-top: 16px;">
            <div style="font-size: 14px; font-weight: 800; color: var(--text); margin-bottom: 6px;">🧪 Chemical Treatment & Dosage</div>
            <ul style="padding-left: 18px; font-size: 13px; color: var(--text-secondary);">
              ${r.chemical_treatment.map((t, idx) => `<li style="margin-bottom: 4px;"><strong>${t}</strong> ${r.dosage?.[idx] ? `— Dosage: ${r.dosage[idx]}` : ''}</li>`).join('')}
            </ul>
          </div>
        ` : ''}

        <div style="margin-top: 20px; display: flex; gap: 10px;">
          <button class="btn btn-outline" id="newDiagBtn" style="width: 100%;">📷 New Diagnosis</button>
        </div>
      </div>
    `;
  }

  function attachListeners(container) {
    const galleryBtn = container.querySelector('#galleryBtn');
    const cameraBtn = container.querySelector('#cameraBtn');
    const fileInput = container.querySelector('#fileInput');
    const cameraInput = container.querySelector('#cameraInput');
    const analyzeBtn = container.querySelector('#analyzeBtn');
    const removeImg = container.querySelector('#removeImg');
    const askGptBtn = container.querySelector('#askGptWithContextBtn');
    const newDiagBtn = container.querySelector('#newDiagBtn');
    const tryAgainBtn = container.querySelector('#tryAgainBtn');

    if (galleryBtn) galleryBtn.onclick = () => fileInput.click();
    if (cameraBtn) cameraBtn.onclick = () => cameraInput.click();

    const handleFileSelect = (e) => {
      const file = e.target.files[0];
      if (file) {
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (ev) => {
          imageDataUrl = ev.target.result;
          analysisState = 'idle';
          render(container);
        };
        reader.readAsDataURL(file);
      }
    };

    if (fileInput) fileInput.onchange = handleFileSelect;
    if (cameraInput) cameraInput.onchange = handleFileSelect;

    if (removeImg) {
      removeImg.onclick = () => {
        selectedFile = null;
        imageDataUrl = null;
        analysisState = 'idle';
        render(container);
      };
    }

    if (analyzeBtn) {
      analyzeBtn.onclick = async () => {
        if (!selectedFile) return;
        analysisState = 'analyzing';
        render(container);

        try {
          const lang = (window.KisanI18n && typeof window.KisanI18n.getCurrentLang === 'function') 
            ? window.KisanI18n.getCurrentLang() 
            : (window.KisanI18n && typeof window.KisanI18n.getCurrentLanguage === 'function' ? window.KisanI18n.getCurrentLanguage() : 'en');
          const res = await window.KisanAPI.diagnoseCrop(selectedFile, '', lang);
          if (res.status === 'low_confidence') {
            analysisState = 'low_confidence';
          } else {
            lastReport = res;
            analysisState = 'done';
          }
        } catch (err) {
          analysisState = 'error';
          errorMessage = err.message || 'Error communicating with backend API';
        }
        render(container);
      };
    }

    if (tryAgainBtn) {
      tryAgainBtn.onclick = () => {
        selectedFile = null;
        imageDataUrl = null;
        analysisState = 'idle';
        render(container);
      };
    }

    if (newDiagBtn) {
      newDiagBtn.onclick = () => {
        selectedFile = null;
        imageDataUrl = null;
        analysisState = 'idle';
        lastReport = null;
        render(container);
      };
    }

    if (askGptBtn && lastReport) {
      askGptBtn.onclick = async () => {
        try {
          await window.KisanAPI.attachDiagnosisContext(lastReport.report_id);
        } catch(e){}
        if (window.attachKisanGptDiagnosisContext) {
          window.attachKisanGptDiagnosisContext(lastReport);
        } else {
          window.location.hash = '#/kisan-gpt';
        }
      };
    }
  }

  if (window.KisanRouter) window.KisanRouter.register('/diagnose', render);
})();
