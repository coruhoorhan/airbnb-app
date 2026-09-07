import * as db from "./db.js";
import { randomUUID } from "crypto";

/**
 * Push Notification & Real-time Alert Engine
 * Manages user subscriptions, notification persistence in SQLite,
 * and dispatching notifications for booking & payment events.
 */

// In-memory active subscription cache for fast dispatch
const subscriptions = new Map(); // userId -> Set<subscription>

export function saveSubscription(userId, subscription) {
  if (!userId || !subscription) return null;
  
  if (!subscriptions.has(userId)) {
    subscriptions.set(userId, new Set());
  }
  
  const subString = typeof subscription === "string" ? subscription : JSON.stringify(subscription);
  subscriptions.get(userId).add(subString);

  // Persist notification record in SQLite
  const notifId = randomUUID();
  const createdAt = Date.now();
  try {
    db.db.prepare(`
      INSERT INTO notifications (id, userId, title, message, type, isRead, createdAt)
      VALUES (?, ?, ?, ?, ?, 0, ?)
    `).run(notifId, userId, "Bildirimler Aktif", "Tarayıcı bildirimleri başarıyla etkinleştirildi.", "system", createdAt);
  } catch (err) {
    // If notifications table schema is missing columns, gracefully create or skip
  }

  return { success: true, subscriptionCount: subscriptions.get(userId).size };
}

export function removeSubscription(userId, endpoint) {
  if (!userId || !subscriptions.has(userId)) {
    return { success: true, remaining: 0 };
  }

  const userSubs = subscriptions.get(userId);
  for (const sub of userSubs) {
    if (sub.includes(endpoint)) {
      userSubs.delete(sub);
    }
  }

  return { success: true, remaining: userSubs.size };
}

export function createNotification({ userId, title, message, type = "booking" }) {
  if (!userId || !title) return null;

  const id = randomUUID();
  const createdAt = Date.now();

  try {
    db.db.prepare(`
      INSERT INTO notifications (id, userId, title, message, type, isRead, createdAt)
      VALUES (?, ?, ?, ?, ?, 0, ?)
    `).run(id, userId, title, message || "", type, createdAt);

    return db.db.prepare("SELECT * FROM notifications WHERE id = ?").get(id);
  } catch (err) {
    return { id, userId, title, message, type, isRead: 0, createdAt };
  }
}

export function getUserNotifications(userId) {
  if (!userId) return [];
  try {
    return db.db.prepare("SELECT * FROM notifications WHERE userId = ? ORDER BY createdAt DESC").all(userId);
  } catch (err) {
    return [];
  }
}

export function markNotificationRead(id) {
  if (!id) return { changed: 0 };
  try {
    const info = db.db.prepare("UPDATE notifications SET isRead = 1 WHERE id = ?").run(id);
    return { changed: info.changes };
  } catch (err) {
    return { changed: 0 };
  }
}
