import webpush from 'web-push';
import { db } from './db.js';
import crypto from 'crypto';

// Use env vars or fallback to hardcoded (for development/testing)
const publicVapidKey = process.env.VAPID_PUBLIC_KEY || 'BI2Lxat8yhJLCiSk1hG0bIkzgOHrFFkwyKHv-Vfk72u6TF714VmZ5uVO7Ix-HulY5v00MlFizZERuN9YD_tupyw';
const privateVapidKey = process.env.VAPID_PRIVATE_KEY || 'D6bJBNDJGxizrGsCi9KlK5rrxDm8b3Ki1guoLKQ-Ufg';

webpush.setVapidDetails(
  'mailto:support@fatsa.bel.tr',
  publicVapidKey,
  privateVapidKey
);

export function saveSubscription(userId, subscription) {
  const id = crypto.randomUUID();
  const endpoint = subscription.endpoint;
  const keysP = subscription.keys?.p256dh || '';
  const keysAuth = subscription.keys?.auth || '';

  // First delete any existing subscription for this user to avoid duplicates if they reconnect
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);

  db.prepare(`
    INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, userId, endpoint, keysP, keysAuth);

  return id;
}

export function removeSubscription(userId) {
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
}

export async function sendNotification(userId, payload) {
  const subs = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

  if (!subs || subs.length === 0) {
    return;
  }

  const payloadString = JSON.stringify(payload);

  for (const sub of subs) {
    const pushSubscription = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };

    try {
      await webpush.sendNotification(pushSubscription, payloadString);
    } catch (err) {
      if (err.statusCode === 404 || err.statusCode === 410) {
        console.log('Subscription has expired or is no longer valid: ', err);
        db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
      } else {
        console.error('Error sending push notification: ', err);
      }
    }
  }
}
