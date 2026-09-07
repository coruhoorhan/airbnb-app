import webpush from "web-push";
import { db } from "./db.js";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// In a real application, these should be loaded from environment variables (e.g. process.env.VAPID_PUBLIC_KEY).
// Since this is a standalone demo clone that doesn't enforce .env files, we will persist auto-generated keys in a local file.
const keysFilePath = path.join(__dirname, "../../.vapid_keys.json");
let vapidKeys;

if (fs.existsSync(keysFilePath)) {
  vapidKeys = JSON.parse(fs.readFileSync(keysFilePath, "utf8"));
} else {
  vapidKeys = webpush.generateVAPIDKeys();
  fs.writeFileSync(keysFilePath, JSON.stringify(vapidKeys, null, 2), "utf8");
}

const publicVapidKey = vapidKeys.publicKey;
const privateVapidKey = vapidKeys.privateKey;

webpush.setVapidDetails(
  "mailto:test@example.com",
  publicVapidKey,
  privateVapidKey
);

export function saveSubscription(userId, subscription) {
  const existing = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ? AND endpoint = ?").get(userId, subscription.endpoint);

  if (!existing) {
    db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      Date.now().toString() + Math.random().toString(36).substring(7),
      userId,
      subscription.endpoint,
      subscription.keys?.p256dh || null,
      subscription.keys?.auth || null
    );
  }
}

export function removeSubscription(userId) {
  // Using userId alone removes all subscriptions for that user. Could be specific to endpoint.
  db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
}

export async function sendNotification(userId, payload) {
  const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").all(userId);

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
    } catch (error) {
      console.error("[Push Engine] Error sending notification:", error.message);
      if (error.statusCode === 410 || error.statusCode === 404) {
        db.prepare("DELETE FROM push_subscriptions WHERE id = ?").run(sub.id);
      }
    }
  }
}

export { publicVapidKey };
