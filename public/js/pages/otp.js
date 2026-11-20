// KisanAI OTP Verification Page Renderer - Production
(function() {
  let timerVal = 60;
  let timerInterval = null;

  function render(container) {
    let contentHtml = `
      <div class="splash-container" style="justify-content: center; padding: 20px; min-height: 80vh;">
        <div class="sunrise-bg"></div>

        <div class="glass-card" style="width: 100%; max-width: 360px; padding: 24px 20px; text-align: left;">
          <h2 style="font-size: 20px; margin-bottom: 4px; color: #ffffff;">Enter Verification Code</h2>
          <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin-bottom: 20px;">
            Enter the 6-digit SMS verification code sent to your registered mobile number.
          </p>

          <!-- Code inputs -->
          <div class="otp-inputs" style="display:flex;gap:8px;justify-content:center;margin-bottom:20px;">
            <input type="text" class="otp-box" maxlength="1" data-idx="0" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
            <input type="text" class="otp-box" maxlength="1" data-idx="1" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
            <input type="text" class="otp-box" maxlength="1" data-idx="2" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
            <input type="text" class="otp-box" maxlength="1" data-idx="3" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
            <input type="text" class="otp-box" maxlength="1" data-idx="4" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
            <input type="text" class="otp-box" maxlength="1" data-idx="5" pattern="[0-9]" inputmode="numeric" style="width:40px;height:48px;font-size:20px;text-align:center;border-radius:10px;border:1.5px solid var(--border);background:var(--bg-elevated);color:#fff;">
          </div>

          <button class="btn btn-primary" id="otpVerifyBtn" style="width:100%;margin-bottom: 16px;">Verify Code</button>

          <!-- Resend options & timer -->
          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 14px; font-size: 12.5px;">
            <div>
              ${timerVal > 0 ? `
                <span style="color: var(--text-muted);">Resend in <strong style="color: #ffffff;">${timerVal}s</strong></span>
              ` : `
                <a href="#/otp" id="otpResendLink" style="color: var(--accent); font-weight: bold; cursor: pointer;">Resend SMS Code</a>
              `}
            </div>
            <a href="#/login" style="color: var(--text-muted); font-size: 12px; text-decoration: none;">Change Number</a>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = contentHtml;
    attachListeners(container);
    startTimer(container);
  }

  function startTimer(container) {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (timerVal > 0) {
        timerVal--;
        const timerSpan = container.querySelector('strong');
        if (timerSpan) {
          timerSpan.textContent = `${timerVal}s`;
        }
        if (timerVal === 0) {
          clearInterval(timerInterval);
          render(container);
        }
      }
    }, 1000);
  }

  function attachListeners(container) {
    const boxes = container.querySelectorAll('.otp-box');
    boxes.forEach((box, idx) => {
      box.addEventListener('input', (e) => {
        if (e.target.value.length === 1 && idx < 5) {
          boxes[idx + 1].focus();
        }
      });
      box.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && e.target.value.length === 0 && idx > 0) {
          boxes[idx - 1].focus();
        }
      });
      box.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '').slice(0, 6);
        text.split('').forEach((ch, i) => {
          if (boxes[i]) boxes[i].value = ch;
        });
        if (text.length === 6) {
          verifyOTP(container);
        }
      });
    });

    const verifyBtn = container.querySelector('#otpVerifyBtn');
    if (verifyBtn) {
      verifyBtn.addEventListener('click', () => {
        verifyOTP(container);
      });
    }

    const resendLink = container.querySelector('#otpResendLink');
    if (resendLink) {
      resendLink.addEventListener('click', (e) => {
        e.preventDefault();
        timerVal = 60;
        if (window.resendOtp) {
          window.resendOtp();
        }
        render(container);
      });
    }
  }

  async function verifyOTP(container) {
    const boxes = container.querySelectorAll('.otp-box');
    let enteredCode = '';
    boxes.forEach(box => enteredCode += box.value);

    if (enteredCode.length < 6) {
      alert("Please enter the complete 6-digit code.");
      return;
    }

    if (timerInterval) clearInterval(timerInterval);

    const input = document.getElementById('otpInput');
    if (input) input.value = enteredCode;
    if (window.verifyOtp) {
      window.verifyOtp();
    }
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/otp', render);
  }
})();
