self.addEventListener('push', (event) => {
  if (event.data) {
    try {
      const payload = event.data.json();
      const title = payload.title || 'Yeni Bildirim';
      const options = {
        body: payload.body || '',
        icon: '/favicon.ico', // Adjust path if needed
        badge: '/favicon.ico',
        data: payload.url || '/'
      };
      event.waitUntil(self.registration.showNotification(title, options));
    } catch (e) {
      // If it's not JSON, treat it as a text string for the body
      const title = 'Yeni Bildirim';
      const options = {
        body: event.data.text(),
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        data: '/'
      };
      event.waitUntil(self.registration.showNotification(title, options));
    }
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      for (let i = 0; i < clientList.length; i++) {
        let client = clientList[i];
        if (client.url === '/' && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(event.notification.data || '/');
      }
    })
  );
});
