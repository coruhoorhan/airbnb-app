import webpush from "web-push";
import { db } from "./db.js";
import { randomUUID } from "node:crypto";

const VAPID_SUBJECT = "mailto:admin@airbnbclone.local";
let publicKey = process.env.VAPID_PUBLIC_KEY;
let privateKey = process.env.VAPID_PRIVATE_KEY;

if (!publicKey || !privateKey) {
  try {
    const keys = webpush.generateVAPIDKeys();
    publicKey = keys.publicKey;
    privateKey = keys.privateKey;
  } catch (err) {
    console.error("Failed to generate VAPID keys", err);
  }
}

try {
  webpush.setVapidDetails(VAPID_SUBJECT, publicKey, privateKey);
} catch (e) {
  console.error("Error setting VAPID details:", e);
}

export function saveSubscription(userId, subscription) {
  const { endpoint, keys } = subscription;
  const p256dh = keys && keys.p256dh;
  const auth = keys && keys.auth;

  if (!endpoint) return null;

  const existing = db.prepare("SELECT * FROM push_subscriptions WHERE endpoint = ?").get(endpoint);

  if (existing) {
    db.prepare("UPDATE push_subscriptions SET userId = ?, keysP = ?, keysAuth = ? WHERE endpoint = ?")
      .run(userId, p256dh, auth, endpoint);
  } else {
    db.prepare("INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth) VALUES (?, ?, ?, ?, ?)")
      .run(randomUUID(), userId, endpoint, p256dh, auth);
  }

  return { success: true };
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
  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);
  if (!subscriptions || subscriptions.length === 0) return;

  const payloadString = JSON.stringify(payload);

  const promises = subscriptions.map(async (sub) => {
    const pushSub = {
      endpoint: sub.endpoint,
      keys: {
        p256dh: sub.keysP,
        auth: sub.keysAuth
      }
    };
    try {
      await webpush.sendNotification(pushSub, payloadString);
    } catch (err) {
      if (err.statusCode === 404 || err.statusCode === 410) {
        db.prepare("DELETE FROM push_subscriptions WHERE endpoint = ?").run(sub.endpoint);
      } else {
        console.error("Push Notification error:", err.message);
      }
    }
  });

  await Promise.all(promises);
}

export function getPublicKey() {
  return publicKey;
}
