const CACHE_VERSION = "saams-2026-03-25-v1";
const STATIC_CACHE = `saams-static-${CACHE_VERSION}`;
const RUNTIME_CACHE = `saams-runtime-${CACHE_VERSION}`;

const CORE_ASSETS = [
    "/static/css/app.css",
    "/static/manifest.json",
    "/static/logo.png",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
    "/static/icons/apple-touch-icon.png",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    "https://cdn.jsdelivr.net/npm/chart.js",
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@500;600;700;800&display=swap",
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Montserrat:wght@600;700;800&family=Poppins:wght@500;600;700&display=swap",
];

const OFFLINE_HTML = `
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offline | School Management System</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #0f172a;
      --card: rgba(255, 255, 255, 0.94);
      --text: #13213d;
      --muted: #5d6b8d;
      --accent: #2563eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: Inter, Segoe UI, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.24), transparent 28%),
        linear-gradient(145deg, #0f172a, #172554 55%, #0f766e);
    }
    .card {
      width: min(460px, 100%);
      padding: 28px;
      border-radius: 24px;
      background: var(--card);
      box-shadow: 0 30px 70px rgba(2, 8, 23, 0.34);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 0.35rem 0.7rem;
      border-radius: 999px;
      background: rgba(37, 99, 235, 0.1);
      color: var(--accent);
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 0.72rem;
    }
    h1 {
      margin: 14px 0 10px;
      font-size: 1.6rem;
      line-height: 1.15;
    }
    p { color: var(--muted); line-height: 1.6; }
    button {
      margin-top: 10px;
      border: 0;
      border-radius: 14px;
      padding: 0.9rem 1.1rem;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      font-weight: 800;
    }
  </style>
</head>
<body>
  <section class="card">
    <span class="badge">Offline mode</span>
    <h1>You are offline</h1>
    <p>The school portal is not reachable right now. Reconnect to open the latest pages, or try again when your connection is back.</p>
    <button type="button" onclick="window.location.reload()">Try again</button>
  </section>
</body>
</html>
`;

function isAssetRequest(request) {
    if (request.destination && ["style", "script", "image", "font", "worker"].includes(request.destination)) {
        return true;
    }

    try {
        const url = new URL(request.url);
        return /\.(css|js|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|eot|json)$/i.test(url.pathname);
    } catch (error) {
        return false;
    }
}

async function cacheResponse(cacheName, request) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    if (cached) {
        return cached;
    }

    const response = await fetch(request);
    if (response && (response.ok || response.type === "opaque")) {
        cache.put(request, response.clone());
    }
    return response;
}

async function cacheCoreAssets() {
    const cache = await caches.open(STATIC_CACHE);
    await Promise.allSettled(
        CORE_ASSETS.map(async function (asset) {
            try {
                const request = new Request(asset, { cache: "reload" });
                const response = await fetch(request);
                if (response && (response.ok || response.type === "opaque")) {
                    await cache.put(asset, response.clone());
                }
            } catch (error) {
                return null;
            }
        })
    );
}

self.addEventListener("install", function (event) {
    event.waitUntil(
        cacheCoreAssets().then(function () {
            return self.skipWaiting();
        })
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.map(function (key) {
                    if (key !== STATIC_CACHE && key !== RUNTIME_CACHE) {
                        return caches.delete(key);
                    }
                    return null;
                })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

self.addEventListener("fetch", function (event) {
    if (event.request.method !== "GET") {
        return;
    }

    const requestUrl = new URL(event.request.url);

    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request)
                .then(function (response) {
                    const clonedResponse = response.clone();
                    caches.open(RUNTIME_CACHE).then(function (cache) {
                        cache.put(event.request, clonedResponse);
                    });
                    return response;
                })
                .catch(async function () {
                    const cachedPage = await caches.match(event.request);
                    if (cachedPage) {
                        return cachedPage;
                    }

                    const cachedHome = await caches.match("/");
                    if (cachedHome) {
                        return cachedHome;
                    }

                    return new Response(OFFLINE_HTML, {
                        headers: {
                            "Content-Type": "text/html; charset=utf-8",
                        },
                    });
                })
        );
        return;
    }

    if (isAssetRequest(event.request) || requestUrl.origin !== self.location.origin) {
        event.respondWith(
            cacheResponse(STATIC_CACHE, event.request).catch(function () {
                return caches.match(event.request);
            })
        );
    }
});
