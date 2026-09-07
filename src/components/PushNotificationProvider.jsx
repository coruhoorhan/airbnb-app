import React, { createContext, useContext, useEffect, useState } from 'react';

const PushNotificationContext = createContext();

export const usePushNotifications = () => {
  return useContext(PushNotificationContext);
};

export const PushNotificationProvider = ({ children, currentUserId }) => {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState('default');
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      setPermission(Notification.permission);
      checkSubscription();
    }
  }, []);

  const checkSubscription = async () => {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      setIsSubscribed(!!subscription);
    } catch (e) {
      console.error("Error checking subscription:", e);
    }
  };

  const getVapidPublicKey = async () => {
    try {
      const res = await fetch('/api/notifications/vapid-public-key');
      const data = await res.json();
      return data.data;
    } catch (e) {
      console.error("Failed to fetch VAPID public key", e);
      return null;
    }
  };

  const urlBase64ToUint8Array = (base64String) => {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  };

  const subscribeToPushNotifications = async () => {
    if (!isSupported || !currentUserId) return false;

    const currentPerm = await Notification.requestPermission();
    setPermission(currentPerm);

    if (currentPerm !== 'granted') return false;

    try {
      const registration = await navigator.serviceWorker.register('/service-worker.js');
      await navigator.serviceWorker.ready;

      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        const vapidPublicKey = await getVapidPublicKey();
        if (!vapidPublicKey) return false;

        const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: convertedVapidKey
        });
      }

      const response = await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          userId: currentUserId,
          subscription
        })
      });

      const result = await response.json();
      if (result.success) {
        setIsSubscribed(true);
        return true;
      }
      return false;
    } catch (e) {
      console.error("Failed to subscribe to push notifications", e);
      return false;
    }
  };

  const unsubscribeFromPushNotifications = async () => {
    if (!isSupported || !currentUserId) return false;

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await subscription.unsubscribe();

        await fetch('/api/notifications/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            userId: currentUserId,
            endpoint: subscription.endpoint
          })
        });
      }
      setIsSubscribed(false);
      return true;
    } catch (e) {
      console.error("Failed to unsubscribe from push notifications", e);
      return false;
    }
  };

  const toggleSubscription = async () => {
    if (isSubscribed) {
      return await unsubscribeFromPushNotifications();
    } else {
      return await subscribeToPushNotifications();
    }
  };

  return (
    <PushNotificationContext.Provider
      value={{
        isSupported,
        permission,
        isSubscribed,
        subscribeToPushNotifications,
        unsubscribeFromPushNotifications,
        toggleSubscription
      }}
    >
      {children}
    </PushNotificationContext.Provider>
  );
};
