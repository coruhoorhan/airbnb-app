1. **Database Update (`src/lib/db.js`)**
   - Add a SQL command to create the `push_subscriptions` table (`id`, `userId`, `endpoint`, `keysP`, `keysAuth`).

2. **Push Notification Engine (`src/lib/pushNotificationEngine.js`)**
   - Create this file using `web-push`.
   - Implement `saveSubscription`, `removeSubscription`, and `sendNotification`.
   - VAPID keys can be statically set or generated.

3. **Backend API Endpoints (`server.js`)**
   - Import `saveSubscription` and `removeSubscription`.
   - Add `POST /api/notifications/subscribe` (protect it and save).
   - Add `POST /api/notifications/unsubscribe` (remove it).
   - Add hooks in message insertion (`insertMessage` in `src/lib/db.js`?) or chat logic to call `sendNotification` with new message payload.
   - Add hooks in booking insertion/status change (`updateBookingApproval`, etc.) to call `sendNotification`.
   - (Need to check where these events happen).

4. **Frontend Service Worker (`src/service-worker.js`)**
   - Create it to handle `push` events and show notifications using `self.registration.showNotification`.

5. **Frontend React Provider (`src/components/PushNotificationProvider.jsx`)**
   - Register service worker.
   - Request Notification permission.
   - Send subscription to `/api/notifications/subscribe`.
   - Provide a UI context or component to toggle this.
   - Wrap the App with this provider or add a toggle in settings.

6. **Integrate Provider (`src/App.jsx`)**
   - Wrap `App` or place the toggle inside it.
   - Since task states "display a UI toggle in the user settings menu", I might need to put it somewhere accessible like `Navbar` or just a floating setting. Wait, the task says: "add `src/components/PushNotificationProvider.jsx` that registers a service worker... Update `App.jsx` to wrap the app with `<PushNotificationProvider>` and display a UI toggle in the user settings menu."
