import webpush from 'web-push';
import { db } from './db.js';
import { randomUUID } from 'crypto';

let keys = null;
import fs from 'fs';
import path from 'path';

try {
  // Try to use environment variables for VAPID keys if provided
  if (process.env.VITE_VAPID_PUBLIC_KEY && process.env.VAPID_PRIVATE_KEY) {
    keys = {
      publicKey: process.env.VITE_VAPID_PUBLIC_KEY,
      privateKey: process.env.VAPID_PRIVATE_KEY,
    };
  } else {
    // Persistent fallback keys to avoid invalidating subscriptions across restarts
    const keyFile = path.resolve(process.cwd(), '.vapid_keys.json');
    if (fs.existsSync(keyFile)) {
      keys = JSON.parse(fs.readFileSync(keyFile, 'utf8'));
    } else {
      keys = webpush.generateVAPIDKeys();
      fs.writeFileSync(keyFile, JSON.stringify(keys));
    }
  }
} catch (e) {
  // If fallback generation fails, keep keys as null and operations will fail later.
}

if (keys) {
  webpush.setVapidDetails(
    'mailto:fatsa-escapes@example.com',
    keys.publicKey,
    keys.privateKey
  );
}

export function saveSubscription(userId, subscription) {
  const id = randomUUID();
  const endpoint = subscription.endpoint;
  const keysP = subscription.keys.p256dh;
  const keysAuth = subscription.keys.auth;

  // Since endpoint can be updated or duplicates might occur, let's remove previous exact endpoints for safety,
  // or just insert. For now we just insert since the task asks for a table with `id`, `userId`, `endpoint`, `keysP`, `keysAuth`.
  // First check if the subscription already exists to avoid duplicates
  const existing = db.prepare("SELECT id FROM push_subscriptions WHERE endpoint = ? AND userId = ?").get(endpoint, userId);

  if (existing) {
     db.prepare("UPDATE push_subscriptions SET keysP = ?, keysAuth = ? WHERE id = ?").run(keysP, keysAuth, existing.id);
     return { id: existing.id, keys };
  } else {
    db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
      VALUES (?, ?, ?, ?, ?)
    `).run(id, userId, endpoint, keysP, keysAuth);
    return { id, keys };
  }
}

export function removeSubscription(userId, endpoint) {
  if (endpoint) {
    db.prepare("DELETE FROM push_subscriptions WHERE userId = ? AND endpoint = ?").run(userId, endpoint);
  } else {
     db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
  }
  return { success: true };
}

export async function sendNotification(userId, payload) {
  if (!keys) return; // Push not configured

  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

  if (subscriptions.length === 0) return;

  const promises = subscriptions.map(sub => {
    const pushSubscription = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };

    return webpush.sendNotification(pushSubscription, JSON.stringify(payload))
      .catch(err => {
        if (err.statusCode === 404 || err.statusCode === 410) {
          // Subscription has expired or is no longer valid
          removeSubscription(userId, sub.endpoint);
        } else {
          console.error("Push notification error:", err);
        }
      });
  });

  await Promise.allSettled(promises);
}

export function getVapidPublicKey() {
  return keys ? keys.publicKey : null;
}
