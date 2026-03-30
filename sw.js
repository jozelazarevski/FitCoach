const CACHE_NAME = 'fitcoach-v14';
const API_CACHE = 'fitcoach-api-v1';
const API_CACHE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

const CACHE_NAME = 'fitcoach-v6';
const ASSETS = [
  '/index.html',
  '/css/style.css',
  '/js/app.js',
  '/js/storage.js',
  '/js/auth.js',
  '/js/llm.js',
  '/js/tracker.js',
  '/js/recipes.js',
  '/js/coach.js',
  '/js/profile.js',
  '/js/ui.js',
  '/js/body.js',
  '/manifest.json',
  '/icons/icon.svg'
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
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== API_CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Cacheable read-only API endpoints (GET only)
const CACHEABLE_API = ['/api/recipes/', '/api/health'];

self.addEventListener('fetch', e => {
  const url = e.request.url;

  // External API calls — never cache
  if (url.includes('api.openai.com') || url.includes('api.anthropic.com')) return;

  // Cacheable API GET requests — stale-while-revalidate
  if (e.request.method === 'GET' && CACHEABLE_API.some(p => url.includes(p))) {
    e.respondWith(
      caches.open(API_CACHE).then(async cache => {
        const cached = await cache.match(e.request);
        const fetchPromise = fetch(e.request).then(res => {
          if (res.ok) {
            const clone = res.clone();
            // Store with timestamp header for TTL
            const headers = new Headers(clone.headers);
            headers.set('sw-cached-at', Date.now().toString());
            cache.put(e.request, new Response(clone.body, { status: clone.status, headers }));
          }
          return res;
        }).catch(() => cached); // offline fallback

        if (cached) {
          const cachedAt = parseInt(cached.headers.get('sw-cached-at') || '0');
          if (Date.now() - cachedAt < API_CACHE_MAX_AGE) return cached;
        }
        return fetchPromise;
      })
    );
    return;
  }

  // Non-API write requests (POST/PUT/DELETE) — skip cache
  if (url.includes('/api/')) return;

  // Static assets — cache-first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
