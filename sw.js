// Guarda la app y la última copia de los datos para abrirla sin conexión.
const CACHE = 'estrategia-v4';
const BASE = ['./', 'index.html', 'manifest.webmanifest', 'icono.svg', 'icono-192.png', 'icono-512.png'];
self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting())));
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
// Primero la red; si no hay conexión, la última copia guardada.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(fetch(e.request).then(r => {
    const copia = r.clone();
    const url = new URL(e.request.url); url.search = '';
    caches.open(CACHE).then(c => c.put(url.toString(), copia));
    return r;
  }).catch(() => { const url = new URL(e.request.url); url.search = ''; return caches.match(url.toString()); }));
});
