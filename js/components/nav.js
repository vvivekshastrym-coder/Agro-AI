// KisanAI Navigations and Language Selector Modal
(function() {
  
  // Icon SVGs
  const icons = {
    home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
    diagnose: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
    gpt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
    weather: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><path d="M12 2v2M4.22 4.22l1.42 1.42M1 12h2M21 12h2M18.36 5.64l1.42-1.42M23 22H3a5 5 0 0 1 0-10h.55a8 8 0 0 1 15.45 0H23a5 5 0 0 1 0 10z"/></svg>`,
    market: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
    more: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`
  };

  function createTopBar() {
    const header = document.createElement('header');
    header.className = 'top-bar';
    header.innerHTML = `
      <div class="logo-container">
        <div class="logo-icon">🌾</div>
        <div>
          <div class="logo-name">KisanAI</div>
          <div class="logo-tagline">AI Farm Assistant</div>
        </div>
      </div>
      <button class="globe-btn" id="globalLangBtn" aria-label="Change Language">
        🌐
      </button>
    `;

    // Event listener for language button
    header.querySelector('#globalLangBtn').addEventListener('click', toggleLanguageOverlay);
    return header;
  }

  function createBottomNav() {
    const nav = document.createElement('nav');
    nav.className = 'bottom-nav';
    nav.innerHTML = `
      <a href="#/" class="bottom-nav-item" data-route="/">
        ${icons.home}
        <span data-i18n="home">Home</span>
      </a>
      <a href="#/diagnose" class="bottom-nav-item" data-route="/diagnose">
        ${icons.diagnose}
        <span data-i18n="diagnose">Diagnose</span>
      </a>
      <a href="#/kisan-gpt" class="bottom-nav-item" data-route="/kisan-gpt">
        ${icons.gpt}
        <span data-i18n="gpt">Kisan GPT</span>
      </a>
      <a href="#/weather" class="bottom-nav-item" data-route="/weather">
        ${icons.weather}
        <span data-i18n="weather">Weather</span>
      </a>
      <a href="#/more" class="bottom-nav-item" data-route="/more">
        ${icons.more}
        <span data-i18n="more">More</span>
      </a>
    `;
    return nav;
  }

  function createLanguageOverlay() {
    // If it already exists, just return it
    let overlay = document.getElementById('kisanLangOverlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'kisanLangOverlay';
    overlay.className = 'lang-overlay';
    
    document.body.appendChild(overlay);
    renderOverlayContent(overlay);
    return overlay;
  }

  function renderOverlayContent(overlay) {
    const currentLang = window.KisanI18n ? window.KisanI18n.getCurrentLang() : 'en';
    const titleText = window.KisanI18n ? window.KisanI18n.t('selectLang') : 'Select Language';
    const backText = window.KisanI18n ? window.KisanI18n.t('back') : 'Back';

    let langGridHtml = '';
    const languages = window.KisanI18n ? window.KisanI18n.LANGUAGES : [];
    
    languages.forEach(lang => {
      const isActive = lang.code === currentLang ? 'active' : '';
      langGridHtml += `
        <div class="lang-card ${isActive}" data-lang="${lang.code}">
          <div class="lang-native">${lang.nativeName}</div>
          <div class="lang-english">${lang.name}</div>
        </div>
      `;
    });

    overlay.innerHTML = `
      <div class="lang-overlay-header">
        <h2 style="font-size: 22px;">${titleText}</h2>
        <button class="btn btn-outline" style="width: auto; padding: 6px 16px; min-height: unset;" id="closeLangOverlay">
          ${backText}
        </button>
      </div>
      <div class="lang-grid">
        ${langGridHtml}
      </div>
    `;

    // Close button event
    overlay.querySelector('#closeLangOverlay').addEventListener('click', () => {
      overlay.classList.remove('open');
    });

    // Language selection cards event
    overlay.querySelectorAll('.lang-card').forEach(card => {
      card.addEventListener('click', () => {
        const langCode = card.getAttribute('data-lang');
        if (window.KisanI18n) {
          window.KisanI18n.setLanguage(langCode);
        }
        overlay.classList.remove('open');
        // Redraw overlay to reflect new active state next time it opens
        renderOverlayContent(overlay);
      });
    });
  }

  function toggleLanguageOverlay() {
    const overlay = createLanguageOverlay();
    // Refresh content to match current language
    renderOverlayContent(overlay);
    overlay.classList.toggle('open');
  }

  // Hook into language change event to refresh overlay content internally
  window.addEventListener('kisanLanguageChanged', () => {
    const overlay = document.getElementById('kisanLangOverlay');
    if (overlay) {
      renderOverlayContent(overlay);
    }
  });

  // Export
  window.KisanNav = {
    createTopBar,
    createBottomNav,
    toggleLanguageOverlay
  };
})();
