// ── JEWELLERY BILLING APP — SERVICE WORKER v3 ─────────────────────────────────
// CSS/JS: network-first so updates load immediately without hard refresh.
// Images/icons: cache-first (they never change).
// HTML + API: network-first always.

const CACHE_NAME = 'jewelbill-v3';

const IMMUTABLE_URLS = [
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/manifest.json',
];

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

// ── INSTALL ────────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return Promise.allSettled(
                IMMUTABLE_URLS.map(url =>
                    cache.add(url).catch(err => console.warn('[SW] Failed to cache:', url, err))
                )
            );
        }).then(() => self.skipWaiting())
    );
});

// ── ACTIVATE: wipe all old caches ─────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => {
                    console.log('[SW] Deleting old cache:', key);
                    return caches.delete(key);
                })
            )
        ).then(() => self.clients.claim())
    );
});

// ── FETCH ──────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    if (url.origin !== self.location.origin) return;
    if (request.method !== 'GET') return;

    // Icons + manifest: cache-first (they never change)
    if (IMMUTABLE_URLS.includes(url.pathname)) {
        event.respondWith(
            caches.match(request).then(cached => cached || fetch(request))
        );
        return;
    }

    // Everything else (CSS, JS, HTML, API): network-first so updates are instant
    event.respondWith(
        fetch(request)
            .then(response => response)
            .catch(() => {
                if (request.mode === 'navigate') {
                    return new Response(OFFLINE_HTML, {
                        headers: { 'Content-Type': 'text/html' },
                    });
                }
                return new Response(
                    JSON.stringify({ error: 'You are offline.' }),
                    { headers: { 'Content-Type': 'application/json' } }
                );
            })
    );
});