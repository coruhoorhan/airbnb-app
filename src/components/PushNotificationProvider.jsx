import React, { createContext, useContext, useState, useEffect } from 'react';

const PushNotificationContext = createContext({
  isSupported: false,
  isSubscribed: false,
  enableNotifications: async () => {},
  disableNotifications: async () => {}
});

export function usePushNotifications() {
  return useContext(PushNotificationContext);
}

// Convert VAPID key to format expected by PushManager
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function PushNotificationProvider({ children, currentUserId }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [subscription, setSubscription] = useState(null);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      registerServiceWorkerAndCheckSubscription();
    }
  }, [currentUserId]);

  async function registerServiceWorkerAndCheckSubscription() {
    try {
      const registration = await navigator.serviceWorker.register('/service-worker.js');

      // Check if already subscribed
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        setIsSubscribed(true);
        setSubscription(sub);
      }
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  }

  const enableNotifications = async () => {
    if (!isSupported || !currentUserId) return;

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        console.warn('Notification permission not granted');
        return;
      }

      const registration = await navigator.serviceWorker.ready;

      // Get VAPID public key from backend
      const vapidRes = await fetch('/api/notifications/vapid-public-key');
      const { key: vapidPublicKey } = await vapidRes.json();

      if (!vapidPublicKey) {
         console.error('No VAPID key available');
         return;
      }

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
      });

      // Get CSRF Token
      const csrfRes = await fetch('/api/csrf-token');
      const { csrfToken } = await csrfRes.json();

      // Send to backend
      const response = await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': csrfToken
        },
        body: JSON.stringify({
          userId: currentUserId,
          subscription: sub
        })
      });

      if (response.ok) {
        setIsSubscribed(true);
        setSubscription(sub);
      } else {
         console.error('Failed to save subscription to server');
      }

    } catch (err) {
      console.error('Failed to subscribe user:', err);
    }
  };

  const disableNotifications = async () => {
    if (!isSupported || !subscription || !currentUserId) return;

    try {
      // Get CSRF Token
      const csrfRes = await fetch('/api/csrf-token');
      const { csrfToken } = await csrfRes.json();

      await fetch('/api/notifications/unsubscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': csrfToken
        },
        body: JSON.stringify({
          userId: currentUserId,
          endpoint: subscription.endpoint
        })
      });

      await subscription.unsubscribe();
      setIsSubscribed(false);
      setSubscription(null);
    } catch (err) {
      console.error('Failed to unsubscribe user:', err);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, isSubscribed, enableNotifications, disableNotifications }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
