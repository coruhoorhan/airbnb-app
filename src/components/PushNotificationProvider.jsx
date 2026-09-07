import React, { createContext, useContext, useEffect, useState } from "react";

const PushNotificationContext = createContext({
  isSubscribed: false,
  toggleSubscription: async () => {}
});

export const usePushNotification = () => useContext(PushNotificationContext);

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

export function PushNotificationProvider({ children }) {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [vapidKey, setVapidKey] = useState(null);

  useEffect(() => {
    fetch("/api/notifications/vapid-key")
      .then(res => res.json())
      .then(data => setVapidKey(data.publicKey))
      .catch(console.error);

    if ("serviceWorker" in navigator && "PushManager" in window) {
      navigator.serviceWorker.register("/service-worker.js").then((registration) => {
        registration.pushManager.getSubscription().then((subscription) => {
          setIsSubscribed(subscription !== null);
        });
      }).catch(console.error);
    }
  }, []);

  const toggleSubscription = async () => {
    if (!("serviceWorker" in navigator && "PushManager" in window)) {
      alert("Push notifications are not supported in this browser.");
      return;
    }

    const registration = await navigator.serviceWorker.ready;

    if (isSubscribed) {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();
        await fetch("/api/notifications/unsubscribe", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("token") || ""}`
          }
        });
      }
      setIsSubscribed(false);
    } else {
      if (Notification.permission !== "granted") {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
          return;
        }
      }

      if (!vapidKey) {
        console.error("VAPID public key not loaded yet");
        return;
      }

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey)
      });

      await fetch("/api/notifications/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token") || ""}`
        },
        body: JSON.stringify({ subscription })
      });

      setIsSubscribed(true);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSubscribed, toggleSubscription }}>
      {children}
    </PushNotificationContext.Provider>
  );
}
