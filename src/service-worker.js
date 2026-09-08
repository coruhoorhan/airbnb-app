self.addEventListener('push', function(event) {
  if (event.data) {
    try {
      const data = event.data.json();
      const title = data.title || 'Yeni Bildirim';
      const options = {
        body: data.body || 'Bildirim içeriği...',
        icon: '/vite.svg',
        badge: '/vite.svg',
        data: data.url || '/'
      };
      event.waitUntil(self.registration.showNotification(title, options));
    } catch (e) {
      console.error('Push event payload is not JSON', e);
    }
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.notification.data) {
    event.waitUntil(
      clients.openWindow(event.notification.data)
    );
  }
});
