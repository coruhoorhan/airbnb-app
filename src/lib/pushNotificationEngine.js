import webpush from "web-push";
import { db } from "./db.js";
import { randomUUID } from "crypto";

// VAPID keys should be read from environment variables.
const VAPID_PUBLIC_KEY = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIVATE_KEY = process.env.VAPID_PRIVATE_KEY;

if (VAPID_PUBLIC_KEY && VAPID_PRIVATE_KEY) {
  webpush.setVapidDetails(
    "mailto:contact@fatsa.bel.tr",
    VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_KEY
  );
} else {
  console.warn("[PUSH ENGINE] VAPID keys missing. Push notifications will not be sent.");
}

export function getVapidPublicKey() {
  return VAPID_PUBLIC_KEY;
}

export function saveSubscription(userId, subscription) {
  if (!userId || !subscription) return null;

  try {
    const existing = db.prepare("SELECT id FROM push_subscriptions WHERE endpoint = ?").get(subscription.endpoint);

    if (existing) {
      db.prepare(`
        UPDATE push_subscriptions SET userId = ?, keysP = ?, keysAuth = ? WHERE endpoint = ?
      `).run(userId, subscription.keys.p256dh, subscription.keys.auth, subscription.endpoint);
    } else {
      const id = randomUUID();
      db.prepare(`
        INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
        VALUES (?, ?, ?, ?, ?)
      `).run(id, userId, subscription.endpoint, subscription.keys.p256dh, subscription.keys.auth);
    }
    return { success: true };
  } catch (err) {
    console.error("[PUSH ENGINE] saveSubscription error:", err.message);
    return { success: false, error: err.message };
  }
}

export function removeSubscription(userId, endpoint) {
  if (!userId || !endpoint) return null;

  try {
    const info = db.prepare("DELETE FROM push_subscriptions WHERE userId = ? AND endpoint = ?").run(userId, endpoint);
    return { success: true, removed: info.changes };
  } catch (err) {
    console.error("[PUSH ENGINE] removeSubscription error:", err.message);
    return { success: false, error: err.message };
  }
}

export async function sendNotification(userId, payload) {
  if (!userId || !payload) return;

  try {
    const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

    if (!subscriptions || subscriptions.length === 0) return { success: false, reason: "No active subscriptions for user" };

    const payloadString = JSON.stringify(payload);
    const results = await Promise.allSettled(
      subscriptions.map(async (sub) => {
        const pushSubscription = {
          endpoint: sub.endpoint,
          keys: {
            p256dh: sub.keysP,
            auth: sub.keysAuth
          }
        };

        try {
          await webpush.sendNotification(pushSubscription, payloadString);
        } catch (error) {
          if (error.statusCode === 404 || error.statusCode === 410) {
            // Subscription has expired or is no longer valid
            db.prepare("DELETE FROM push_subscriptions WHERE endpoint = ?").run(sub.endpoint);
          } else {
            throw error;
          }
        }
      })
    );

    const failures = results.filter((r) => r.status === "rejected");
    if (failures.length > 0) {
      console.error("[PUSH ENGINE] Some notifications failed:", failures);
    }

    return { success: true, sent: results.length - failures.length };
  } catch (err) {
    console.error("[PUSH ENGINE] sendNotification error:", err.message);
    return { success: false, error: err.message };
  }
}
