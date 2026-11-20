// KisanAI — Premium 4-Slide Onboarding
(function () {

  /* ── module-level state ── */
  let activeSlide = 0;

  const slides = [
    {
      icon: '🔬',
      color: '#22c55e',
      badge: 'AI Vision',
      title: 'AI Crop Doctor',
      subtitle: 'Diagnose diseases in 3 seconds',
      desc: 'Point your camera at any leaf. Our Vision AI instantly identifies 200+ crop diseases across 50+ crops and prescribes personalised chemical & organic treatment plans.',
      stat1: '200+ Diseases', stat2: '98.4% Accuracy',
    },
    {
      icon: '🗣️',
      color: '#3b82f6',
      badge: '50+ Languages',
      title: 'Voice AI Agronomist',
      subtitle: 'Talk in your language',
      desc: 'Kisan GPT understands 50+ Indian dialects. Speak naturally in Hindi, Telugu, Kannada, Tamil, Marathi, or any regional language — just like calling a real agronomist.',
      stat1: '50+ Dialects', stat2: '24 / 7 Support',
    },
    {
      icon: '🛰️',
      color: '#a855f7',
      badge: 'Sentinel-2',
      title: 'Satellite Intelligence',
      subtitle: 'See what eyes cannot',
      desc: 'Sentinel-2 satellites monitor every centimetre of your farm 24/7. Receive stress alerts, water-pooling warnings, and pest outbreak forecasts 14 days before visible symptoms appear.',
      stat1: '14-Day Forecast', stat2: '10m Resolution',
    },
    {
      icon: '💰',
      color: '#f59e0b',
      badge: 'Earn More',
      title: 'AI Income Boost',
      subtitle: 'AI-powered income boost',
      desc: 'Track live mandi prices across 7,000+ markets, earn carbon credits for sustainable practices, and unlock low-interest KisanScore loans — all in one place.',
      stat1: '7,000+ Mandis', stat2: '₹32K avg. boost',
    },
  ];

  /* ── inject styles once ── */
  function injectStyles() {
    if (document.getElementById('kisanOnbStyles')) return;
    const s = document.createElement('style');
    s.id = 'kisanOnbStyles';
    s.textContent = `
      @keyframes onb-slide-in {
        0%   { opacity: 0; transform: translateX(40px) scale(0.97); }
        100% { opacity: 1; transform: translateX(0)   scale(1);    }
      }
      @keyframes onb-icon-bounce {
        0%   { transform: scale(0.5) rotate(-8deg); opacity: 0; }
        60%  { transform: scale(1.12) rotate(4deg); opacity: 1; }
        80%  { transform: scale(0.95) rotate(-2deg); }
        100% { transform: scale(1) rotate(0deg); }
      }
      @keyframes onb-stat-pop {
        0%   { transform: translateY(8px); opacity: 0; }
        100% { transform: translateY(0);   opacity: 1; }
      }
      .onb-stat-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 10px 16px;
        text-align: center;
        animation: onb-stat-pop 0.5s ease-out both;
      }
      .onb-stat-card:nth-child(2) { animation-delay: 0.12s; }
    `;
    document.head.appendChild(s);
  }

  function render(container) {
    injectStyles();
    const slide = slides[activeSlide];
    const isLast = activeSlide === slides.length - 1;

    /* background glow colour per slide */
    const glowMap = ['rgba(34,197,94,0.08)', 'rgba(59,130,246,0.08)', 'rgba(168,85,247,0.08)', 'rgba(245,158,11,0.10)'];
    const glow = glowMap[activeSlide];

    container.innerHTML = `
      <div style="
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        background: var(--bg);
        position: relative;
        overflow: hidden;
      ">

        <!-- Background glow -->
        <div style="
          position: absolute;
          top: -10%;
          left: 50%;
          transform: translateX(-50%);
          width: 100vw;
          height: 55vh;
          background: radial-gradient(ellipse at top, ${glow} 0%, transparent 70%);
          pointer-events: none;
          transition: background 0.4s ease;
        "></div>

        <!-- ── TOP BAR (Skip) ── -->
        <div style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 52px 24px 0;
          position: relative;
          z-index: 2;
        ">
          <div style="
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 999px;
            padding: 4px 12px;
            font-size: 11px;
            font-weight: 700;
            color: ${slide.color};
            letter-spacing: 0.06em;
            text-transform: uppercase;
          ">${slide.badge}</div>

          ${activeSlide < slides.length - 1 ? `
            <button id="onbSkipBtn" style="
              background: none;
              border: none;
              color: var(--text-muted);
              font-size: 14px;
              font-weight: 600;
              cursor: pointer;
              padding: 8px 4px;
            ">Skip →</button>
          ` : '<div style="width:60px"></div>'}
        </div>

        <!-- ── SLIDE CONTENT ── -->
        <div style="
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 28px;
          text-align: center;
          position: relative;
          z-index: 2;
          animation: onb-slide-in 0.38s ease-out both;
        ">
          <!-- Icon circle -->
          <div style="
            width: 140px; height: 140px;
            border-radius: 50%;
            background: radial-gradient(circle, ${glow.replace('0.08', '0.18').replace('0.10','0.20')} 0%, rgba(20,36,27,0.6) 70%);
            border: 2px solid ${slide.color}22;
            display: flex; align-items: center; justify-content: center;
            font-size: 76px;
            margin-bottom: 32px;
            animation: onb-icon-bounce 0.7s cubic-bezier(0.175,0.885,0.32,1.275) both;
            filter: drop-shadow(0 0 24px ${slide.color}44);
            position: relative;
          ">
            ${slide.icon}
            <!-- accent dot -->
            <div style="
              position: absolute;
              bottom: 8px; right: 8px;
              width: 22px; height: 22px;
              border-radius: 50%;
              background: ${slide.color};
              border: 3px solid var(--bg);
              display: flex; align-items: center; justify-content: center;
              font-size: 10px;
            ">✓</div>
          </div>

          <!-- Title -->
          <h2 style="
            font-size: 30px;
            font-weight: 900;
            letter-spacing: -0.03em;
            color: #ffffff;
            margin-bottom: 8px;
            line-height: 1.1;
          ">${slide.title}</h2>

          <!-- Subtitle -->
          <p style="
            font-size: 13px;
            font-weight: 700;
            color: ${slide.color};
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 16px;
          ">${slide.subtitle}</p>

          <!-- Description -->
          <p style="
            font-size: 15px;
            line-height: 1.65;
            color: var(--text-muted);
            max-width: 340px;
            margin-bottom: 28px;
          ">${slide.desc}</p>

          <!-- Stat pills -->
          <div style="display: flex; gap: 12px; justify-content: center;">
            <div class="onb-stat-card">
              <div style="font-size: 14px; font-weight: 800; color: #ffffff;">${slide.stat1}</div>
            </div>
            <div class="onb-stat-card">
              <div style="font-size: 14px; font-weight: 800; color: #ffffff;">${slide.stat2}</div>
            </div>
          </div>
        </div>

        <!-- ── BOTTOM CONTROLS ── -->
        <div style="
          padding: 0 28px 48px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 20px;
          position: relative;
          z-index: 2;
        ">
          <!-- Dot indicators -->
          <div class="onboarding-dots">
            ${slides.map((_, i) => `
              <div class="onboarding-dot ${i === activeSlide ? 'active' : ''}"
                style="${i === activeSlide ? `background:${slide.color};` : ''}">
              </div>
            `).join('')}
          </div>

          <!-- CTA Button -->
          ${isLast ? `
            <button id="onbGetStartedBtn" class="btn" style="
              max-width: 340px;
              background: linear-gradient(135deg, var(--accent), var(--accent-light));
              color: #0b130e;
              font-size: 16px;
              font-weight: 800;
              letter-spacing: -0.01em;
              box-shadow: 0 8px 24px rgba(245,158,11,0.35);
              border: none;
            ">🚀 Get Started — It's Free</button>
          ` : `
            <button id="onbNextBtn" class="btn" style="
              max-width: 340px;
              background: linear-gradient(135deg, var(--primary-light), var(--primary));
              color: #ffffff;
              font-size: 16px;
              font-weight: 700;
              border: 1px solid rgba(255,255,255,0.08);
              box-shadow: 0 4px 16px rgba(31,77,43,0.4);
            ">Next →</button>
          `}

          <!-- Slide counter -->
          <p style="font-size: 12px; color: rgba(255,255,255,0.2); margin-top: -8px;">
            ${activeSlide + 1} of ${slides.length}
          </p>
        </div>
      </div>
    `;

    attachListeners(container);
  }

  function attachListeners(container) {
    const nextBtn = container.querySelector('#onbNextBtn');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (activeSlide < slides.length - 1) {
          activeSlide++;
          render(container);
        }
      });
    }

    const skipBtn = container.querySelector('#onbSkipBtn');
    if (skipBtn) {
      skipBtn.addEventListener('click', () => {
        activeSlide = 0;           // reset for next visit
        window.location.hash = '#/language';
      });
    }

    const startBtn = container.querySelector('#onbGetStartedBtn');
    if (startBtn) {
      startBtn.addEventListener('click', () => {
        localStorage.setItem('kisanOnboarded', 'true');
        activeSlide = 0;           // reset
        window.location.hash = '#/language';
      });
    }

    /* swipe gesture */
    let touchX = null;
    const swipeEl = container.querySelector('div');
    if (swipeEl) {
      swipeEl.addEventListener('touchstart', e => { touchX = e.touches[0].clientX; }, { passive: true });
      swipeEl.addEventListener('touchend', e => {
        if (touchX === null) return;
        const dx = e.changedTouches[0].clientX - touchX;
        if (Math.abs(dx) > 50) {
          if (dx < 0 && activeSlide < slides.length - 1) { activeSlide++; render(container); }
          if (dx > 0 && activeSlide > 0) { activeSlide--; render(container); }
        }
        touchX = null;
      }, { passive: true });
    }
  }

  if (window.KisanRouter) {
    window.KisanRouter.register('/onboarding', render);
  }
})();
