import webpush from "web-push";
import { db } from "./db.js";

// Ensure VAPID keys exist
const VAPID_SUBJECT = "mailto:admin@airbnbclone.com";
let VAPID_PUBLIC_KEY = process.env.VAPID_PUBLIC_KEY;
let VAPID_PRIVATE_KEY = process.env.VAPID_PRIVATE_KEY;

if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY) {
  const vapidKeys = webpush.generateVAPIDKeys();
  VAPID_PUBLIC_KEY = vapidKeys.publicKey;
  VAPID_PRIVATE_KEY = vapidKeys.privateKey;
  console.log("[PushEngine] Generated VAPID Keys for development:");
  console.log("Public:", VAPID_PUBLIC_KEY);
  console.log("Private:", VAPID_PRIVATE_KEY);
}

webpush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

export function getVapidPublicKey() {
  return VAPID_PUBLIC_KEY;
}

export function saveSubscription(userId, subscription) {
  const { endpoint, keys } = subscription;
  const existing = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ? AND endpoint = ?").get(userId, endpoint);

  if (!existing) {
    db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
      VALUES (@id, @userId, @endpoint, @keysP, @keysAuth)
    `).run({
      id: `push_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      userId,
      endpoint,
      keysP: keys.p256dh,
      keysAuth: keys.auth
    });
  }
}

export function removeSubscription(userId) {
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
}

export async function sendNotification(userId, payload) {
  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

  const payloadString = JSON.stringify(payload);

  for (const sub of subscriptions) {
    try {
      await webpush.sendNotification({
        endpoint: sub.endpoint,
        keys: {
          p256dh: sub.keysP,
          auth: sub.keysAuth
        }
      }, payloadString);
    } catch (error) {
      if (error.statusCode === 410 || error.statusCode === 404) {
        db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
      } else {
        console.error("[PushEngine] Error sending notification:", error);
      }
    }
  }
}
