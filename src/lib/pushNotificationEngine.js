import webpush from 'web-push';
import { db } from './db.js';
import crypto from 'crypto';
import dotenv from 'dotenv';

dotenv.config();

// Default hardcoded email for VAPID contact, or process.env.VAPID_SUBJECT
const subject = process.env.VAPID_SUBJECT || 'mailto:admin@fatsaescapes.com';
const publicKey = process.env.VITE_VAPID_PUBLIC_KEY;
const privateKey = process.env.VAPID_PRIVATE_KEY;

if (publicKey && privateKey) {
  webpush.setVapidDetails(subject, publicKey, privateKey);
} else {
  console.warn('Push Notification VAPID keys not configured. Push functionality will not work.');
}

export function saveSubscription(userId, subscription) {
  const id = crypto.randomUUID();
  const endpoint = subscription.endpoint;
  const keysP = subscription.keys?.p256dh || null;
  const keysAuth = subscription.keys?.auth || null;

  // UPSERT logic: remove old subscription for this userId or endpoint and insert new one
  db.prepare('DELETE FROM push_subscriptions WHERE userId = ? OR endpoint = ?').run(userId, endpoint);

  db.prepare(`
    INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, userId, endpoint, keysP, keysAuth);
}

export function removeSubscription(userId) {
  db.prepare('DELETE FROM push_subscriptions WHERE userId = ?').run(userId);
}

export async function sendNotification(userId, payload) {
  if (!publicKey || !privateKey) return;

  const subscriptions = db.prepare('SELECT * FROM push_subscriptions WHERE userId = ?').all(userId);

  for (const sub of subscriptions) {
    const pushSubscription = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };

    try {
      await webpush.sendNotification(pushSubscription, JSON.stringify(payload));
    } catch (err) {
      if (err.statusCode === 404 || err.statusCode === 410) {
        console.log('Subscription has expired or is no longer valid: ', err);
        db.prepare('DELETE FROM push_subscriptions WHERE id = ?').run(sub.id);
      } else {
        console.error('Error sending push notification: ', err);
      }
    }
  }
}
