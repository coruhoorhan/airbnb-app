self.addEventListener('push', function(event) {
  let data = {};
  try {
    data = event.data.json();
  } catch (err) {
    data = { title: "Yeni Bildirim", body: event.data.text() };
  }

  const title = data.title || "Fatsa Escapes";
  const options = {
    body: data.body || "Yeni bir bildiriminiz var.",
    icon: '/waves.svg', // Assuming we don't have this, it'll fallback
    badge: '/waves.svg',
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  if (event.notification.data && event.notification.data.url) {
    event.waitUntil(
      clients.openWindow(event.notification.data.url)
    );
  }
});
