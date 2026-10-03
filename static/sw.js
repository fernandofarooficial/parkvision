const CACHE_NAME = 'parkvision-v1';
const STATIC_ASSETS = [
    '/app/',
    '/app/login',
    '/static/icons/icon-square.svg',
    '/static/manifest.json',
];

self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    // Sempre busca da rede para rotas da aplicação (dados sempre frescos)
    if (e.request.url.includes('/api/') || e.request.url.includes('/app/')) {
        e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
        return;
    }
    // Demais assets: cache-first
    e.respondWith(
        caches.match(e.request).then((cached) => cached || fetch(e.request))
    );
});

// Alertas de câmera/NioBox (visionlib/statuslib -> pushlib), mesmo conteúdo do WhatsApp
self.addEventListener('push', (e) => {
    let dados = { title: 'ParkVision', body: '' };
    try { dados = e.data.json(); } catch (err) { /* payload vazio/õinválido — usa default */ }

    e.waitUntil(
        self.registration.showNotification(dados.title || 'ParkVision', {
            body: dados.body || '',
            icon: '/static/icons/icon-192.png',
            badge: '/static/icons/icon-192.png',
            tag: 'parkvision-status',
        })
    );
});

self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    e.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((lista) => {
            for (const c of lista) {
                if (c.url.includes('/app/') && 'focus' in c) return c.focus();
            }
            if (clients.openWindow) return clients.openWindow('/app/monitoramento');
        })
    );
});
