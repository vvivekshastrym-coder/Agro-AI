// ═══════════════════════════════════════════════════════════
// AGRO AI — AGRO GPT v2.0
// Full-Featured Single Source of Truth Backend Chat Integration
// Robust Voice Speech-to-Text & Interactive Voice Mode
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let messages = [
    { role: 'assistant', content: '🌾 Namaste! I am Agro GPT, your AI farming companion. How can I help with your crops or farm today?' }
  ];
  let isListening = false;
  let isThinking = false;
  let isSpeaking = false;
  let interactiveVoiceMode = false;
  let currentSpeakingUtterance = null;
  let conversationId = null;
  let currentAudioContext = null;
  let recognitionInstance = null;
  let activeDiagnosisContext = null;

  // ── Preload Voices ──────────────────────────────────────────
  let systemVoices = [];
  if ('speechSynthesis' in window) {
    systemVoices = window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      systemVoices = window.speechSynthesis.getVoices();
    };
  }

  // ── Audio Context Unlocker ──────────────────────────────────
  function unlockAudio() {
    try {
      if (!currentAudioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) currentAudioContext = new AudioCtx();
      }
      if (currentAudioContext && currentAudioContext.state === 'suspended') {
        currentAudioContext.resume();
      }
      if ('speechSynthesis' in window && window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }
    } catch (e) {
      console.warn('Audio unlock warning:', e);
    }
  }

  function render(container) {
    const currentLang = (window.KisanI18n && typeof window.KisanI18n.getCurrentLang === 'function') 
      ? window.KisanI18n.getCurrentLang() 
      : (window.KisanI18n && typeof window.KisanI18n.getCurrentLanguage === 'function' ? window.KisanI18n.getCurrentLanguage() : 'en');

    container.innerHTML = `
      <div style="display: flex; flex-direction: column; height: calc(100vh - 120px);">
        <!-- Top Title & Language Row -->
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
          <div>
            <h1 style="font-size: 20px; font-weight: 900; margin: 0; display: flex; align-items: center; gap: 6px;">
              🤖 Agro GPT
            </h1>
            <span style="font-size: 11px; color: var(--accent); font-weight: 700;">SINGLE SOURCE OF TRUTH AI</span>
          </div>

          <div style="display: flex; align-items: center; gap: 8px;">
            <!-- Start Interactive Voice Mode Button -->
            <button id="startInteractiveVoiceBtn" class="btn btn-primary btn-sm" style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: 12px; border-radius: 20px; box-shadow: 0 0 15px rgba(34, 197, 94, 0.3);">
              🎙️ Interactive Voice
            </button>

            <!-- Language Selector -->
            <select id="langSelect" style="padding: 5px 8px; border-radius: 10px; font-size: 12px; background: var(--surface-1); color: var(--text); border: 1px solid var(--border);">
              <option value="en" ${currentLang === 'en' ? 'selected' : ''}>English</option>
              <option value="hi" ${currentLang === 'hi' ? 'selected' : ''}>Hindi (हिंदी)</option>
              <option value="kn" ${currentLang === 'kn' ? 'selected' : ''}>Kannada (ಕನ್ನಡ)</option>
              <option value="te" ${currentLang === 'te' ? 'selected' : ''}>Telugu (తెలుగు)</option>
              <option value="ta" ${currentLang === 'ta' ? 'selected' : ''}>Tamil (தமிழ்)</option>
              <option value="mr" ${currentLang === 'mr' ? 'selected' : ''}>Marathi (मराठी)</option>
            </select>
          </div>
        </div>

        ${activeDiagnosisContext ? `
          <div style="margin-bottom: 10px; padding: 8px 12px; background: var(--surface-2); border-left: 3px solid var(--accent); border-radius: 8px; font-size: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              🌿 <strong>Active Diagnosis Attached:</strong> ${escapeHtml(activeDiagnosisContext.crop || 'Crop')} — ${escapeHtml(activeDiagnosisContext.disease || 'Condition')}
            </div>
            <button id="clearContextBtn" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 12px;">✕</button>
          </div>
        ` : ''}

        <!-- Chat History Window -->
        <div id="chatHistory" style="flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; background: var(--surface-1); border-radius: 16px; border: 1px solid var(--border); margin-bottom: 12px;">
          ${messages.map((m, idx) => renderBubble(m, idx)).join('')}
          ${isThinking ? `
            <div style="display: flex; gap: 8px; align-items: center; background: var(--surface-2); padding: 10px 14px; border-radius: 14px; width: fit-content;">
              <div class="spinner spinner-sm"></div>
              <span style="font-size: 13px; color: var(--text-muted);">Agro GPT is analyzing farm data...</span>
            </div>
          ` : ''}
        </div>

        <!-- Input Control Bar -->
        <div style="display: flex; gap: 8px; align-items: center;">
          <button id="micBtn" title="Hold or Click to Speak" style="background: ${isListening ? '#EF4444' : 'var(--surface-2)'}; color: ${isListening ? '#fff' : 'var(--text)'}; border: 1px solid var(--border); width: 44px; height: 44px; border-radius: 50%; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; shrink: 0; transition: all 0.2s;">
            ${isListening ? '🎙️' : '🎤'}
          </button>
          <input type="text" id="chatInput" placeholder="Ask in your language (voice or text)..." style="flex: 1; height: 44px; border-radius: 22px; padding: 0 16px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 14px;">
          <button id="sendBtn" class="btn btn-primary" style="height: 44px; width: 44px; border-radius: 50%; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 18px;">➔</button>
        </div>
      </div>

      <!-- Interactive Voice Mode Overlay Modal -->
      <div id="interactiveVoiceModal" style="display: ${interactiveVoiceMode ? 'flex' : 'none'};" class="voice-mode-overlay">
        <div class="voice-mode-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 20px;">🤖</span>
            <div>
              <div style="font-size: 15px; font-weight: 800; color: var(--text);">Agro GPT Voice Assistant</div>
              <div style="font-size: 11px; color: var(--text-muted);">Hands-Free Interactive Mode</div>
            </div>
          </div>
          <button id="closeVoiceModeBtn" style="background: rgba(255,255,255,0.1); border: none; color: #fff; width: 36px; height: 36px; border-radius: 50%; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center;">✕</button>
        </div>

        <div class="voice-mode-body">
          <div class="voice-radar-container">
            <div class="voice-radar-ring ${isListening ? 'listening' : ''}"></div>
            <div class="voice-radar-ring ${isListening ? 'listening' : ''}"></div>
            <div class="voice-radar-ring ${isListening ? 'listening' : ''}"></div>
            <button id="voiceModalMicBtn" class="voice-main-mic-btn ${isListening ? 'listening' : isSpeaking ? 'speaking' : isThinking ? 'thinking' : ''}">
              ${isThinking ? '⏳' : isSpeaking ? '🔊' : isListening ? '🎙️' : '🎤'}
            </button>
          </div>

          <!-- State Label Badge -->
          <div style="margin-bottom: 8px;">
            ${isThinking ? `
              <span class="badge badge-warning" style="font-size: 13px; padding: 6px 14px;">● Analyzing with Backend AI...</span>
            ` : isSpeaking ? `
              <span class="badge badge-primary" style="font-size: 13px; padding: 6px 14px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4);">● Agro GPT Speaking (Tap to interrupt)</span>
            ` : isListening ? `
              <span class="badge badge-success" style="font-size: 13px; padding: 6px 14px;">● Listening... Speak now</span>
            ` : `
              <span class="badge" style="font-size: 13px; padding: 6px 14px; background: var(--surface-2); color: var(--text);">● Tap mic to speak</span>
            `}
          </div>

          <!-- Waveform Visualizer -->
          <div class="voice-wave-container ${isSpeaking ? 'speaking' : ''}">
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
            <div class="voice-wave-bar"></div>
          </div>

          <!-- Live Transcript Output Box -->
          <div id="voiceTranscriptBox" class="voice-transcript-box">
            ${messages.length > 0 ? escapeHtml(messages[messages.length - 1].content).replace(/\n/g, '<br>') : 'Speak your question about crops, diseases, fertilizers, or prices...'}
          </div>
        </div>

        <div style="display: flex; justify-content: space-around; align-items: center; border-top: 1px solid var(--border); padding-top: 16px;">
          <button id="stopVoiceSpeechBtn" class="btn btn-outline btn-sm" style="font-size: 13px; padding: 8px 16px;">
            ${isSpeaking ? '⏹️ Stop Speaking' : isListening ? '⏹️ Pause Listening' : '🎙️ Start Listening'}
          </button>
          <button id="exitVoiceModeBtn" class="btn btn-primary btn-sm" style="font-size: 13px; padding: 8px 16px;">
            💬 Switch to Text Chat
          </button>
        </div>
      </div>
    `;

    scrollToBottom(container);
    attachListeners(container);
  }

  function renderBubble(m, idx) {
    const isUser = m.role === 'user';
    return `
      <div style="display: flex; justify-content: ${isUser ? 'flex-end' : 'flex-start'};">
        <div style="max-width: 84%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.5; ${isUser ? 'background: var(--accent); color: #fff; border-bottom-right-radius: 4px;' : 'background: var(--surface-2); color: var(--text); border-bottom-left-radius: 4px; border: 1px solid var(--border);'}">
          ${escapeHtml(m.content).replace(/\n/g, '<br>')}
          ${!isUser ? `
            <div style="margin-top: 8px; display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 10px; color: var(--text-muted);">Agro AI Verified</span>
              <button class="speak-bubble-btn btn btn-sm" data-idx="${idx}" data-text="${escapeHtml(m.content)}" style="background: rgba(255,255,255,0.06); border: 1px solid var(--border); font-size: 11px; padding: 3px 8px; border-radius: 12px; cursor: pointer; color: var(--text);">
                🔊 Listen
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  function attachListeners(container) {
    const chatInput = container.querySelector('#chatInput');
    const sendBtn = container.querySelector('#sendBtn');
    const micBtn = container.querySelector('#micBtn');
    const langSelect = container.querySelector('#langSelect');
    const startInteractiveVoiceBtn = container.querySelector('#startInteractiveVoiceBtn');
    const closeVoiceModeBtn = container.querySelector('#closeVoiceModeBtn');
    const exitVoiceModeBtn = container.querySelector('#exitVoiceModeBtn');
    const voiceModalMicBtn = container.querySelector('#voiceModalMicBtn');
    const stopVoiceSpeechBtn = container.querySelector('#stopVoiceSpeechBtn');
    const clearContextBtn = container.querySelector('#clearContextBtn');

    if (clearContextBtn) {
      clearContextBtn.onclick = () => {
        activeDiagnosisContext = null;
        render(container);
      };
    }

    const sendMessage = async (customText = null) => {
      unlockAudio();
      const text = customText || (chatInput ? chatInput.value.trim() : '');
      if (!text || isThinking) return;

      messages.push({ role: 'user', content: text });
      if (chatInput) chatInput.value = '';
      isThinking = true;
      render(container);

      try {
        const lang = langSelect ? langSelect.value : 'en';
        const contextPayload = activeDiagnosisContext ? { diagnosis_report_id: activeDiagnosisContext.report_id } : null;
        
        const res = await window.KisanAPI.agroGptChat(text, conversationId, lang, 'default_farmer', contextPayload);
        conversationId = res.conversation_id;
        messages.push({ role: 'assistant', content: res.reply });

        // Auto Text-to-Speech synthesis
        speakText(res.reply, lang, () => {
          // Callback after speech ends
          if (interactiveVoiceMode) {
            // In interactive hands-free mode, automatically resume listening for next question
            setTimeout(() => {
              if (interactiveVoiceMode && !isSpeaking && !isThinking) {
                startSpeechRecognition(container);
              }
            }, 600);
          }
        });
      } catch (err) {
        const errorMsg = err.message || 'Unable to connect to Agro GPT backend.';
        messages.push({ role: 'assistant', content: `⚠️ Error: ${errorMsg}` });
        if (interactiveVoiceMode) {
          speakText('Sorry, there was an issue connecting to the AI backend. Please retry.', 'en');
        }
      } finally {
        isThinking = false;
        render(container);
      }
    };

    if (sendBtn) sendBtn.onclick = () => sendMessage();
    if (chatInput) {
      chatInput.onkeydown = (e) => {
        if (e.key === 'Enter') sendMessage();
      };
    }

    if (langSelect) {
      langSelect.onchange = () => {
        if (window.KisanI18n) window.KisanI18n.setLanguage(langSelect.value);
        render(container);
      };
    }

    // ── Interactive Voice Mode Buttons ───────────────────────────
    if (startInteractiveVoiceBtn) {
      startInteractiveVoiceBtn.onclick = () => {
        unlockAudio();
        stopSpeech();
        interactiveVoiceMode = true;
        render(container);
        startSpeechRecognition(container);
      };
    }

    if (closeVoiceModeBtn) {
      closeVoiceModeBtn.onclick = () => {
        stopSpeech();
        stopSpeechRecognition();
        interactiveVoiceMode = false;
        render(container);
      };
    }

    if (exitVoiceModeBtn) {
      exitVoiceModeBtn.onclick = () => {
        stopSpeech();
        stopSpeechRecognition();
        interactiveVoiceMode = false;
        render(container);
      };
    }

    if (voiceModalMicBtn) {
      voiceModalMicBtn.onclick = () => {
        unlockAudio();
        if (isSpeaking) {
          stopSpeech();
          startSpeechRecognition(container);
        } else if (isListening) {
          stopSpeechRecognition();
          render(container);
        } else {
          startSpeechRecognition(container);
        }
      };
    }

    if (stopVoiceSpeechBtn) {
      stopVoiceSpeechBtn.onclick = () => {
        unlockAudio();
        if (isSpeaking) {
          stopSpeech();
          render(container);
        } else if (isListening) {
          stopSpeechRecognition();
          render(container);
        } else {
          startSpeechRecognition(container);
        }
      };
    }

    // ── Regular Mic Button ───────────────────────────────────────
    if (micBtn) {
      micBtn.onclick = () => {
        unlockAudio();
        if (isListening) {
          stopSpeechRecognition();
          render(container);
        } else {
          startSpeechRecognition(container, (transcript) => {
            if (chatInput) chatInput.value = transcript;
            sendMessage(transcript);
          });
        }
      };
    }

    // ── Speak Bubble Buttons ─────────────────────────────────────
    container.querySelectorAll('.speak-bubble-btn').forEach(btn => {
      btn.onclick = () => {
        unlockAudio();
        const text = btn.getAttribute('data-text');
        if (isSpeaking) {
          stopSpeech();
          btn.innerHTML = '🔊 Listen';
          render(container);
        } else {
          btn.innerHTML = '⏹️ Stop';
          speakText(text, langSelect ? langSelect.value : 'en', () => {
            btn.innerHTML = '🔊 Listen';
            render(container);
          });
        }
      };
    });
  }

  // ── Speech-to-Text Recognition ───────────────────────────────
  function startSpeechRecognition(container, onCompleteCallback = null) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported on this browser. Please use Chrome, Edge, or Safari.');
      return;
    }

    stopSpeech();
    stopSpeechRecognition();

    try {
      recognitionInstance = new SpeechRecognition();
      const langCode = getLangCode(document.querySelector('#langSelect')?.value || 'en');
      recognitionInstance.lang = langCode;
      recognitionInstance.interimResults = true;
      recognitionInstance.maxAlternatives = 1;

      let finalTranscript = '';

      recognitionInstance.onstart = () => {
        isListening = true;
        render(container);
      };

      recognitionInstance.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        const display = finalTranscript || interim;
        const box = container.querySelector('#voiceTranscriptBox');
        if (box && display) {
          box.innerHTML = `<em>"${escapeHtml(display)}"</em>`;
        }
        const chatInput = container.querySelector('#chatInput');
        if (chatInput && display) chatInput.value = display;
      };

      recognitionInstance.onerror = (e) => {
        console.warn('Speech recognition error:', e.error);
        isListening = false;
        render(container);
      };

      recognitionInstance.onend = () => {
        isListening = false;
        render(container);

        const textToSubmit = finalTranscript.trim() || document.querySelector('#chatInput')?.value?.trim();
        if (textToSubmit) {
          if (onCompleteCallback) {
            onCompleteCallback(textToSubmit);
          } else {
            // Trigger send in container
            const chatInput = container.querySelector('#chatInput');
            if (chatInput) chatInput.value = textToSubmit;
            const sendBtn = container.querySelector('#sendBtn');
            if (sendBtn) sendBtn.click();
          }
        }
      };

      recognitionInstance.start();
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      isListening = false;
      render(container);
    }
  }

  function stopSpeechRecognition() {
    if (recognitionInstance) {
      try { recognitionInstance.stop(); } catch(e){}
      recognitionInstance = null;
    }
    isListening = false;
  }

  function stopSpeech() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    isSpeaking = false;
    currentSpeakingUtterance = null;
  }

  // ── Bulletproof Speech Synthesis (TTS) ────────────────────────
  function speakText(rawText, lang, onEndCallback = null) {
    if (!('speechSynthesis' in window)) {
      console.warn('SpeechSynthesis not supported.');
      if (onEndCallback) onEndCallback();
      return;
    }

    unlockAudio();
    stopSpeech();

    // 1. Clean markdown and special symbols for clean speech
    const cleanSpeech = rawText
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/#{1,6}\s?/g, '')
      .replace(/`{1,3}.*?`{1,3}/gs, '')
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
      .replace(/[🌿🌾💊💡⚠️⏰📈🔬🤖●·\-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanSpeech) {
      if (onEndCallback) onEndCallback();
      return;
    }

    const targetLang = getLangCode(lang || 'en');
    const utterance = new SpeechSynthesisUtterance(cleanSpeech);
    utterance.lang = targetLang;
    utterance.rate = 0.95; // Clear natural pacing
    utterance.pitch = 1.0;

    // 2. Select appropriate system voice
    if (systemVoices.length === 0) {
      systemVoices = window.speechSynthesis.getVoices();
    }

    const matchedVoice = systemVoices.find(v => v.lang === targetLang || v.lang === targetLang.replace('-', '_')) ||
      systemVoices.find(v => v.lang.startsWith(targetLang.split('-')[0])) ||
      systemVoices.find(v => v.lang.includes('IN') || v.lang.includes('en'));

    if (matchedVoice) {
      utterance.voice = matchedVoice;
    }

    // 3. Keep-alive heartbeat for Chrome SpeechSynthesis bug
    let resumeInterval = null;

    utterance.onstart = () => {
      isSpeaking = true;
      currentSpeakingUtterance = utterance;
      resumeInterval = setInterval(() => {
        if (window.speechSynthesis.speaking) {
          window.speechSynthesis.pause();
          window.speechSynthesis.resume();
        }
      }, 4000);
      const modal = document.querySelector('#interactiveVoiceModal');
      if (modal) {
        const barContainer = modal.querySelector('.voice-wave-container');
        if (barContainer) barContainer.classList.add('speaking');
        const micBtn = modal.querySelector('#voiceModalMicBtn');
        if (micBtn) {
          micBtn.className = 'voice-main-mic-btn speaking';
          micBtn.innerHTML = '🔊';
        }
      }
    };

    utterance.onend = () => {
      isSpeaking = false;
      currentSpeakingUtterance = null;
      if (resumeInterval) clearInterval(resumeInterval);
      const modal = document.querySelector('#interactiveVoiceModal');
      if (modal) {
        const barContainer = modal.querySelector('.voice-wave-container');
        if (barContainer) barContainer.classList.remove('speaking');
      }
      if (onEndCallback) onEndCallback();
    };

    utterance.onerror = (err) => {
      console.warn('Speech synthesis error:', err);
      isSpeaking = false;
      currentSpeakingUtterance = null;
      if (resumeInterval) clearInterval(resumeInterval);
      if (onEndCallback) onEndCallback();
    };

    window.speechSynthesis.speak(utterance);
  }

  function getLangCode(lang) {
    const map = { en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN', te: 'te-IN', ta: 'ta-IN', mr: 'mr-IN' };
    return map[lang] || 'en-IN';
  }

  function scrollToBottom(container) {
    setTimeout(() => {
      const history = container.querySelector('#chatHistory');
      if (history) history.scrollTop = history.scrollHeight;
    }, 50);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Global helper to attach diagnosis context from diagnosis page
  window.attachKisanGptDiagnosisContext = function (diagReport) {
    activeDiagnosisContext = diagReport;
    if (window.KisanRouter) window.KisanRouter.navigate('/kisan-gpt');
  };

  if (window.KisanRouter) window.KisanRouter.register('/kisan-gpt', render);
})();

