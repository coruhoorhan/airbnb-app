import webpush from "web-push";
import { db } from "./db.js";
import crypto from "node:crypto";

const PUBLIC_KEY = process.env.VITE_VAPID_PUBLIC_KEY;
const PRIVATE_KEY = process.env.VAPID_PRIVATE_KEY;

if (PUBLIC_KEY && PRIVATE_KEY) {
  webpush.setVapidDetails(
    "mailto:admin@magda.local",
    PUBLIC_KEY,
    PRIVATE_KEY
  );
} else {
  console.warn("VAPID keys are missing. Web push notifications will not be configured.");
}

export function saveSubscription(userId, subscription) {
  const { endpoint, keys } = subscription;
  const stmt = db.prepare(`
    INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(userId) DO UPDATE SET
      endpoint = excluded.endpoint,
      keysP = excluded.keysP,
      keysAuth = excluded.keysAuth
  `);
  const id = crypto.randomUUID();
  stmt.run(id, userId, endpoint, keys.p256dh, keys.auth);
}

export function removeSubscription(userId) {
  const stmt = db.prepare("DELETE FROM push_subscriptions WHERE userId = ?");
  stmt.run(userId);
}

export async function sendNotification(userId, payload) {
  const stmt = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?");
  const sub = stmt.get(userId);
  if (!sub) return;

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
    console.error("Push notification error:", err);
    if (err.statusCode === 410 || err.statusCode === 404) {
      removeSubscription(userId);
    }
  }
}
