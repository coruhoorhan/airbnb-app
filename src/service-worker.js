self.addEventListener('push', function(event) {
  if (event.data) {
    try {
      const data = event.data.json();
      const options = {
        body: data.body || 'Yeni bildirim',
        icon: '/vite.svg',
        badge: '/vite.svg',
        data: data.url || '/'
      };
      event.waitUntil(
        self.registration.showNotification(data.title || 'Fatsa Escapes', options)
      );
    } catch (err) {
      const options = {
        body: event.data.text(),
        icon: '/vite.svg',
        badge: '/vite.svg'
      };
      event.waitUntil(
        self.registration.showNotification('Fatsa Escapes', options)
      );
    }
  }
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      if (clientList.length > 0) {
        let client = clientList[0];
        for (let i = 0; i < clientList.length; i++) {
          if (clientList[i].focused) {
            client = clientList[i];
          }
        }
        return client.focus();
      }
      return clients.openWindow(event.notification.data || '/');
    })
  );
});
