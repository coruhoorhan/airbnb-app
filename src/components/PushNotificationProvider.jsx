import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

const PushNotificationContext = createContext({
  isSupported: false,
  isSubscribed: false,
  subscribe: async () => {},
  unsubscribe: async () => {}
});

export const usePushNotifications = () => useContext(PushNotificationContext);

// Utility to convert VAPID public key to Uint8Array for pushManager
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
  const [subscriptionInfo, setSubscriptionInfo] = useState(null);

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
    }
  }, []);

  const checkSubscription = useCallback(async () => {
    if (!isSupported) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        setIsSubscribed(true);
        setSubscriptionInfo(sub);
      } else {
        setIsSubscribed(false);
        setSubscriptionInfo(null);
      }
    } catch (err) {
      console.error("[PushProvider] Error checking subscription", err);
    }
  }, [isSupported]);

  useEffect(() => {
    if (isSupported) {
      checkSubscription();
    }
  }, [isSupported, checkSubscription]);

  const subscribe = async () => {
    if (!isSupported) return { success: false, error: "Not supported" };
    if (!currentUserId) return { success: false, error: "User not logged in" };

    try {
      // Get VAPID public key from backend
      const vapidRes = await fetch('/api/notifications/vapid-public-key');
      const vapidPublicKey = await vapidRes.text();
      const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);

      const registration = await navigator.serviceWorker.ready;

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey
      });

      // Send to backend
      const response = await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          userId: currentUserId,
          subscription: sub
        })
      });

      const data = await response.json();
      if (data.success) {
        setIsSubscribed(true);
        setSubscriptionInfo(sub);
        return { success: true };
      } else {
        return { success: false, error: data.error };
      }

    } catch (err) {
      console.error("[PushProvider] Failed to subscribe:", err);
      return { success: false, error: err.message };
    }
  };

  const unsubscribe = async () => {
    if (!isSupported) return { success: false, error: "Not supported" };
    if (!currentUserId) return { success: false, error: "User not logged in" };

    try {
      const registration = await navigator.serviceWorker.ready;
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        await sub.unsubscribe();

        // Remove from backend
        await fetch('/api/notifications/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            userId: currentUserId,
            endpoint: sub.endpoint
          })
        });
      }
      setIsSubscribed(false);
      setSubscriptionInfo(null);
      return { success: true };
    } catch (err) {
      console.error("[PushProvider] Failed to unsubscribe:", err);
      return { success: false, error: err.message };
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, isSubscribed, subscribe, unsubscribe }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
