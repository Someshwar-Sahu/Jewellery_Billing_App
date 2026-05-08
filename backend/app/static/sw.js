// ── JEWELLERY BILLING APP — SERVICE WORKER ────────────────────────────────────
// Strategy:
//   Shell files (CSS, JS, icons) → Cache-first (fast loads, updated on new deploy)
//   All HTML pages and API calls → Network-first (always fresh data)
//   Offline fallback → Show a simple offline page if network fails

const CACHE_NAME    = 'jewelbill-v1';
const CACHE_VERSION = 1;

// Files to pre-cache on install — the app "shell"
const SHELL_URLS = [
    '/static/css/style.css',
    '/static/js/invoice.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/manifest.json',
];

// Offline fallback HTML — shown when network fails on a page navigation
const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offline — Jewellery Billing</title>
    <style>
        body { font-family: Arial, sans-serif; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; background: #f5f5f5; margin: 0; }
        .box { text-align: center; padding: 40px; background: #fff;
               border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 320px; }
        h1   { color: #1a1a2e; font-size: 20px; margin-bottom: 8px; }
        p    { color: #888; font-size: 14px; margin-bottom: 20px; }
        button { background: #1a1a2e; color: #fff; border: none; padding: 10px 24px;
                 border-radius: 6px; cursor: pointer; font-size: 14px; }
    </style>
</head>
<body>
    <div class="box">
        <div style="font-size:48px;margin-bottom:12px">📡</div>
        <h1>You're offline</h1>
        <p>Please check your internet connection and try again.</p>
        <button onclick="location.reload()">Try Again</button>
    </div>
</body>
</html>`;

// ── INSTALL: pre-cache the shell ──────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Pre-caching shell');
            // Cache each file individually — don't let one failure block all
            return Promise.allSettled(
                SHELL_URLS.map(url =>
                    cache.add(url).catch(err =>
                        console.warn('[SW] Failed to cache:', url, err)
                    )
                )
            );
        }).then(() => self.skipWaiting())
    );
});

// ── ACTIVATE: clean up old caches ─────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => {
                        console.log('[SW] Deleting old cache:', key);
                        return caches.delete(key);
                    })
            )
        ).then(() => self.clients.claim())
    );
});

// ── FETCH: routing strategy ───────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url         = new URL(request.url);

    // Only handle same-origin requests
    if (url.origin !== self.location.origin) return;

    // Skip non-GET requests (POST/PUT bill saves must always go to network)
    if (request.method !== 'GET') return;

    // ── Static assets: cache-first ────────────────────────────────────────
    if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
        event.respondWith(
            caches.match(request).then(cached => {
                if (cached) return cached;
                return fetch(request).then(response => {
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    }
                    return response;
                });
            })
        );
        return;
    }

    // ── All other routes (HTML pages, API): network-first ─────────────────
    // Data must always be fresh — never serve stale bills/rates from cache
    event.respondWith(
        fetch(request)
            .then(response => response)
            .catch(() => {
                // Network failed — check if it's a page navigation
                if (request.mode === 'navigate') {
                    return new Response(OFFLINE_HTML, {
                        headers: { 'Content-Type': 'text/html' },
                    });
                }
                // For API/JSON requests return a JSON error
                return new Response(
                    JSON.stringify({ error: 'You are offline.' }),
                    { headers: { 'Content-Type': 'application/json' } }
                );
            })
    );
});