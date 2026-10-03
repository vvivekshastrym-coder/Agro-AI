// ═══════════════════════════════════════════════════════════
// AGRO AI — SUPABASE CLIENT & AUTH MODULE
// Configured with live Supabase Project
// ═══════════════════════════════════════════════════════════
(function () {
  'use strict';

  const SUPABASE_URL = 'https://eziigoiirqdsgimfkquv.supabase.co';
  const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_fDc46mh4MukSCabbBpeVMA_KqtWdOee';

  let client = null;

  function initSupabase() {
    if (window.supabase && typeof window.supabase.createClient === 'function') {
      try {
        client = window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
        window.supabaseClient = client;
        console.log('⚡ Supabase Client initialized successfully');

        // Listen for Auth state changes (OAuth redirects, login, logout)
        client.auth.onAuthStateChange(async (event, session) => {
          console.log('[Supabase Auth Event]:', event, session ? session.user?.email : 'No session');
          
          if (event === 'SIGNED_IN' && session && session.user) {
            localStorage.setItem('kisanAuth', 'true');
            localStorage.setItem('kisanUser', JSON.stringify({
              id: session.user.id,
              email: session.user.email,
              name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0] || 'Farmer Partner',
              avatar: session.user.user_metadata?.avatar_url || ''
            }));

            // Sync with backend API
            try {
              await fetch('http://localhost:8000/api/auth/google', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  email: session.user.email,
                  name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0],
                  picture: session.user.user_metadata?.avatar_url
                })
              });
            } catch(e) {
              console.warn('Backend auth sync notice:', e);
            }

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
      console.warn('Supabase JS library not yet loaded. Retrying...');
      setTimeout(initSupabase, 200);
    }
  }

  // Trigger Google OAuth sign-in
  async function signInWithGoogle() {
    if (!client) {
      initSupabase();
    }
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

  // Sign out
  async function signOut() {
    if (client) {
      await client.auth.signOut();
    }
    localStorage.removeItem('kisanAuth');
    localStorage.removeItem('kisanUser');
    window.location.hash = '#/login';
  }

  // Expose global methods
  window.AgroSupabase = {
    getClient: () => client,
    signInWithGoogle,
    signOut,
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
  };

  // Start init
  initSupabase();
})();
