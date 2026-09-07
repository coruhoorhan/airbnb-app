import React, { createContext, useContext, useState, useEffect } from 'react';

const PushNotificationContext = createContext({
  isSubscribed: false,
  isSupported: false,
  subscribe: async () => {},
  unsubscribe: async () => {},
});

export function usePushNotification() {
  return useContext(PushNotificationContext);
}

// Ensure the VAPID key is accessible here.
const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;

export function PushNotificationProvider({ children, currentUser }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [registration, setRegistration] = useState(null);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      registerServiceWorker();
    }
  }, []);

  useEffect(() => {
    // If the user changes, we might want to check subscription status.
    // For simplicity, we just rely on local state.
  }, [currentUser]);

  const registerServiceWorker = async () => {
    try {
      const swReg = await navigator.serviceWorker.register('/service-worker.js');
      setRegistration(swReg);

      const sub = await swReg.pushManager.getSubscription();
      if (sub) {
        setIsSubscribed(true);
      }
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  };

  const getCsrfToken = async () => {
    const res = await fetch("/api/csrf-token");
    const data = await res.json();
    return data.csrfToken;
  };

  const urlB64ToUint8Array = (base64String) => {
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
  };

  const subscribe = async () => {
    if (!registration || !currentUser) return;

    try {
      const applicationServerKey = urlB64ToUint8Array(VAPID_PUBLIC_KEY);
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });

      const csrfToken = await getCsrfToken();

      const response = await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': csrfToken
        },
        body: JSON.stringify({ subscription })
      });

      if (!response.ok) {
        throw new Error('Failed to subscribe on server');
      }

      setIsSubscribed(true);
    } catch (error) {
      console.error('Failed to subscribe the user:', error);
    }
  };

  const unsubscribe = async () => {
    if (!registration || !currentUser) return;

    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();

        const csrfToken = await getCsrfToken();
        await fetch('/api/notifications/unsubscribe', {
          method: 'POST',
          headers: {
             'x-csrf-token': csrfToken
          }
        });
      }
      setIsSubscribed(false);
    } catch (error) {
      console.error('Error unsubscribing', error);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSubscribed, isSupported, subscribe, unsubscribe }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
