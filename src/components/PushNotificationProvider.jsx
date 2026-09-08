import React, { createContext, useContext, useEffect, useState } from 'react';

const PushNotificationContext = createContext({
  isSupported: false,
  isSubscribed: false,
  subscribe: async () => {},
  unsubscribe: async () => {}
});

export const usePushNotifications = () => useContext(PushNotificationContext);

// Base64Url to Uint8Array converter
const urlB64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

export const PushNotificationProvider = ({ children }) => {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [registration, setRegistration] = useState(null);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);

      navigator.serviceWorker.register('/src/service-worker.js')
        .then(reg => {
          setRegistration(reg);
          return reg.pushManager.getSubscription();
        })
        .then(sub => {
          setIsSubscribed(!!sub);
        })
        .catch(err => {
          console.error('Service Worker registration failed: ', err);
        });
    }
  }, []);

  const getCsrfToken = async () => {
    const res = await fetch('/api/auth/csrf');
    const token = res.headers.get('x-csrf-token');
    return token;
  };

  const subscribe = async () => {
    if (!registration) return;

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        throw new Error('Notification permission denied');
      }

      const vapidPublicKey = import.meta.env.VITE_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        throw new Error('VAPID public key not found');
      }

      const applicationServerKey = urlB64ToUint8Array(vapidPublicKey);

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey
      });

      const csrfToken = await getCsrfToken();

      const res = await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': csrfToken
        },
        body: JSON.stringify({ subscription })
      });

      if (!res.ok) {
        throw new Error('Failed to save subscription on server');
      }

      setIsSubscribed(true);
    } catch (err) {
      console.error('Failed to subscribe the user: ', err);
    }
  };

  const unsubscribe = async () => {
    if (!registration) return;

    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();

        const csrfToken = await getCsrfToken();
        await fetch('/api/notifications/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csrf-token': csrfToken
          }
        });
      }
      setIsSubscribed(false);
    } catch (err) {
      console.error('Failed to unsubscribe the user: ', err);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, isSubscribed, subscribe, unsubscribe }}>
      {children}
    </PushNotificationContext.Provider>
  );
};
