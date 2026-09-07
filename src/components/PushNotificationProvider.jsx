import React, { createContext, useContext, useEffect, useState } from "react";

const PushNotificationContext = createContext();

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

export function PushNotificationProvider({ children, currentUserId }) {
  const [isSupported, setIsSupported] = useState(false);
  const [subscription, setSubscription] = useState(null);
  const [permission, setPermission] = useState("default");
  const [vapidKey, setVapidKey] = useState(null);

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
      setPermission(Notification.permission);

      fetch("/api/notifications/vapidPublicKey")
        .then(res => res.json())
        .then(data => {
            if (data.publicKey) {
                setVapidKey(data.publicKey);
            }
        })
        .catch(err => console.error(err));

      navigator.serviceWorker.register("/service-worker.js")
        .then(swReg => {
          return swReg.pushManager.getSubscription();
        })
        .then(sub => {
          setSubscription(sub);
        })
        .catch(err => {
          console.error("Service Worker Error", err);
        });
    }
  }, []);

  const subscribe = async () => {
    if (!isSupported || !vapidKey) return;

    try {
      const swReg = await navigator.serviceWorker.ready;

      const convertedVapidKey = urlBase64ToUint8Array(vapidKey);

      const sub = await swReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey
      });

      setSubscription(sub);
      setPermission(Notification.permission);

      const csrfRes = await fetch("/api/csrf-token");
      const { csrfToken } = await csrfRes.json();

      await fetch("/api/notifications/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": csrfToken
        },
        body: JSON.stringify({ subscription: sub })
      });
    } catch (err) {
      console.error("Failed to subscribe the user: ", err);
    }
  };

  const unsubscribe = async () => {
    if (!isSupported || !subscription) return;

    try {
      await subscription.unsubscribe();
      setSubscription(null);
      setPermission(Notification.permission);

      const csrfRes = await fetch("/api/csrf-token");
      const { csrfToken } = await csrfRes.json();

      await fetch("/api/notifications/unsubscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-csrf-token": csrfToken
        }
      });
    } catch (err) {
      console.error("Error unsubscribing", err);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, permission, subscription, subscribe, unsubscribe }}>
      {children}
    </PushNotificationContext.Provider>
  );
}

export function usePushNotification() {
  return useContext(PushNotificationContext);
}

export function PushNotificationToggle() {
  const { isSupported, permission, subscription, subscribe, unsubscribe } = usePushNotification();

  if (!isSupported) {
    return null;
  }

  const isSubscribed = subscription !== null;

  return (
    <div className="flex items-center gap-3 bg-white dark:bg-charcoal p-3 rounded-lg border border-charcoal-border dark:border-gray-700 shadow-sm">
      <div className="flex-1">
        <h4 className="text-sm font-bold text-charcoal dark:text-white">Anlık Bildirimler</h4>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Yeni mesajlar ve rezervasyon güncellemelerinden haberdar olun.
        </p>
      </div>
      <button
        onClick={isSubscribed ? unsubscribe : subscribe}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
          isSubscribed ? "bg-airbnb" : "bg-gray-300 dark:bg-gray-600"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            isSubscribed ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}
