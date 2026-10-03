// KisanAI OTP Verification Page Renderer
(function() {
  let timerVal = 30;
  let timerInterval = null;

  function render(container) {
    let contentHtml = `
      <div class="splash-container" style="justify-content: center; padding: 20px; min-height: 80vh;">
        <div class="sunrise-bg"></div>

        <div class="glass-card" style="width: 100%; max-width: 360px; padding: 24px 20px; text-align: left;">
          <h2 style="font-size: 20px; margin-bottom: 4px; color: #ffffff;">Enter Verification Code</h2>
          <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin-bottom: 20px;">
            We sent a 4-digit verification code to your registered mobile number.
          </p>

          <!-- Code inputs -->
          <div class="otp-inputs">
            <input type="text" class="otp-box" maxlength="1" data-idx="0" pattern="[0-9]" inputmode="numeric">
            <input type="text" class="otp-box" maxlength="1" data-idx="1" pattern="[0-9]" inputmode="numeric">
            <input type="text" class="otp-box" maxlength="1" data-idx="2" pattern="[0-9]" inputmode="numeric">
            <input type="text" class="otp-box" maxlength="1" data-idx="3" pattern="[0-9]" inputmode="numeric">
          </div>

          <div style="text-align: center; margin-bottom: 20px;">
            <button class="btn btn-outline" id="otpAutoFillBtn" style="font-size: 12.5px; width: auto; padding: 4px 12px; min-height: unset; border-color: var(--accent); color: var(--accent);">
              📲 Auto-Detect OTP (Simulate)
            </button>
          </div>

          <button class="btn btn-primary" id="otpVerifyBtn" style="margin-bottom: 16px;">Verify Code</button>

          <!-- Resend options & timer -->
          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 14px; font-size: 12.5px;">
            <div>
              ${timerVal > 0 ? `
                <span style="color: var(--text-muted);">Resend in <strong style="color: #ffffff;">${timerVal}s</strong></span>
              ` : `
                <a href="#/otp" id="otpResendLink" style="color: var(--accent); font-weight: bold;">Resend Code</a>
              `}
            </div>
            <button class="btn btn-outline" id="otpVoiceBtn" style="width: auto; padding: 4px 10px; min-height: unset; font-size: 11.5px;">🗣️ Voice OTP</button>
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
          render(container); // Re-render to show resend link
        }
      }
    }, 1000);
  }

  function attachListeners(container) {
    // Focus chaining
    const boxes = container.querySelectorAll('.otp-box');
    boxes.forEach((box, idx) => {
      box.addEventListener('input', (e) => {
        if (e.target.value.length === 1 && idx < 3) {
          boxes[idx + 1].focus();
        }
      });
      box.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && e.target.value.length === 0 && idx > 0) {
          boxes[idx - 1].focus();
        }
      });
    });

    const autofill = container.querySelector('#otpAutoFillBtn');
    if (autofill) {
      autofill.addEventListener('click', () => {
        const otpCode = ['5', '9', '8', '3'];
        boxes.forEach((box, idx) => {
          box.value = otpCode[idx];
        });
        setTimeout(() => {
          verifyOTP(container);
        }, 300);
      });
    }

    const verifyBtn = container.querySelector('#otpVerifyBtn');
    if (verifyBtn) {
      verifyBtn.addEventListener('click', () => {
        verifyOTP(container);
      });
    }

    const voiceBtn = container.querySelector('#otpVoiceBtn');
    if (voiceBtn) {
      voiceBtn.addEventListener('click', () => {
        alert("KisanAI Voice System: 'Your verification code is 5 9 8 3. I repeat: 5 9 8 3.'");
      });
    }

    const resendLink = container.querySelector('#otpResendLink');
    if (resendLink) {
      resendLink.addEventListener('click', (e) => {
        e.preventDefault();
        timerVal = 30;
        alert("Verification code resent successfully!");
        render(container);
      });
    }
  }

  function verifyOTP(container) {
    const boxes = container.querySelectorAll('.otp-box');
    let enteredCode = '';
    boxes.forEach(box => enteredCode += box.value);

    if (enteredCode.length < 4) {
      alert("Please enter the complete 4-digit code.");
      return;
    }

    if (timerInterval) clearInterval(timerInterval);

    // Show success animation state
    container.innerHTML = `
      <div class="splash-container" style="justify-content: center; padding: 20px; min-height: 80vh;">
        <div class="sunrise-bg"></div>
        <div class="glass-card" style="width: 100%; max-width: 360px; padding: 32px 20px; text-align: center; border-color: rgba(34, 197, 94, 0.3);">
          <div style="width: 64px; height: 64px; background: rgba(34,197,94,0.15); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px auto; color: #22c55e; font-size: 32px;">✓</div>
          <h2 style="font-size: 20px; margin-bottom: 6px; color: #ffffff;">Verification Success!</h2>
          <p style="font-size: 13px; color: var(--text-muted); line-height: 1.4; margin-bottom: 20px;">
            Your mobile number has been authenticated.
          </p>
        </div>
      </div>
    `;

    setTimeout(() => {
      window.location.hash = '#/permissions';
    }, 1500);
  }

  // Register in Router
  if (window.KisanRouter) {
    window.KisanRouter.register('/otp', render);
  }
})();
