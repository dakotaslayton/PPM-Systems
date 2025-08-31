self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('ppm-cache-v1').then(cache =>
      cache.addAll(['./','./index.html','./manifest.json','./icon-192.png','./icon-512.png'])
    )
  );
});
self.addEventListener('fetch', (e) => {
  e.respondWith(caches.match(e.request).then(resp => resp || fetch(e.request)));
});
