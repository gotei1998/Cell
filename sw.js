// Кеш для повторных заходов: движок весит около 30 МБ, и на телефоне его не стоит качать каждый раз.
// Файлы движка в runtime/ не меняются, поэтому берутся из кеша. Сама страница и решатель идут из сети,
// а кеш нужен им только когда сети нет, так что обновления сайта приходят сразу.
const RUNTIME = 'kletka-runtime-v1';  // поднимите номер, если заменили файлы в runtime/
const APP = 'kletka-app-v1';
const ENGINE = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'pyodide-lock.json', 'python_stdlib.zip',
  'mpmath.zip', 'sympy.zip', 'mathjax-tex-svg.js', 'telegram-web-app.js'];

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name !== RUNTIME && name !== APP) await caches.delete(name);
    await self.clients.claim();
  })());
});

// Страница просит докачать движок в кеш после первого запуска: в первый заход он грузится раньше, чем включается кеш.
self.addEventListener('message', (event) => {
  if (!event.data || event.data.type !== 'precache') return;
  event.waitUntil((async () => {
    const cache = await caches.open(RUNTIME);
    for (const file of ENGINE) {
      const url = new URL('runtime/' + file, self.registration.scope).href;
      if (await cache.match(url)) continue;
      try {
        const res = await fetch(url);
        if (res.ok) await cache.put(url, res);
      } catch {}
    }
  })());
});

async function fromCacheFirst(request) {
  const cache = await caches.open(RUNTIME);
  const hit = await cache.match(request.url);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request.url, res.clone());
  return res;
}

async function fromNetworkFirst(request) {
  const cache = await caches.open(APP);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(request.url, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(request.url, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope)) return;
  const path = url.href.slice(self.registration.scope.length);
  event.respondWith(path.startsWith('runtime/') ? fromCacheFirst(request) : fromNetworkFirst(request));
});
