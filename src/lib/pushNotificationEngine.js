import webpush from "web-push";
import { db } from "./db.js";
import { randomUUID } from "crypto";

const currentVapidKeys = {
  publicKey: process.env.VAPID_PUBLIC_KEY || "BGp4iYx6EK7Gk_iW7ElBKsn-alL_478-BpNYDXx4G7ImVZP2CMw6Ddyoo8bYmVmyW1t1RjF96bXDg4Cl48qQJzw",
  privateKey: process.env.VAPID_PRIVATE_KEY || "YXwYlIJMCVwAxqqN0IZAjvOvPcUdlJx-6enbTYLHhCY"
};

try {
  webpush.setVapidDetails(
    "mailto:admin@fatsaescapes.com",
    currentVapidKeys.publicKey,
    currentVapidKeys.privateKey
  );
} catch (e) {
  console.error("Failed to set Vapid Details", e);
}

export function saveSubscription(userId, subscription) {
  if (!userId || !subscription || !subscription.endpoint || !subscription.keys) return null;

  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);

  const id = randomUUID();
  db.prepare(`
    INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, userId, subscription.endpoint, subscription.keys.p256dh, subscription.keys.auth);

  return { id, userId };
}

export function removeSubscription(userId) {
  if (!userId) return null;
  const info = db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
  return info.changes > 0;
}

export async function sendNotification(userId, payload) {
  if (!userId || !payload) return;

  const subs = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);
  if (!subs || subs.length === 0) return;

  const promises = subs.map(sub => {
    const pushSubscription = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };

    return webpush.sendNotification(pushSubscription, JSON.stringify(payload))
      .catch(error => {
        if (error.statusCode === 404 || error.statusCode === 410) {
          db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
        }
      });
  });

  await Promise.allSettled(promises);
}

export function getVapidPublicKey() {
  return currentVapidKeys.publicKey;
}
