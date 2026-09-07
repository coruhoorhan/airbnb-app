import React, { createContext, useContext, useState, useEffect } from "react";

const PushNotificationContext = createContext({
  isSupported: false,
  permission: "default",
  isSubscribed: false,
  subscribe: async () => {},
  unsubscribe: async () => {}
});

export const usePushNotifications = () => useContext(PushNotificationContext);

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/\-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function PushNotificationProvider({ children, currentUser }) {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState("default");
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [subscription, setSubscription] = useState(null);

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
      setPermission(Notification.permission);

      navigator.serviceWorker.register("/src/service-worker.js")
        .then(registration => {
          return registration.pushManager.getSubscription();
        })
        .then(sub => {
          if (sub) {
            setIsSubscribed(true);
            setSubscription(sub);
          }
        })
        .catch(err => console.error("Service Worker registration failed:", err));
    }
  }, []);

  const subscribe = async () => {
    if (!isSupported || !currentUser) return;
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== "granted") {
        throw new Error("Notification permission not granted");
      }

      const registration = await navigator.serviceWorker.ready;

      // Fetch VAPID public key
      const response = await fetch("/api/notifications/vapid-public-key");
      const data = await response.json();

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(data.publicKey)
      });

      const csrfRes = await fetch("/api/csrf-token");
      const { csrfToken } = await csrfRes.json();

      // Send to server
      await fetch("/api/notifications/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": csrfToken
        },
        body: JSON.stringify({ userId: currentUser.id, subscription: sub })
      });

      setIsSubscribed(true);
      setSubscription(sub);
    } catch (err) {
      console.error("Failed to subscribe to push notifications", err);
    }
  };

  const unsubscribe = async () => {
    if (!isSupported || !subscription || !currentUser) return;
    try {
      await subscription.unsubscribe();

      const csrfRes = await fetch("/api/csrf-token");
      const { csrfToken } = await csrfRes.json();

      await fetch("/api/notifications/unsubscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": csrfToken
        },
        body: JSON.stringify({ userId: currentUser.id, endpoint: subscription.endpoint })
      });

      setIsSubscribed(false);
      setSubscription(null);
    } catch (err) {
      console.error("Failed to unsubscribe", err);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, permission, isSubscribed, subscribe, unsubscribe }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
