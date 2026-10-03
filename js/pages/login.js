// KisanAI — Premium Login Screen
(function () {

  let showPassword = false;

  /* ── one-time style injection ── */
  function injectStyles() {
    if (document.getElementById('kisanLoginStyles')) return;
    const s = document.createElement('style');
    s.id = 'kisanLoginStyles';
    s.textContent = `
      @keyframes login-fade-up {
        0%   { opacity: 0; transform: translateY(24px); }
        100% { opacity: 1; transform: translateY(0);    }
      }
      @keyframes login-particle {
        0%   { transform: translateY(0)   scale(1);   opacity: 0.6; }
        100% { transform: translateY(-90px) scale(0.6); opacity: 0;   }
      }
      .login-input {
        width: 100%;
        background: rgba(255,255,255,0.04);
        border: 1.5px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 13px 16px;
        font-size: 15px;
        color: #ffffff;
        outline: none;
        transition: border-color 0.2s, background 0.2s;
        font-family: inherit;
      }
      .login-input:focus {
        border-color: var(--accent);
        background: rgba(245,158,11,0.04);
      }
      .login-input::placeholder { color: rgba(255,255,255,0.25); }
      .social-btn {
        display: flex; align-items: center; justify-content: center; gap: 8px;
        padding: 11px 12px;
        background: rgba(255,255,255,0.04);
        border: 1.5px solid rgba(255,255,255,0.09);
        border-radius: 12px;
        color: var(--text);
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.18s;
        font-family: inherit;
      }
      .social-btn:hover  { background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.18); }
      .social-btn:active { transform: scale(0.97); background: rgba(255,255,255,0.06); }
      .eye-toggle {
        background: none; border: none; cursor: pointer;
        position: absolute; right: 14px; top: 50%;
        transform: translateY(-50%);
        color: var(--text-muted); font-size: 17px;
        padding: 4px;
        transition: color 0.2s;
      }
      .eye-toggle:hover { color: var(--accent); }
      .login-label {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
        display: block;
        margin-bottom: 6px;
        letter-spacing: 0.03em;
      }
      .or-divider {
        display: flex; align-items: center; gap: 12px;
        margin: 20px 0;
      }
      .or-divider-line { flex: 1; height: 1px; background: rgba(255,255,255,0.08); }
      .or-divider-text { font-size: 11px; color: rgba(255,255,255,0.3); font-weight: 600; letter-spacing: 0.08em; }
      #loginErrorMsg {
        display: none;
        background: rgba(239,68,68,0.12);
        border: 1px solid rgba(239,68,68,0.3);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 13px;
        color: #f87171;
        margin-bottom: 4px;
      }
      .biometric-btn:active { transform: scale(0.9) !important; }
    `;
    document.head.appendChild(s);
  }

  function render(container) {
    injectStyles();

    const particles = [
      { left: '8%',  bottom: '20%', size: 4, delay: '0s',   dur: '4s'   },
      { left: '22%', bottom: '15%', size: 3, delay: '0.6s', dur: '3.5s' },
      { left: '80%', bottom: '25%', size: 5, delay: '0.2s', dur: '4.5s' },
      { left: '92%', bottom: '18%', size: 3, delay: '1.1s', dur: '3.8s' },
    ];

    const particleHtml = particles.map(p => `
      <div style="
        position: fixed;
        left: ${p.left}; bottom: ${p.bottom};
        width: ${p.size}px; height: ${p.size}px;
        border-radius: 50%;
        background: var(--accent); opacity: 0;
        animation: login-particle ${p.dur} ${p.delay} ease-in infinite;
        pointer-events: none; z-index: 0;
      "></div>
    `).join('');

    container.innerHTML = `
      <!-- full bg -->
      <div style="
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px 16px 80px;
        position: relative;
        overflow: hidden;
        background: var(--bg);
      ">
        <!-- Sunrise glow -->
        <div style="
          position: fixed; inset: 0; pointer-events: none; z-index: 0;
          background:
            radial-gradient(ellipse at 50% 100%, rgba(245,158,11,0.14) 0%, transparent 55%),
            radial-gradient(ellipse at 0% 0%,   rgba(31,77,43,0.15)   0%, transparent 50%);
        "></div>

        ${particleHtml}

        <!-- ═══ GLASS CARD ═══ -->
        <div style="
          width: 100%; max-width: 400px;
          background: rgba(20,36,27,0.72);
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 24px;
          padding: 32px 28px 28px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06);
          position: relative; z-index: 2;
          animation: login-fade-up 0.5s ease-out both;
        ">

          <!-- ── HEADER ── -->
          <div style="text-align: center; margin-bottom: 28px;">
            <!-- Logo circle -->
            <div style="
              width: 68px; height: 68px;
              border-radius: 20px;
              background: linear-gradient(135deg, var(--primary-light), var(--primary));
              border: 1px solid rgba(255,255,255,0.12);
              display: flex; align-items: center; justify-content: center;
              font-size: 36px;
              margin: 0 auto 14px;
              box-shadow: 0 8px 24px rgba(31,77,43,0.4);
            ">🌾</div>
            <h1 style="
              font-size: 22px; font-weight: 900; color: #ffffff;
              letter-spacing: -0.03em; margin-bottom: 3px;
            ">KisanAI</h1>
            <p style="font-size: 11.5px; color: var(--text-muted); letter-spacing: 0.03em;">
              India's AI Farm Operating System
            </p>
          </div>

          <!-- ── TITLE ── -->
          <div style="margin-bottom: 22px;">
            <h2 style="font-size: 20px; font-weight: 800; color: #ffffff; margin-bottom: 4px; letter-spacing: -0.02em;">
              Welcome Back, Farmer 👋
            </h2>
            <p style="font-size: 13.5px; color: var(--text-muted);">
              Sign in to continue your farming journey
            </p>
          </div>

          <!-- ── ERROR MSG ── -->
          <div id="loginErrorMsg">⚠️ Please enter your phone/email and password.</div>

          <!-- ── FORM ── -->
          <form id="loginForm" style="display: flex; flex-direction: column; gap: 14px;">

            <!-- Phone / Email -->
            <div>
              <label class="login-label">📱 Phone Number or Email</label>
              <input
                type="text"
                id="loginUsername"
                class="login-input"
                placeholder="9876543210 or name@email.com"
                autocomplete="username"
              >
            </div>

            <!-- Password -->
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <label class="login-label" style="margin: 0;">🔒 Password</label>
                <a href="#/forgot-password" style="font-size: 12px; color: var(--accent); font-weight: 600;">Forgot?</a>
              </div>
              <div style="position: relative;">
                <input
                  type="password"
                  id="loginPassword"
                  class="login-input"
                  placeholder="••••••••••"
                  autocomplete="current-password"
                  style="padding-right: 46px;"
                >
                <button type="button" id="eyeToggle" class="eye-toggle">👁️</button>
              </div>
            </div>

            <button type="submit" class="btn btn-primary" style="
              margin-top: 6px;
              font-size: 15px; font-weight: 700;
              letter-spacing: -0.01em;
            ">Sign In to KisanAI</button>
          </form>

          <!-- ── OR DIVIDER ── -->
          <div class="or-divider">
            <div class="or-divider-line"></div>
            <span class="or-divider-text">OR CONTINUE WITH</span>
            <div class="or-divider-line"></div>
          </div>

          <!-- ── SOCIAL GRID (2 × 2) ── -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 22px;">
            <button class="social-btn" id="googleLoginBtn">🌐 Google</button>
            <button class="social-btn" id="otpRedirectBtn">📱 Phone OTP</button>
            <button class="social-btn" id="appleLoginBtn">🍎 Apple ID</button>
            <button class="social-btn" id="guestModeBtn">👤 Guest Mode</button>
          </div>

          <!-- ── BIOMETRIC ── -->
          <div style="
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 16px;
            text-align: center;
            margin-bottom: 22px;
          ">
            <p style="font-size: 12px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 14px;">
              ⚡ Quick Biometric Access
            </p>
            <div class="biometric-container">
              <div style="display: flex; flex-direction: column; align-items: center; gap: 6px;">
                <button class="biometric-btn" id="bioFingerprint" title="Fingerprint">🖐️</button>
                <span style="font-size: 10px; color: var(--text-muted);">Fingerprint</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: center; gap: 6px;">
                <button class="biometric-btn" id="bioFaceId" title="Face ID">👤</button>
                <span style="font-size: 10px; color: var(--text-muted);">Face ID</span>
              </div>
            </div>
          </div>

          <!-- ── BOTTOM LINK ── -->
          <div style="
            text-align: center;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.07);
            font-size: 13.5px;
          ">
            <span style="color: var(--text-muted);">New to KisanAI?</span>
            <a href="#/signup" style="
              color: var(--accent);
              font-weight: 700;
              margin-left: 6px;
            ">Create Account →</a>
          </div>
        </div>
      </div>
    `;

    attachListeners(container);
  }

  /* ── simulate loading button ── */
  function simulateLogin(btn, callback) {
    const orig = btn.innerHTML;
    btn.innerHTML = `<span style="display:inline-block;width:16px;height:16px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin 0.7s linear infinite;vertical-align:middle;margin-right:8px;"></span>Signing in...`;
    btn.disabled = true;
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.disabled = false;
      callback();
    }, 1400);
  }

  function attachListeners(container) {
    /* eye toggle */
    const eye = container.querySelector('#eyeToggle');
    const pwd = container.querySelector('#loginPassword');
    if (eye && pwd) {
      eye.addEventListener('click', () => {
        showPassword = !showPassword;
        pwd.type = showPassword ? 'text' : 'password';
        eye.textContent = showPassword ? '🙈' : '👁️';
      });
    }

    /* form submit */
    const form = container.querySelector('#loginForm');
    const errMsg = container.querySelector('#loginErrorMsg');
    if (form) {
      form.addEventListener('submit', e => {
        e.preventDefault();
        const u = container.querySelector('#loginUsername').value.trim();
        const p = container.querySelector('#loginPassword').value.trim();
        if (!u || !p) {
          errMsg.style.display = 'block';
          return;
        }
        errMsg.style.display = 'none';
        const btn = form.querySelector('[type=submit]');
        simulateLogin(btn, () => {
          localStorage.setItem('kisanAuth', 'true');
          window.location.hash = '#/permissions';
        });
      });
    }

    /* Google */
    const googleBtn = container.querySelector('#googleLoginBtn');
    if (googleBtn) {
      googleBtn.addEventListener('click', () => {
        googleBtn.textContent = '⏳ Connecting...';
        setTimeout(() => {
          localStorage.setItem('kisanAuth', 'true');
          alert('✅ Google Sign-In simulated successfully!');
          window.location.hash = '#/permissions';
        }, 1200);
      });
    }

    /* Apple */
    const appleBtn = container.querySelector('#appleLoginBtn');
    if (appleBtn) {
      appleBtn.addEventListener('click', () => {
        appleBtn.textContent = '⏳ Connecting...';
        setTimeout(() => {
          localStorage.setItem('kisanAuth', 'true');
          alert('✅ Apple Sign-In simulated successfully!');
          window.location.hash = '#/permissions';
        }, 1200);
      });
    }

    /* Phone OTP */
    const otpBtn = container.querySelector('#otpRedirectBtn');
    if (otpBtn) {
      otpBtn.addEventListener('click', () => {
        window.location.hash = '#/otp';
      });
    }

    /* Guest */
    const guestBtn = container.querySelector('#guestModeBtn');
    if (guestBtn) {
      guestBtn.addEventListener('click', () => {
        localStorage.setItem('kisanAuth', 'guest');
        window.location.hash = '#/';
      });
    }

    /* Biometric – fingerprint */
    const bioFp = container.querySelector('#bioFingerprint');
    if (bioFp) {
      bioFp.addEventListener('click', () => {
        bioFp.style.animation = 'pulse 0.8s ease-in-out 2';
        bioFp.textContent = '🔄';
        setTimeout(() => {
          bioFp.textContent = '✅';
          setTimeout(() => {
            localStorage.setItem('kisanAuth', 'true');
            window.location.hash = '#/';
          }, 600);
        }, 1000);
      });
    }

    /* Biometric – face ID */
    const bioFace = container.querySelector('#bioFaceId');
    if (bioFace) {
      bioFace.addEventListener('click', () => {
        bioFace.textContent = '🔄';
        setTimeout(() => {
          bioFace.textContent = '✅';
          setTimeout(() => {
            localStorage.setItem('kisanAuth', 'true');
            window.location.hash = '#/';
          }, 600);
        }, 1000);
      });
    }
  }

  if (window.KisanRouter) {
    window.KisanRouter.register('/login', render);
  }
})();
