const CACHE_NAME = 'fitcoach-v6';
const ASSETS = [
  '/index.html',
  '/css/style.css',
  '/js/app.js',
  '/js/storage.js',
  '/js/llm.js',
  '/js/tracker.js',
  '/js/coach.js',
  '/js/profile.js',
  '/js/ui.js',
  '/js/body.js',
  '/js/db.js',
  '/data/recipes.db',
  '/manifest.json'
];
const CDN_ASSETS = [
  'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js',
  'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.wasm'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c =>
      c.addAll(ASSETS).then(() => c.addAll(CDN_ASSETS).catch(() => {}))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.url.includes('api.openai.com') || e.request.url.includes('api.anthropic.com')) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
