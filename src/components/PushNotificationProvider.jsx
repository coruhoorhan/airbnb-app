import React, { createContext, useContext, useState, useEffect } from 'react';

const PushNotificationContext = createContext();

export const usePushNotification = () => useContext(PushNotificationContext);

// Hardcoded default since process.env or import.meta.env might not be set up for this specific VAPID key in the test environment,
// but we check import.meta.env if it exists.
const VAPID_PUBLIC_KEY = (import.meta && import.meta.env && import.meta.env.VITE_VAPID_PUBLIC_KEY) || "BMiq0uvC4kyqT6PthKvlLd6fUTb7z00wT_RU7bo79axRetIbco2ORTop1GALoisKllbvKuWDM3ZNarbYScHKNU8";

// Utility function to convert Base64 URL-safe string to Uint8Array
const urlBase64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

export const PushNotificationProvider = ({ children }) => {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState('default');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      setPermission(Notification.permission);

      // Register service worker and check current subscription status
      navigator.serviceWorker.register('/service-worker.js')
        .then(registration => {
          return registration.pushManager.getSubscription();
        })
        .then(subscription => {
          setIsSubscribed(subscription !== null);
          setLoading(false);
        })
        .catch(err => {
          console.error('Service Worker registration failed:', err);
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const getCsrfToken = async () => {
    try {
      const res = await fetch('/api/csrf-token');
      const data = await res.json();
      return data.csrfToken;
    } catch (e) {
      console.error("Error fetching CSRF token", e);
      return '';
    }
  };

  const subscribe = async () => {
    if (!isSupported) return;
    setLoading(true);

    try {
      const permissionResult = await Notification.requestPermission();
      setPermission(permissionResult);

      if (permissionResult !== 'granted') {
        throw new Error('We weren\'t granted permission.');
      }

      const registration = await navigator.serviceWorker.ready;
      const applicationServerKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);

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
        throw new Error('Failed to save subscription on server');
      }

      setIsSubscribed(true);
    } catch (error) {
      console.error('Failed to subscribe:', error);
    } finally {
      setLoading(false);
    }
  };

  const unsubscribe = async () => {
    if (!isSupported) return;
    setLoading(true);

    try {
      const registration = await navigator.serviceWorker.ready;
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
    } catch (error) {
      console.error('Error during unsubscribe:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleSubscription = () => {
    if (isSubscribed) {
      return unsubscribe();
    } else {
      return subscribe();
    }
  };

  return (
    <PushNotificationContext.Provider
      value={{
        isSupported,
        permission,
        isSubscribed,
        loading,
        subscribe,
        unsubscribe,
        toggleSubscription
      }}
    >
      {children}
    </PushNotificationContext.Provider>
  );
};
