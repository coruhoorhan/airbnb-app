import React, { createContext, useContext, useEffect, useState } from "react";

const PushNotificationContext = createContext();

export function PushNotificationProvider({ children, currentUserId }) {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [swRegistration, setSwRegistration] = useState(null);

  const PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY;

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      navigator.serviceWorker
        .register("/service-worker.js")
        .then((swReg) => {
          setSwRegistration(swReg);
          // Check if already subscribed
          swReg.pushManager.getSubscription().then((subscription) => {
            setIsSubscribed(subscription !== null);
          });
        })
        .catch((error) => {
          console.error("Service Worker Error", error);
        });
    }
  }, []);

  const urlB64ToUint8Array = (base64String) => {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/\-/g, "+")
      .replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  };

  const subscribeUser = async () => {
    try {
      if (!swRegistration) throw new Error("Service worker not registered");

      const applicationServerKey = urlB64ToUint8Array(PUBLIC_KEY);
      const subscription = await swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
      });

      await fetch("/api/notifications/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(subscription)
      });
      setIsSubscribed(true);
    } catch (err) {
      console.error("Failed to subscribe the user: ", err);
    }
  };

  const unsubscribeUser = async () => {
    try {
      if (!swRegistration) throw new Error("Service worker not registered");

      const subscription = await swRegistration.pushManager.getSubscription();
      if (subscription) {
        await subscription.unsubscribe();

        await fetch("/api/notifications/unsubscribe", {
          method: "POST"
        });
      }
      setIsSubscribed(false);
    } catch (err) {
      console.error("Failed to unsubscribe the user: ", err);
    }
  };

  const toggleSubscription = async () => {
    if (isSubscribed) {
      await unsubscribeUser();
    } else {
      await subscribeUser();
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSubscribed, toggleSubscription, isSupported: "serviceWorker" in navigator && "PushManager" in window }}>
      {children}
    </PushNotificationContext.Provider>
  );
}

export function usePushNotification() {
  return useContext(PushNotificationContext);
}
