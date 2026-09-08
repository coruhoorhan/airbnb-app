import React, { createContext, useState, useEffect, useContext } from 'react';
import { Bell } from 'lucide-react';

const PushNotificationContext = createContext({
  isSubscribed: false,
  toggleSubscription: async () => {},
  isSupported: false
});

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
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      checkSubscription();
    }
  }, []);

  const getCsrfToken = async () => {
    try {
      const res = await fetch('/api/csrf-token');
      const data = await res.json();
      return data.csrfToken;
    } catch (err) {
      console.error('Failed to get CSRF token', err);
      return '';
    }
  };

  const checkSubscription = async () => {
    try {
      const registration = await navigator.serviceWorker.register('/src/service-worker.js');
      const subscription = await registration.pushManager.getSubscription();
      setIsSubscribed(!!subscription);
    } catch (err) {
      console.error('Service Worker registration failed:', err);
    }
  };

  const toggleSubscription = async () => {
    if (!isSupported) return;

    try {
      const registration = await navigator.serviceWorker.ready;
      const csrfToken = await getCsrfToken();

      if (isSubscribed) {
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await subscription.unsubscribe();

          await fetch('/api/notifications/unsubscribe', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'x-csrf-token': csrfToken
            },
            body: JSON.stringify({ endpoint: subscription.endpoint })
          });
        }
        setIsSubscribed(false);
      } else {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          alert('Bildirim izni verilmedi.');
          return;
        }

        const publicVapidKey = 'BI2Lxat8yhJLCiSk1hG0bIkzgOHrFFkwyKHv-Vfk72u6TF714VmZ5uVO7Ix-HulY5v00MlFizZERuN9YD_tupyw'; // Should match backend

        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
        });

        await fetch('/api/notifications/subscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csrf-token': csrfToken
          },
          body: JSON.stringify({ subscription })
        });

        setIsSubscribed(true);
      }
    } catch (err) {
      console.error('Error toggling push subscription:', err);
    }
  };

  return (
    <PushNotificationContext.Provider value={{ isSubscribed, toggleSubscription, isSupported }}>
      {children}
    </PushNotificationContext.Provider>
  );
}

export function PushNotificationToggle() {
  const { isSubscribed, toggleSubscription, isSupported } = useContext(PushNotificationContext);

  if (!isSupported) {
    return null; // Don't show if not supported
  }

  return (
    <button
      onClick={toggleSubscription}
      className="flex items-center gap-1.5 px-3 py-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white transition-colors active:scale-95"
      title={isSubscribed ? "Bildirimleri Kapat" : "Bildirimleri Aç"}
    >
      <Bell className={`w-3.5 h-3.5 ${isSubscribed ? 'text-amber-400' : 'text-charcoal-light dark:text-gray-400'}`} />
    </button>
  );
}
