// KisanAI Service Worker for Offline Farming Support
const CACHE_NAME = 'kisanai-v2';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './css/styles.css',
  './js/i18n.js',
  './js/router.js',
  './js/engine/core.js',
  './js/engine/api.js',
  './js/engine/reports.js',
  './js/engine/whatsapp.js',
  './js/components/nav.js',
  './js/pages/home.js',
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
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching App Shell Assets');
      return cache.addAll(ASSETS);
    }).then(() => self.skipWaiting())
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

// Fetch Event (Network falling back to cache with offline page fallback)
self.addEventListener('fetch', (e) => {
  // Only handle GET requests
  if (e.request.method !== 'GET') return;

  // Skip API weather requests to allow real-time checking, falling back to cache if offline
  if (e.request.url.includes('api.open-meteo.com')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }

  e.respondWith(
    fetch(e.request)
      .then((response) => {
        // Clone and put in cache if valid response
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Offline: try to return from cache
        return caches.match(e.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // If a page/route is requested, fallback to index
          if (e.request.mode === 'navigate') {
            return caches.match('./index.html');
          }
        });
      })
  );
});
