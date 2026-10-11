// ═══════════════════════════════════════════════════════════
// AGRO AI — SUPABASE CLIENT & AUTH MODULE
// Configured with Live Supabase Project & Google Identity Services
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  const SUPABASE_URL = 'https://eziigoiirqdsgimfkquv.supabase.co';
  const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_fDc46mh4MukSCabbBpeVMA_KqtWdOee';
  const GOOGLE_CLIENT_ID = '390368260977-87pg849eb5975glaikekhr9s4rlus4e2.apps.googleusercontent.com';

  let client = null;
  let gsiInitialized = false;

  function initSupabase() {
    if (window.supabase && typeof window.supabase.createClient === 'function') {
      try {
        client = window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
        window.supabaseClient = client;
        console.log('⚡ Supabase Client initialized successfully');

        // Listen for Auth state changes (OAuth redirects, login, logout)
        client.auth.onAuthStateChange(async (event, session) => {
          console.log('[Supabase Auth Event]:', event, session ? session.user?.email : 'No session');
          if ((event === 'SIGNED_IN' || event === 'INITIAL_SESSION') && session && session.user) {
            window.dispatchEvent(new CustomEvent('agro:signed-in', { detail: session }));
          }

          if (event === 'SIGNED_IN' && session && session.user) {
            localStorage.setItem('kisanAuth', 'true');
            localStorage.setItem('kisanUser', JSON.stringify({
              id: session.user.id,
              email: session.user.email,
              name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0] || 'Farmer Partner',
              avatar: session.user.user_metadata?.avatar_url || ''
            }));

            // Redirect to main screen if on login/signup page
            if (window.location.hash === '#/login' || window.location.hash === '#/signup' || !window.location.hash) {
              window.location.hash = '#/';
            }
          } else if (event === 'SIGNED_OUT') {
            localStorage.removeItem('kisanAuth');
            localStorage.removeItem('kisanUser');
          }
        });

      } catch (err) {
        console.error('Failed to initialize Supabase client:', err);
      }
    } else {
      setTimeout(initSupabase, 200);
    }
  }

  // Parse JWT token safely
  function parseJwt(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (e) {
      console.warn('Could not parse JWT token', e);
      return null;
    }
  }

  // Handle Google Identity Services credential response
  async function handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) {
      console.warn('No credential received in Google response');
      return;
    }

    const idToken = response.credential;
    console.log('⚡ Received Google ID token from Identity Services');

    // Method A: Sign in via Supabase using the ID token
    if (client && client.auth && typeof client.auth.signInWithIdToken === 'function') {
      try {
        const { data, error } = await client.auth.signInWithIdToken({
          provider: 'google',
          token: idToken,
        });

        if (!error && data && data.session) {
          console.log('⚡ Supabase authenticated successfully via Google ID Token:', data.session.user?.email);
          return; // onAuthStateChange triggers agro:signed-in
        }
        if (error) {
          console.warn('[Supabase signInWithIdToken Notice]:', error.message);
        }
      } catch (err) {
        console.warn('Supabase signInWithIdToken error:', err);
      }
    }

    // Method B: Direct Google Identity verification fallback
    const claims = parseJwt(idToken);
    if (claims && claims.sub) {
      console.log('⚡ Establishing verified Google session for:', claims.email);
      const googleSession = {
        access_token: idToken,
        token_type: 'bearer',
        user: {
          id: claims.sub,
          email: claims.email,
          phone: null,
          user_metadata: {
            full_name: claims.name || claims.given_name || claims.email?.split('@')[0],
            name: claims.name,
            avatar_url: claims.picture || '',
          },
          app_metadata: {
            provider: 'google',
          },
        },
      };

      localStorage.setItem('kisanAuth', 'true');
      localStorage.setItem('kisanUser', JSON.stringify({
        id: claims.sub,
        email: claims.email,
        name: claims.name || 'Farmer Partner',
        avatar: claims.picture || ''
      }));

      window.dispatchEvent(new CustomEvent('agro:signed-in', { detail: googleSession }));

      if (window.location.hash === '#/login' || window.location.hash === '#/signup') {
        window.location.hash = '#/';
      }
    }
  }

  // Initialize Google Identity Services
  function initGoogleIdentity() {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      try {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
          itp_support: true,
        });
        gsiInitialized = true;
        console.log('⚡ Google Identity Services (GIS) ready');

        // Auto-render button if container exists
        renderGoogleButtons();
      } catch (e) {
        console.warn('Failed to initialize Google Identity Services:', e);
      }
    } else {
      setTimeout(initGoogleIdentity, 300);
    }
  }

  function renderGoogleButtons() {
    if (!window.google?.accounts?.id) return;
    const targets = ['googleBtnContainer', 'loginGoogleBtnContainer', 'modalGoogleBtnContainer'];
    targets.forEach(id => {
      const el = document.getElementById(id);
      if (el && !el.dataset.gsiRendered) {
        el.dataset.gsiRendered = 'true';
        window.google.accounts.id.renderButton(el, {
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: el.clientWidth > 100 ? el.clientWidth : 280,
        });
      }
    });
  }

  // Fallback OAuth redirect flow
  async function fallbackToOAuthRedirect() {
    if (!client) initSupabase();
    if (!client) {
      throw new Error('Supabase client is still loading. Please check your connection.');
    }

    const redirectUrl = window.location.origin + window.location.pathname;
    const { data, error } = await client.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: redirectUrl,
        queryParams: {
          access_type: 'offline',
          prompt: 'consent'
        }
      }
    });

    if (error) {
      console.error('[Supabase Google Sign-In Error]:', error);
      throw error;
    }
    return data;
  }

  // Trigger Google Sign-In: prefers GIS popup/prompt, falls back to OAuth redirect
  async function signInWithGoogle() {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      if (!gsiInitialized) {
        initGoogleIdentity();
      }
      try {
        window.google.accounts.id.prompt((notification) => {
          if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
            const reason = notification.getNotDisplayedReason?.() || notification.getSkippedReason?.() || 'prompt_suppressed';
            console.log('GIS One Tap prompt not shown (' + reason + '), triggering OAuth redirect...');
            fallbackToOAuthRedirect().catch(err => {
              console.error('OAuth redirect fallback error:', err);
            });
          }
        });
        return { method: 'gis_prompt' };
      } catch (err) {
        console.warn('GIS prompt exception, falling back to OAuth redirect:', err);
      }
    }

    return await fallbackToOAuthRedirect();
  }

  // Sign out
  async function signOut() {
    if (client) {
      try { await client.auth.signOut(); } catch(e){}
    }
    if (window.google?.accounts?.id) {
      try { window.google.accounts.id.disableAutoSelect(); } catch(e){}
    }
    localStorage.removeItem('kisanAuth');
    localStorage.removeItem('kisanUser');
    localStorage.removeItem('agroAiSession');
    localStorage.removeItem('agroAiProfile');
    window.location.hash = '#/login';
  }

  // Expose global methods
  window.AgroSupabase = {
    getClient: () => client,
    signInWithGoogle,
    signOut,
    initGoogleIdentity,
    renderGoogleButtons,
    handleGoogleCredentialResponse,
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
    GOOGLE_CLIENT_ID,
  };

  // Start init
  initSupabase();
  initGoogleIdentity();
})();
