// KisanAI More Services Page & Ecosystem Details
(function() {
  function render(container) {
    const t = window.KisanI18n ? window.KisanI18n.t : (key) => key;
    const currentLang = window.KisanI18n ? window.KisanI18n.getCurrentLang() : 'en';

    // List of premium services from PPT slides
    const services = [
      {
        icon: '🛰️',
        title: t('prodSatelliteTitle'),
        desc: t('prodSatelliteDesc'),
        route: '/satellite',
        details: "Digital Twin & Satellite Field Monitoring: Using Sentinel-2 ESA open datasets and Google Earth Engine to monitor farm vegetation index (NDVI). Automatically detects crop stress, water pooling, or chlorophyll loss 14 days before it is visible to the human eye, sending proactive SMS alerts to prevent outbreak spreads."
      },
      {
        icon: '🧪',
        title: t('prodSoilTitle'),
        desc: t('prodSoilDesc'),
        route: '/soil-dna',
        details: "Soil Microbiome DNA Testing: A simple test kit sent directly to your farm via India Post. Scoop soil, mail it back, and receive a complete genomic sequence of your soil's beneficial bacteria, fungi, and pathogens. Replaces guesswork and chemical fertilizer overuse, saving up to ₹2,000/acre/season."
      },
      {
        icon: '⚡',
        title: 'Auto-Triggered Insurance',
        desc: "Satellite damage detection triggers auto claim and UPI payout in 24 hrs.",
        route: '/insurance',
        details: "Parametric smart-contract insurance. When local weather sensors report a dry spell or satellite imagery confirms wind/flood damage to your field, a claim is auto-triggered. Zero forms, zero surveyors, and direct cash deposit via UPI to the farmer's bank account within 24 hours."
      },
      {
        icon: '🌱',
        title: 'Carbon Credit Offset',
        desc: "Earn extra income by implementing eco-friendly farming practices.",
        route: '/carbon',
        details: "Marketplace for sustainable agriculture. AI calculates your organic carbon sequestration. Certified credits are bundled and sold to top corporate buyers like Tata or Infosys, giving you up to ₹15,000 extra income per season."
      },
      {
        icon: '🚁',
        title: 'Drone Scouting',
        desc: "Book DGCA-certified drone pilots for farm mapping and spraying.",
        route: '/drone',
        details: "Kisan Drone Marketplace: Instantly book certified pilots near your village. Get ultra-high-resolution multispectral field scans (NDVI) or schedule automated pesticide/fertilizer spraying starting at just ₹250 per acre."
      },
      {
        icon: '🚚',
        title: 'Harvest Logistics',
        desc: "Truck matching with fair quotes, ratings, and farm transport.",
        route: '/logistics',
        details: "Local cargo network connecting you directly to truck drivers. View real-time quotes, driver ratings, and standard market rates to prevent price exploitation by middlemen during harvest rush."
      },
      {
        icon: '💳',
        title: 'KisanScore Credit',
        desc: "Unlock lower bank interest rates using UPI & satellite farm data.",
        route: '/credit',
        details: "Alternative credit scoring platform. Combines your UPI digital receipts, satellite farm history, and yield predictions to create a KisanScore. Local banks use this score to instantly approve low-interest crop loans."
      },
      {
        icon: '🔗',
        title: 'Blockchain Farm Passport',
        desc: "Traceability QR code on crop bags showing farmer info & purity.",
        route: '/passport',
        details: "Farm passport for urban buyers. Generates a unique QR code on every crop bag. Consumers scan it in urban supermarket shelves to verify your village name, farmer face, crop purity, and pesticide-free guarantee."
      },
      {
        icon: '👤',
        title: 'Farmer Profile',
        desc: "View your verified farmer dashboard, crop history, and achievements.",
        route: '/profile',
        details: "Farmer dashboard showing your acreage, crop cycles, registered locations, verified credentials, and gamified achievements badge awards."
      },
      {
        icon: '⚙️',
        title: 'App Settings',
        desc: "Configure push alerts, offline caching, and biometric unlock preferences.",
        route: '/settings',
        details: "Control system security, notifications stream toggles, offline database cache syncing, and accessibility contrast adjustments."
      },
      {
        icon: '💬',
        title: 'Help Center',
        desc: "Talk to agro experts, view video tutorials, or call support desk.",
        route: '/help',
        details: "Access FAQs, video guides on automated drone spraying, or launch live chat sessions with certified crop agronomists."
      }
    ];

    let pageHtml = `
      <div style="margin-bottom: 20px;">
        <h1 data-i18n="moreTitle" style="font-size: 24px; margin-bottom: 6px;">${t('moreTitle')}</h1>
        <p data-i18n="moreDesc" style="font-size: 14px; color: var(--text-muted);">${t('moreDesc')}</p>
      </div>

      <!-- Globe Selection Inside More Page -->
      <div class="glass-card" style="padding: 16px; border-color: rgba(245, 158, 11, 0.2);">
        <h3 data-i18n="selectLang" style="font-size: 15px; margin-bottom: 12px; color: var(--accent);">🌐 ${t('selectLang')}</h3>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;" id="moreLangGrid">
          ${renderLanguageGrid(currentLang)}
        </div>
      </div>

      <!-- Services Grid -->
      <div class="grid-2">
        ${services.map((srv, idx) => `
          <div class="glass-card glass-card-interactive service-item-card" data-index="${idx}" style="padding: 16px;">
            <div style="font-size: 28px; margin-bottom: 8px;">${srv.icon}</div>
            <h3 style="font-size: 15px; margin-bottom: 4px; color: #ffffff;">${srv.title}</h3>
            <p style="font-size: 12.5px; color: var(--text-muted); line-height: 1.4;">${srv.desc}</p>
            <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: var(--accent); display: flex; align-items: center; gap: 4px;">
              <span>View Module</span>
              <span>→</span>
            </div>
          </div>
        `).join('')}
      </div>

      <!-- Modal overlay for service details -->
      <div id="serviceDetailModal" class="lang-overlay" style="justify-content: center; padding: 24px 20px;">
        <div class="glass-card" style="margin: auto; max-width: 500px; width: 100%; border-color: var(--accent);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="modalIcon" style="font-size: 28px;">🛰️</span>
              <h3 id="modalTitle" style="font-size: 18px; color: #ffffff;">Service Name</h3>
            </div>
            <button class="btn btn-outline" id="closeModalBtn" style="width: auto; padding: 4px 12px; min-height: unset; font-size: 12px;">✕ Close</button>
          </div>
          <p id="modalDetails" style="font-size: 14px; line-height: 1.5; color: #e5e7eb; margin-bottom: 16px;">
            Description details go here.
          </p>
          <button class="btn btn-primary" id="modalOkBtn" data-i18n="comingSoon">
            ${t('comingSoon')}
          </button>
        </div>
      </div>
    `;

    container.innerHTML = pageHtml;
    attachListeners(container, services);
  }

  function renderLanguageGrid(currentLang) {
    const languages = window.KisanI18n ? window.KisanI18n.LANGUAGES : [];
    return languages.map(lang => {
      const active = lang.code === currentLang ? 'style="border-color: var(--accent); background: rgba(245,158,11,0.1); color: var(--accent); font-weight:700;"' : '';
      return `<button class="btn btn-outline" ${active} data-lang-btn="${lang.code}" style="padding: 8px 10px; font-size: 13.5px; min-height: 38px;">${lang.nativeName}</button>`;
    }).join('');
  }

  function attachListeners(container, services) {
    // Language quick change listeners
    const langBtns = container.querySelectorAll('[data-lang-btn]');
    langBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const langCode = btn.getAttribute('data-lang-btn');
        if (window.KisanI18n) {
          window.KisanI18n.setLanguage(langCode);
        }
      });
    });

    // Modal elements (fallback)
    const modal = container.querySelector('#serviceDetailModal');
    const modalIcon = container.querySelector('#modalIcon');
    const modalTitle = container.querySelector('#modalTitle');
    const modalDetails = container.querySelector('#modalDetails');
    const closeModal = container.querySelector('#closeModalBtn');
    const modalOk = container.querySelector('#modalOkBtn');

    const openModal = (srv) => {
      modalIcon.textContent = srv.icon;
      modalTitle.textContent = srv.title;
      modalDetails.textContent = srv.details;
      modal.classList.add('open');
    };

    const hideModal = () => {
      modal.classList.remove('open');
    };

    // Card click events
    container.querySelectorAll('.service-item-card').forEach(card => {
      card.addEventListener('click', () => {
        const index = parseInt(card.getAttribute('data-index'), 10);
        const srv = services[index];
        if (srv && srv.route) {
          window.location.hash = '#' + srv.route;
        } else if (srv) {
          openModal(srv);
        }
      });
    });

    closeModal.addEventListener('click', hideModal);
    modalOk.addEventListener('click', hideModal);
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/more', render);
  }
})();
