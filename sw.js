// Offline cache. Bump VERSION whenever index.html changes so phones pick up the update.
const VERSION = "indys-year-v2.6.0";
const FILES = ["./foods.json.gz", "./", "./index.html", "./manifest.webmanifest", "./icon.svg", "./icon-180.png", "./icon-192.png", "./icon-512.png",
  // (foods.json.gz above: the offline food database, ~380 KB, built by tools/build_fooddb.py)
  // self-hosted fonts (Neon Athletic restyle): precached, then served by the cache-first fetch handler below
  "./fonts/barlow-400.woff2", "./fonts/barlow-500.woff2", "./fonts/barlow-600.woff2", "./fonts/barlow-700.woff2",
  "./fonts/chakra-petch-500.woff2", "./fonts/chakra-petch-600.woff2", "./fonts/chakra-petch-700.woff2"];
// Pinned supabase-js (cloud sync). Cached separately so a CDN hiccup can't break the install; the app also works without it.
const SB_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/dist/umd/supabase.js";
self.addEventListener("install", e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES).then(() => c.add(new Request(SB_JS, { mode: "cors" })).catch(() => {})))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  // Network first for the page so updates arrive; fall back to cache offline.
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put("./index.html", copy)); return r; }).catch(() => caches.match("./index.html")));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
