import webpush from "web-push";
import { db } from "./db.js";
import { randomUUID } from "node:crypto";

// We generate keys dynamically if not provided. In production, these should be static and set in env vars.
let vapidPublicKey = process.env.VAPID_PUBLIC_KEY || "BMiq0uvC4kyqT6PthKvlLd6fUTb7z00wT_RU7bo79axRetIbco2ORTop1GALoisKllbvKuWDM3ZNarbYScHKNU8";
let vapidPrivateKey = process.env.VAPID_PRIVATE_KEY;
if (!vapidPrivateKey) {
  const keys = webpush.generateVAPIDKeys();
  vapidPrivateKey = keys.privateKey;
  vapidPublicKey = keys.publicKey;
  // Note: We only do this in development/testing. Production should define env vars.
}

webpush.setVapidDetails(
  "mailto:admin@fatsa.bel.tr",
  vapidPublicKey,
  vapidPrivateKey
);

export function saveSubscription(userId, subscription) {
  if (!userId || !subscription || !subscription.endpoint || !subscription.keys) {
    throw new Error("Invalid subscription object or userId");
  }

  // Upsert pattern - check if exists for the user first, or just insert new one
  // One user could have multiple subscriptions (different devices).
  // For simplicity, we could allow multiple, but the prompt says removeSubscription(userId) which implies 1-to-1 or wiping all for a user.
  // We'll insert it if endpoint doesn't exist.

  const existing = db.prepare("SELECT id FROM push_subscriptions WHERE endpoint = ?").get(subscription.endpoint);

  if (existing) {
    db.prepare("UPDATE push_subscriptions SET userId = ?, keysP = ?, keysAuth = ? WHERE id = ?").run(
      userId,
      subscription.keys.p256dh,
      subscription.keys.auth,
      existing.id
    );
  } else {
    db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      `push_${Date.now()}_${randomUUID()}`,
      userId,
      subscription.endpoint,
      subscription.keys.p256dh,
      subscription.keys.auth
    );
  }

  return true;
}

export function removeSubscription(userId) {
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
  return true;
}

export async function sendNotification(userId, payload) {
  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);
  if (subscriptions.length === 0) return;

  const payloadString = typeof payload === "string" ? payload : JSON.stringify(payload);

  for (const sub of subscriptions) {
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
        // Subscription has expired or is no longer valid
        db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
      } else {
        console.error("Error sending push notification:", err);
      }
    }
  }
}
