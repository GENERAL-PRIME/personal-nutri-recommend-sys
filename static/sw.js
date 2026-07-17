// NutriAI — minimal service worker
// Satisfies Chrome's PWA installability requirement (fetch handler present).
// Uses network-first; falls back to cache only if a request was cached previously.

const CACHE_NAME = "nutriai-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) => cached || Response.error()),
    ),
  );
});
