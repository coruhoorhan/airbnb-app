import { describe, it, expect, vi, beforeEach } from "vitest";
import { saveSubscription, removeSubscription, sendNotification, getPublicKey } from "../src/lib/pushNotificationEngine.js";
import { db } from "../src/lib/db.js";
import webpush from "web-push";

vi.mock("web-push", () => ({
  default: {
    generateVAPIDKeys: vi.fn(() => ({ publicKey: 'test_pub_key', privateKey: 'test_priv_key' })),
    setVapidDetails: vi.fn(),
    sendNotification: vi.fn(() => Promise.resolve())
  }
}));

describe("Push Notification Engine", () => {
  const userId = "test_user_1";
  const subscription = {
    endpoint: "https://fcm.googleapis.com/fcm/send/test_endpoint",
    keys: {
      p256dh: "test_p256dh",
      auth: "test_auth"
    }
  };

  beforeEach(() => {
    // Clear the test user's subscriptions
    db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(userId);
    vi.clearAllMocks();
  });

  it("should return the public key", () => {
    const key = getPublicKey();
    expect(key).toBeDefined();
  });

  it("should save a push subscription successfully", () => {
    const result = saveSubscription(userId, subscription);
    expect(result.success).toBe(true);

    const saved = db.prepare("SELECT * FROM push_subscriptions WHERE endpoint = ?").get(subscription.endpoint);
    expect(saved).toBeDefined();
    expect(saved.userId).toBe(userId);
    expect(saved.keysP).toBe(subscription.keys.p256dh);
    expect(saved.keysAuth).toBe(subscription.keys.auth);
  });

  it("should update an existing push subscription if endpoint is the same", () => {
    saveSubscription(userId, subscription);

    // Attempt to save same endpoint with a different user (e.g. login as another user)
    const newUser = "test_user_2";
    saveSubscription(newUser, subscription);

    const subscriptions = db.prepare("SELECT * FROM push_subscriptions WHERE endpoint = ?").all(subscription.endpoint);
    expect(subscriptions.length).toBe(1);
    expect(subscriptions[0].userId).toBe(newUser);
  });

  it("should remove a push subscription by endpoint", () => {
    saveSubscription(userId, subscription);
    removeSubscription(userId, subscription.endpoint);

    const saved = db.prepare("SELECT * FROM push_subscriptions WHERE endpoint = ?").get(subscription.endpoint);
    expect(saved).toBeUndefined();
  });

  it("should send a notification to the subscribed user", async () => {
    saveSubscription(userId, subscription);

    const payload = { title: "Test Title", body: "Test Body" };
    await sendNotification(userId, payload);

    expect(webpush.sendNotification).toHaveBeenCalledTimes(1);
    expect(webpush.sendNotification).toHaveBeenCalledWith(
      {
        endpoint: subscription.endpoint,
        keys: {
          p256dh: subscription.keys.p256dh,
          auth: subscription.keys.auth
        }
      },
      JSON.stringify(payload)
    );
  });
});
