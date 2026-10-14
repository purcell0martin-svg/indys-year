// Offline cache. Bump VERSION whenever index.html changes so phones pick up the update.
const VERSION = "indys-year-v2.16.1";
// Runtime cache for jsDelivr files fetched on demand (the barcode-scanner polyfill and its WASM engine). It is NOT tied to VERSION,
// so a new release does not throw away the offline scanner. Every URL is pinned to an exact version, so cached copies never go stale.
const CDN_CACHE = "indys-year-cdn";
const FILES = ["./foods.json.gz", "./", "./index.html", "./manifest.webmanifest", "./icon.svg", "./icon-180.png", "./icon-192.png", "./icon-512.png",
  // (foods.json.gz above: the offline food database, ~380 KB, built by tools/build_fooddb.py)
  // self-hosted fonts (Neon Athletic restyle): precached, then served by the cache-first fetch handler below
  "./fonts/barlow-400.woff2", "./fonts/barlow-500.woff2", "./fonts/barlow-600.woff2", "./fonts/barlow-700.woff2",
  "./fonts/chakra-petch-500.woff2", "./fonts/chakra-petch-600.woff2", "./fonts/chakra-petch-700.woff2"];
// Pinned supabase-js (cloud sync). Cached separately so a CDN hiccup can't break the install; the app also works without it.
const SB_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/dist/umd/supabase.js";
self.addEventListener("install", e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES).then(() => c.add(new Request(SB_JS, { mode: "cors" })).catch(() => {})))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION && k !== CDN_CACHE).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  // jsDelivr (any host: the polyfill comes from cdn.jsdelivr.net but its WASM comes from fastly.jsdelivr.net): cache-first, then cache on first fetch.
  // caches.match() looks in every cache, so the precached supabase-js is found too.
  const u = new URL(e.request.url);
  if (u.hostname === "jsdelivr.net" || u.hostname.endsWith(".jsdelivr.net")) {
    e.respondWith((async () => {
      const hit = await caches.match(e.request);
      if (hit) return hit;
      const r = await fetch(e.request);
      if (r && r.ok) { const copy = r.clone(); caches.open(CDN_CACHE).then(c => c.put(e.request, copy)); }   // clone now, before the body is read
      return r;
    })());
    return;
  }
  // Network first for the page so updates arrive; fall back to cache offline.
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put("./index.html", copy)); return r; }).catch(() => caches.match("./index.html")));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
