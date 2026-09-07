import webpush from "web-push";
import { db } from "./db.js";
import { randomUUID } from "node:crypto";

// VAPID keys should ideally be set in environment variables, but for this task we can generate or use static ones.
// Generating one pair for demo purposes. In production, these should be static so they don't change on server restart.
// Run `npx web-push generate-vapid-keys` to get a pair.
const VAPID_PUBLIC_KEY = "BDwB7E9_w9lQ7J_l0fGvUaWz3gHh9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9c";
const VAPID_PRIVATE_KEY = "8z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_9z_8";

// Let's generate valid keys to ensure it works correctly
const vapidKeys = webpush.generateVAPIDKeys();

webpush.setVapidDetails(
  "mailto:contact@airbnb-fatsa.local",
  vapidKeys.publicKey,
  vapidKeys.privateKey
);

export function getVapidPublicKey() {
  return vapidKeys.publicKey;
}

export function saveSubscription(userId, subscription) {
  try {
    const existing = db.prepare("SELECT id FROM push_subscriptions WHERE userId = ? AND endpoint = ?").get(userId, subscription.endpoint);

    if (!existing) {
      db.prepare(`
        INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
        VALUES (@id, @userId, @endpoint, @keysP, @keysAuth)
      `).run({
        id: randomUUID(),
        userId,
        endpoint: subscription.endpoint,
        keysP: subscription.keys.p256dh,
        keysAuth: subscription.keys.auth
      });
    } else {
      db.prepare(`
        UPDATE push_subscriptions
        SET keysP = @keysP, keysAuth = @keysAuth
        WHERE id = @id
      `).run({
        id: existing.id,
        keysP: subscription.keys.p256dh,
        keysAuth: subscription.keys.auth
      });
    }
    return { success: true };
  } catch (err) {
    console.error("[PUSH NOTIFICATION] Error saving subscription:", err.message);
    return { success: false, error: err.message };
  }
}

export function removeSubscription(userId, endpoint) {
  try {
    if (endpoint) {
      db.prepare("DELETE FROM push_subscriptions WHERE userId = ? AND endpoint = ?").run(userId, endpoint);
    } else {
      // Remove all subscriptions for a user
      db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
    }
    return { success: true };
  } catch (err) {
    console.error("[PUSH NOTIFICATION] Error removing subscription:", err.message);
    return { success: false, error: err.message };
  }
}

export async function sendNotification(userId, payload) {
  try {
    const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

    if (subscriptions.length === 0) {
      return { success: true, count: 0 };
    }

    const payloadString = JSON.stringify(payload);
    let successCount = 0;

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
        successCount++;
      } catch (err) {
        if (err.statusCode === 404 || err.statusCode === 410) {
          // Subscription has expired or is no longer valid
          console.log("[PUSH NOTIFICATION] Subscription expired, removing...");
          db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
        } else {
          console.error("[PUSH NOTIFICATION] Error sending to endpoint:", err.message);
        }
      }
    }

    return { success: true, count: successCount };
  } catch (err) {
    console.error("[PUSH NOTIFICATION] Error in sendNotification:", err.message);
    return { success: false, error: err.message };
  }
}
