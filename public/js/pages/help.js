// ═══════════════════════════════════════════════════════════
// AGRO AI — HELP & SUPPORT v2.0
// Single Source of Truth Backend Integration
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  let chatMessages = [
    { sender: 'bot', text: '👋 Hello! I am the KisanAI Support Assistant powered by Agro GPT. How can I help you navigate the app or answer your farming questions?' }
  ];

  function render(container) {
    container.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h1 style="font-size: 22px; font-weight: 900; margin-bottom: 6px;">❓ Help & Support</h1>
        <p style="font-size: 13px; color: var(--text-muted);">24/7 AI-powered farmer support assistant & FAQs</p>
      </div>

      <!-- Live Chat Container -->
      <div class="glass-card" style="padding: 16px; margin-bottom: 20px;">
        <div style="font-size: 14px; font-weight: 800; margin-bottom: 12px;">💬 Live AI Assistant Chat</div>
        <div id="helpChatBox" style="max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; padding-right: 4px;">
          ${chatMessages.map(m => `
            <div style="display: flex; justify-content: ${m.sender === 'user' ? 'flex-end' : 'flex-start'};">
              <div style="max-width: 85%; padding: 10px 14px; border-radius: 14px; font-size: 13px; ${m.sender === 'user' ? 'background: var(--accent); color: #fff;' : 'background: var(--surface-2); color: var(--text); border: 1px solid var(--border);'}">
                ${m.text}
              </div>
            </div>
          `).join('')}
        </div>

        <div style="display: flex; gap: 8px;">
          <input type="text" id="helpChatInput" placeholder="Type your question..." style="flex:1; padding: 10px 14px; border-radius: 20px; border: 1px solid var(--border); background: var(--surface-2); color: var(--text); font-size: 13px;">
          <button id="sendHelpBtn" class="btn btn-primary" style="border-radius: 20px; padding: 0 16px;">Send</button>
        </div>
      </div>
    `;

    attachListeners(container);
  }

  function attachListeners(container) {
    const input = container.querySelector('#helpChatInput');
    const sendBtn = container.querySelector('#sendHelpBtn');

    const handleSend = async () => {
      const query = input.value.trim();
      if (!query) return;

      chatMessages.push({ sender: 'user', text: query });
      input.value = '';
      render(container);

      try {
        const res = await window.KisanAPI.agroGptChat(query);
        chatMessages.push({ sender: 'bot', text: res.reply });
      } catch (err) {
        chatMessages.push({ sender: 'bot', text: '⚠️ Service temporarily unavailable. Please try again.' });
      }
      render(container);
    };

    if (sendBtn) sendBtn.onclick = handleSend;
    if (input) {
      input.onkeydown = (e) => {
        if (e.key === 'Enter') handleSend();
      };
    }
  }

  if (window.KisanRouter) window.KisanRouter.register('/help', render);
})();
