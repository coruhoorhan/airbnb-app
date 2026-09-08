self.addEventListener('push', function(event) {
  if (event.data) {
    try {
      const data = event.data.json();
      const options = {
        body: data.body || 'Bildirim içeriği...',
        icon: '/vite.svg',
        badge: '/vite.svg',
        vibrate: [100, 50, 100],
        data: {
          dateOfArrival: Date.now(),
          primaryKey: '2'
        }
      };

      event.waitUntil(
        self.registration.showNotification(data.title || 'Fatsa Escapes', options)
      );
    } catch (err) {
      console.error('Error parsing push data', err);
    }
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      // Check if there is already a window/tab open with the target URL
      for (var i = 0; i < windowClients.length; i++) {
        var client = windowClients[i];
        if (client.url.indexOf(self.registration.scope) !== -1 && 'focus' in client) {
          return client.focus();
        }
      }
      // If not, open a new window
      if (clients.openWindow) {
        return clients.openWindow('/');
      }
    })
  );
});
