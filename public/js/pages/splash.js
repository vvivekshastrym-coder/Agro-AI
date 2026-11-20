// KisanAI — Premium Splash Screen
(function () {

  /* ─── keyframe injection (runs once) ─── */
  function injectSplashStyles() {
    if (document.getElementById('kisanSplashStyles')) return;
    const style = document.createElement('style');
    style.id = 'kisanSplashStyles';
    style.textContent = `
      @keyframes splash-progress {
        0%   { width: 0%; }
        100% { width: 100%; }
      }
      @keyframes float-particle {
        0%   { transform: translateY(0) scale(1);   opacity: 0.8; }
        50%  { transform: translateY(-60px) scale(1.3); opacity: 0.5; }
        100% { transform: translateY(-120px) scale(0.8); opacity: 0; }
      }
      @keyframes logo-fade-in {
        0%   { opacity: 0; transform: translateY(16px); }
        100% { opacity: 1; transform: translateY(0); }
      }
      @keyframes tagline-fade {
        0%   { opacity: 0; letter-spacing: 0.25em; }
        100% { opacity: 1; letter-spacing: 0.12em; }
      }
      @keyframes orbit-dot {
        0%   { transform: rotate(0deg) translateX(55px); }
        100% { transform: rotate(360deg) translateX(55px); }
      }
      @keyframes orbit-dot-rev {
        0%   { transform: rotate(0deg) translateX(68px); }
        100% { transform: rotate(-360deg) translateX(68px); }
      }
      @keyframes pulse-ring {
        0%, 100% { transform: scale(1);   opacity: 0.6; }
        50%       { transform: scale(1.08); opacity: 1;   }
      }
    `;
    document.head.appendChild(style);
  }

  function render(container) {
    injectSplashStyles();

    /* particle positions/sizes/delays */
    const particles = [
      { left: '12%', size: 5,  delay: '0s',    dur: '3.2s' },
      { left: '28%', size: 4,  delay: '0.5s',  dur: '2.8s' },
      { left: '45%', size: 6,  delay: '0.2s',  dur: '3.6s' },
      { left: '60%', size: 3,  delay: '0.8s',  dur: '2.5s' },
      { left: '75%', size: 5,  delay: '0.3s',  dur: '3.0s' },
      { left: '88%', size: 4,  delay: '1.0s',  dur: '2.7s' },
    ];

    const particleHtml = particles.map(p => `
      <div style="
        position: absolute;
        bottom: 18%;
        left: ${p.left};
        width: ${p.size}px;
        height: ${p.size}px;
        border-radius: 50%;
        background: var(--accent);
        opacity: 0;
        animation: float-particle ${p.dur} ${p.delay} ease-in-out infinite;
        pointer-events: none;
      "></div>
    `).join('');

    container.innerHTML = `
      <!-- ═══ Full-viewport wrapper ═══ -->
      <div id="splashRoot" style="
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: var(--bg);
        overflow: hidden;
        text-align: center;
        padding: 32px 20px;
      ">

        <!-- ── Radial sunrise glow at bottom ── -->
        <div style="
          position: absolute;
          bottom: -10%;
          left: 50%;
          transform: translateX(-50%);
          width: 110vw;
          height: 60vh;
          background: radial-gradient(ellipse at center bottom,
            rgba(245,158,11,0.22) 0%,
            rgba(31,77,43,0.12)   40%,
            transparent           70%);
          pointer-events: none;
        "></div>

        <!-- ── Corner vignette glows ── -->
        <div style="
          position: absolute; top: 0; left: 0;
          width: 35vw; height: 35vw; max-width: 260px; max-height: 260px;
          background: radial-gradient(circle, rgba(31,77,43,0.2), transparent 70%);
          pointer-events: none;
        "></div>
        <div style="
          position: absolute; bottom: 0; right: 0;
          width: 35vw; height: 35vw; max-width: 260px; max-height: 260px;
          background: radial-gradient(circle, rgba(245,158,11,0.08), transparent 70%);
          pointer-events: none;
        "></div>

        <!-- ── Floating particles ── -->
        ${particleHtml}

        <!-- ═══ LOGO BLOCK ═══ -->
        <div class="splash-logo-wrapper" style="
          position: relative;
          width: 160px; height: 160px;
          display: flex; align-items: center; justify-content: center;
          margin-bottom: 28px;
        ">
          <!-- Outer pulsing circuit ring -->
          <div class="splash-circuit" style="
            width: 148px; height: 148px;
            animation: pulse-ring 3.5s ease-in-out infinite;
          "></div>

          <!-- Rotating orbit ring with a dot -->
          <div class="splash-orbit" style="
            width: 120px; height: 120px;
            animation: rotate-orbit 7s linear infinite;
            border: 2px dashed rgba(245,158,11,0.4);
          ">
            <!-- Orbit dot -->
            <div style="
              position: absolute;
              top: -5px; left: 50%; transform: translateX(-50%);
              width: 10px; height: 10px;
              border-radius: 50%;
              background: var(--accent);
              box-shadow: 0 0 8px rgba(245,158,11,0.9);
            "></div>
          </div>

          <!-- Second counter-rotating ring -->
          <div style="
            position: absolute;
            width: 96px; height: 96px;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 50%;
            animation: rotate-orbit 14s linear infinite reverse;
          ">
            <div style="
              position: absolute;
              bottom: -4px; left: 50%; transform: translateX(-50%);
              width: 7px; height: 7px;
              border-radius: 50%;
              background: rgba(255,255,255,0.4);
            "></div>
          </div>

          <!-- 🌾 Leaf — uses existing .splash-leaf + growing animation -->
          <div class="splash-leaf" style="
            font-size: 72px;
            z-index: 4;
            filter: drop-shadow(0 0 20px rgba(245,158,11,0.5));
          ">🌾</div>
        </div>

        <!-- ═══ TEXT BLOCK ═══ -->
        <div style="animation: logo-fade-in 0.9s 0.6s ease-out both;">
          <!-- KisanAI wordmark -->
          <h1 style="
            font-size: 42px;
            font-weight: 900;
            letter-spacing: -0.04em;
            line-height: 1;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #ffffff 30%, var(--accent-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          ">KisanAI</h1>

          <!-- Tagline -->
          <p style="
            font-size: 11px;
            font-weight: 600;
            color: var(--accent);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            max-width: 280px;
            margin: 0 auto 36px;
            animation: tagline-fade 1.2s 1s ease-out both;
          ">The AI Operating System of Indian Agriculture</p>
        </div>

        <!-- ═══ PROGRESS BAR ═══ -->
        <div style="
          position: absolute;
          bottom: 48px;
          left: 50%;
          transform: translateX(-50%);
          width: min(320px, 80vw);
        ">
          <!-- Label -->
          <p style="
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 10px;
            letter-spacing: 0.05em;
          ">🤖 Loading Farm Intelligence...</p>

          <!-- Track -->
          <div style="
            width: 100%;
            height: 3px;
            background: rgba(255,255,255,0.06);
            border-radius: 999px;
            overflow: hidden;
          ">
            <!-- Fill — animated via CSS -->
            <div id="splashProgressFill" style="
              height: 100%;
              width: 0%;
              border-radius: 999px;
              background: linear-gradient(90deg, var(--primary-light), var(--accent));
              animation: splash-progress 3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
              box-shadow: 0 0 8px rgba(245,158,11,0.6);
            "></div>
          </div>
        </div>

        <!-- ── Version watermark ── -->
        <div style="
          position: absolute;
          bottom: 20px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 10px;
          color: rgba(255,255,255,0.18);
          letter-spacing: 0.06em;
        ">v2.0.0 · India's #1 AgriTech AI</div>

      </div><!-- #splashRoot -->
    `;

    /* ─── Auto-navigate ─── */
    const timer = setTimeout(() => {
      if (window.location.hash === '#/splash' || window.location.hash === '') {
        window.location.hash = '#/onboarding';
      }
    }, 3200);

    /* cleanup if route changes early */
    container._splashCleanup = () => clearTimeout(timer);
  }

  if (window.KisanRouter) {
    window.KisanRouter.register('/splash', render);
  }
})();
