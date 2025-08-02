self.addEventListener('install', event => {
    event.waitUntil(
        caches.open('chat-app-v1').then(cache => {
            return cache.addAll([
                '/',
                '/static/styles.css',
                '/static/app.js',
                '/static/manifest.json',
                '/static/icon.png',
                '/static/icon-512.png'
            ]);
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

self.addEventListener('sync', event => {
    if (event.tag === 'sync-messages') {
        event.waitUntil(
            fetch('/api/get_messages')
                .then(response => response.json())
                .then(messages => {
                    self.clients.matchAll().then(clients => {
                        clients.forEach(client => {
                            client.postMessage({ type: 'sync-messages', messages });
                        });
                    });
                })
        );
    }
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
            for (let client of clients) {
                if (client.url.includes('/') && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow('/');
            }
        })
    );
});