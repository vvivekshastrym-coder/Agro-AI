// Agro AI Service Worker for Offline Farming Support
const CACHE_NAME = 'agroai-v17-kannada-fix';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './favicon.png',
  './css/styles.css',
  './js/i18n.js',
  './js/router.js',
  './js/engine/supabase.js',
  './js/engine/core.js',
  './js/engine/api.js',
  './js/engine/reports.js',
  './js/engine/whatsapp.js',
  './js/components/nav.js',
  './js/pages/home.js',
  './js/pages/mart.js',
  './js/pages/diagnose.js',
  './js/pages/kisan-gpt.js',
  './js/pages/weather.js',
  './js/pages/market.js',
  './js/pages/more.js',
  './icons/agro-ai-logo.png',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png'
];

// Install Event
self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching App Shell Assets:', CACHE_NAME);
      return cache.addAll(ASSETS);
    })
  );
});

// Activate Event: purge all outdated caches & notify clients
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[Service Worker] Removing old cache', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim()).then(() => {
      return self.clients.matchAll({ type: 'window' }).then((clients) => {
        clients.forEach((client) => {
          try {
            client.postMessage({ type: 'SW_UPDATED', version: CACHE_NAME });
          } catch(err){}
        });
      });
    })
  );
});

// Fetch Event (Network-first for HTML & dynamic APIs, with robust cache fallback)
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  // Never intercept API calls or external auth with static cache
  if (e.request.url.includes('/api/') || e.request.url.includes('supabase.co') || e.request.url.includes('accounts.google.com')) {
    return;
  }

  // Network-first for navigation requests (index.html) so updates are immediate
  if (e.request.mode === 'navigate' || e.request.destination === 'document') {
    e.respondWith(
      fetch(e.request)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(e.request, copy));
          }
          return response;
        })
        .catch(() => caches.match('./index.html', { ignoreSearch: true }))
    );
    return;
  }

  e.respondWith(
    fetch(e.request)
      .then((response) => {
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        return caches.match(e.request, { ignoreSearch: true }).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          if (e.request.mode === 'navigate') {
            return caches.match('./index.html', { ignoreSearch: true });
          }
        });
      })
  );
});
