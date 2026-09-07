import webpush from "web-push";
import { randomUUID } from "crypto";
import * as db from "./db.js";

// Ensure VAPID keys exist, generate if not
const vapidKeys = webpush.generateVAPIDKeys();
webpush.setVapidDetails(
  "mailto:admin@fatsa.bel.tr",
  vapidKeys.publicKey,
  vapidKeys.privateKey
);

export function getVapidPublicKey() {
  return vapidKeys.publicKey;
}

export function saveSubscription(userId, subscription) {
  if (!userId || !subscription || !subscription.endpoint) {
    return { success: false, error: "Invalid subscription details" };
  }

  const id = randomUUID();
  const keysP = subscription.keys?.p256dh || null;
  const keysAuth = subscription.keys?.auth || null;
  const createdAt = Date.now();

  try {
    // Basic upsert based on endpoint (in SQLite you can use REPLACE if there's a UNIQUE constraint,
    // but we can just delete the old one for this user/endpoint and insert)
    db.db.prepare("DELETE FROM push_subscriptions WHERE userId = ? AND endpoint = ?").run(userId, subscription.endpoint);

    db.db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth, createdAt)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(id, userId, subscription.endpoint, keysP, keysAuth, createdAt);
    return { success: true };
  } catch (err) {
    console.error("[Push] Error saving subscription:", err);
    return { success: false, error: err.message };
  }
}

export function removeSubscription(userId, endpoint) {
  if (!userId || !endpoint) {
    return { success: false, error: "Missing userId or endpoint" };
  }

  try {
    const info = db.db.prepare("DELETE FROM push_subscriptions WHERE userId = ? AND endpoint = ?").run(userId, endpoint);
    return { success: true, deleted: info.changes };
  } catch (err) {
    console.error("[Push] Error removing subscription:", err);
    return { success: false, error: err.message };
  }
}

export async function sendNotification(userId, payload) {
  if (!userId || !payload) return;

  try {
    const subs = db.db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);
    if (!subs || subs.length === 0) return;

    const pushPayload = JSON.stringify(payload);
    const promises = subs.map(async (sub) => {
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
        if (error.statusCode === 404 || error.statusCode === 410) {
          // Subscription has expired or is no longer valid
          removeSubscription(userId, sub.endpoint);
        } else {
          console.error("[Push] Error sending notification:", error);
        }
      }
    });

    await Promise.all(promises);
  } catch (err) {
    console.error("[Push] Error in sendNotification:", err);
  }
}
