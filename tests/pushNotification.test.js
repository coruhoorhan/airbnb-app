import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import { db } from "../src/lib/db.js";

// Ensure mock vapid keys
process.env.VAPID_PUBLIC_KEY = "test_public";
process.env.VAPID_PRIVATE_KEY = "test_private";

describe("Push Notification Engine", () => {
  const testUserId = "usr_guest_01";
  const mockSubscription = {
    endpoint: "https://fcm.googleapis.com/fcm/send/test-endpoint",
    keys: {
      p256dh: "test-p256dh",
      auth: "test-auth"
    }
  };

  afterAll(() => {
    db.prepare("DELETE FROM push_subscriptions WHERE userId = ?").run(testUserId);
  });

  it("should get vapid public key", async () => {
    const res = await request(app).get("/api/notifications/vapid-key");
    expect(res.status).toBe(200);
    expect(res.body.publicKey).toBeDefined();
  });
});
