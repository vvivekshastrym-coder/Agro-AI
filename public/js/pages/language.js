// KisanAI Language Selection Page Renderer
(function() {
  let searchFilter = '';
  let selectedLang = 'en';

  const languages = [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी' },
    { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
    { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
    { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்' },
    { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം' },
    { code: 'mr', name: 'Marathi', nativeName: 'मराठी' },
    { code: 'bn', name: 'Bengali', nativeName: 'বাংলা' },
    { code: 'gu', name: 'Gujarati', nativeName: 'ગુજરાતી' },
    { code: 'pa', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ' },
    { code: 'ur', name: 'Urdu', nativeName: 'اردو' },
    { code: 'or', name: 'Odia', nativeName: 'ଓଡ଼ିଆ' },
    { code: 'bho', name: 'Bhojpuri', nativeName: 'भोजपुरी' },
    { code: 'as', name: 'Assamese', nativeName: 'অসমীয়া' },
    { code: 'har', name: 'Haryanvi', nativeName: 'हरियाणवी' }
  ];

  function render(container) {
    if (window.KisanI18n) {
      selectedLang = window.KisanI18n.getCurrentLang();
    }

    const filteredLangs = languages.filter(lang => 
      lang.name.toLowerCase().includes(searchFilter.toLowerCase()) || 
      lang.nativeName.toLowerCase().includes(searchFilter.toLowerCase())
    );

    let contentHtml = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 24px; margin-bottom: 6px; color: #ffffff;">🌐 Select Language</h1>
        <p style="font-size: 14px; color: var(--text-muted);">Choose your preferred language for voice and app support.</p>
      </div>

      <!-- Search Box -->
      <div class="glass-card" style="padding: 10px; margin-bottom: 16px;">
        <input type="text" id="langSearchInput" class="btn btn-outline" style="text-align: left; background: rgba(255,255,255,0.02); border-color: rgba(255,255,255,0.1); padding: 8px 12px; font-size: 13.5px;" placeholder="🔍 Search language..." value="${searchFilter}">
      </div>

      <!-- Language Cards Grid -->
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; max-height: 320px; overflow-y: auto; padding-right: 4px;">
        ${filteredLangs.map(lang => {
          const isActive = lang.code === selectedLang;
          const activeStyle = isActive ? 'border-color: var(--accent); background: rgba(245, 158, 11, 0.1); color: var(--accent);' : '';
          return `
            <div class="glass-card glass-card-interactive lang-select-card" data-code="${lang.code}" style="padding: 12px; text-align: center; margin-bottom: 0; ${activeStyle}">
              <div style="font-size: 16px; font-weight: 700;">${lang.nativeName}</div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${lang.name}</div>
            </div>
          `;
        }).join('')}
      </div>

      <!-- CTA -->
      <button class="btn btn-primary" id="langContinueBtn">Continue</button>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
  }

  function attachListeners(container) {
    const searchInput = container.querySelector('#langSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        searchFilter = e.target.value;
        render(container);
        // Put focus back to input and place cursor at end
        const input = container.querySelector('#langSearchInput');
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      });
    }

    const cards = container.querySelectorAll('.lang-select-card');
    cards.forEach(card => {
      card.addEventListener('click', () => {
        selectedLang = card.getAttribute('data-code');
        render(container);
      });
    });

    const contBtn = container.querySelector('#langContinueBtn');
    if (contBtn) {
      contBtn.addEventListener('click', () => {
        if (window.KisanI18n) {
          window.KisanI18n.setLanguage(selectedLang);
        }
        window.location.hash = '#/login';
      });
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/language', render);
  }
})();
