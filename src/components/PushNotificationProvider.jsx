import React, { createContext, useContext, useEffect, useState } from "react";

const PushNotificationContext = createContext();

export function usePushNotification() {
  return useContext(PushNotificationContext);
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function PushNotificationProvider({ children }) {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [registration, setRegistration] = useState(null);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      navigator.serviceWorker.register('/service-worker.js')
        .then(reg => {
          setRegistration(reg);
          reg.pushManager.getSubscription().then(sub => {
            setIsSubscribed(!!sub);
          });
        })
        .catch(err => console.error("Service Worker registration failed:", err));
    }
  }, []);

  const subscribe = async () => {
    if (!registration) return;
    try {
      const vapidRes = await fetch('/api/notifications/vapid-key');
      const { publicVapidKey } = await vapidRes.json();
      const convertedVapidKey = urlBase64ToUint8Array(publicVapidKey);

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey
      });

      await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription })
      });

      setIsSubscribed(true);
    } catch (err) {
      console.error("Failed to subscribe the user: ", err);
    }
  };

  const unsubscribe = async () => {
    if (!registration) return;
    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();
        await fetch('/api/notifications/unsubscribe', { method: 'POST' });
        setIsSubscribed(false);
      }
    } catch (err) {
      console.error("Failed to unsubscribe the user: ", err);
    }
  };

  const toggleSubscription = () => {
    if (isSubscribed) unsubscribe();
    else subscribe();
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, isSubscribed, toggleSubscription }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
