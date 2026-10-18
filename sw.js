// KisanAI Service Worker for Offline Farming Support
const CACHE_NAME = 'agroai-v10-auth';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
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

// Activate Event
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
    }).then(() => self.clients.claim())
  );
});

// Fetch Event (Network-first for HTML/JS/API; cache fallback when offline)
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  // Never intercept API calls with static cache
  if (e.request.url.includes('/api/') || e.request.url.includes('supabase.co')) {
    return;
  }

  e.respondWith(
    fetch(e.request, { cache: 'no-store' })
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
        return caches.match(e.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          if (e.request.mode === 'navigate') {
            return caches.match('./index.html');
          }
        });
      })
  );
});
