import React, { createContext, useContext, useEffect, useState } from 'react';
import { Bell, BellOff } from "lucide-react";

const PushNotificationContext = createContext(null);

export const usePushNotifications = () => {
  return useContext(PushNotificationContext);
};

export function PushNotificationProvider({ children, currentUserId }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [registration, setRegistration] = useState(null);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      registerServiceWorker();
    }
  }, []);

  const registerServiceWorker = async () => {
    try {
      const reg = await navigator.serviceWorker.register('/service-worker.js');
      setRegistration(reg);

      const sub = await reg.pushManager.getSubscription();
      setIsSubscribed(!!sub);
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  };

  const getCsrfToken = () => {
    const match = document.cookie.match(new RegExp('(^| )csrfToken=([^;]+)'));
    return match ? match[2] : null;
  };

  const getToken = () => {
    const match = document.cookie.match(new RegExp('(^| )token=([^;]+)'));
    return match ? match[2] : null;
  };

  const subscribe = async () => {
    if (!registration || !currentUserId) return;

    try {
      const response = await fetch('/api/notifications/vapidPublicKey');
      const vapidPublicKey = await response.text();

      function urlBase64ToUint8Array(base64String) {
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
      }

      const convertedVapidKey = urlBase64ToUint8Array(vapidPublicKey);

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedVapidKey
      });

      await fetch('/api/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'CSRF-Token': getCsrfToken(),
          'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify({
          userId: currentUserId,
          subscription: subscription.toJSON()
        })
      });

      setIsSubscribed(true);
    } catch (error) {
      console.error('Failed to subscribe the user: ', error);
    }
  };

  const unsubscribe = async () => {
    if (!registration || !currentUserId) return;

    try {
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await fetch('/api/notifications/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'CSRF-Token': getCsrfToken(),
            'Authorization': `Bearer ${getToken()}`
          },
          body: JSON.stringify({
            userId: currentUserId,
            endpoint: subscription.endpoint
          })
        });

        await subscription.unsubscribe();
        setIsSubscribed(false);
      }
    } catch (error) {
      console.error('Failed to unsubscribe the user: ', error);
    }
  };

  const toggleSubscription = () => {
    if (isSubscribed) {
      unsubscribe();
    } else {
      subscribe();
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSupported, isSubscribed, toggleSubscription }}>
      {children}
    </PushNotificationContext.Provider>
  );
}

export function PushNotificationToggle() {
  const context = usePushNotifications();
  if (!context || !context.isSupported) return null;

  const { isSubscribed, toggleSubscription } = context;

  return (
    <button
      onClick={toggleSubscription}
      className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center justify-between cursor-pointer"
    >
      <div className="flex items-center gap-2.5">
        {isSubscribed ? <Bell className="w-4 h-4 text-airbnb" /> : <BellOff className="w-4 h-4 text-charcoal-light dark:text-gray-600" />}
        <span>Anlık Bildirimler</span>
      </div>
      <div className={`w-8 h-4 rounded-full transition-colors relative ${isSubscribed ? 'bg-emerald-500' : 'bg-gray-300 dark:bg-gray-600'}`}>
        <div className={`absolute top-0.5 left-0.5 bg-white w-3 h-3 rounded-full transition-transform ${isSubscribed ? 'translate-x-4' : ''}`} />
      </div>
    </button>
  );
}
