import webpush from 'web-push';
import { db } from './db.js';

// Setup VAPID keys
// Generate a fallback if env variables are not present.
// Note: In production, they must be persistent.
const vapidPublicKey = process.env.VITE_VAPID_PUBLIC_KEY;
const vapidPrivateKey = process.env.VAPID_PRIVATE_KEY;

if (vapidPublicKey && vapidPrivateKey) {
  webpush.setVapidDetails(
  'mailto:admin@fatsa.bel.tr',
  vapidPublicKey,
  vapidPrivateKey
  );
}

export function saveSubscription(userId, subscription) {
  const existing = db.prepare("SELECT id FROM push_subscriptions WHERE userId = ? AND endpoint = ?").get(userId, subscription.endpoint);

  if (existing) {
    db.prepare("UPDATE push_subscriptions SET keysP = ?, keysAuth = ? WHERE id = ?").run(
      subscription.keys.p256dh,
      subscription.keys.auth,
      existing.id
    );
    return;
  }

  const id = 'push_' + Date.now() + Math.random().toString(36).substring(7);
  db.prepare(`
    INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth, createdAt)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    id,
    userId,
    subscription.endpoint,
    subscription.keys.p256dh,
    subscription.keys.auth,
    Date.now()
  );
}

export function removeSubscription(userId) {
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
}

export async function sendNotification(userId, payload) {
  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);
  if (!subscriptions || subscriptions.length === 0) return;

  const pushPayload = JSON.stringify(payload);

  for (const sub of subscriptions) {
    const pushSubscription = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };

    try {
      await webpush.sendNotification(pushSubscription, pushPayload);
    } catch (error) {
      console.error(`Failed to send push notification to user ${userId}:`, error.message);
      if (error.statusCode === 404 || error.statusCode === 410) {
        db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
      }
    }
  }
}
