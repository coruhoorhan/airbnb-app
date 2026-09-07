import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";
import { generateToken, generateCsrfToken } from "../src/lib/auth.js";

describe("Web Push Notification Engine Integration", () => {
  const testUserId = `test_push_user_${Date.now()}`;
  let vapidKey = "";
  let csrfToken = "";

  beforeAll(() => {
    db.insertUser({
      id: testUserId,
      name: "Push Notification Tester",
      email: `push_${Date.now()}@test.com`,
      isHost: false
    });
    csrfToken = generateCsrfToken();
  });

  afterAll(() => {
    db.db.prepare("DELETE FROM users WHERE id = ?").run(testUserId);
  });

  it("should expose the public VAPID key", async () => {
    const res = await request(app).get("/api/notifications/vapid-key");
    expect(res.status).toBe(200);
    expect(res.body.publicVapidKey).toBeDefined();
    expect(typeof res.body.publicVapidKey).toBe("string");
    vapidKey = res.body.publicVapidKey;
  });

  it("should allow a user to subscribe to push notifications", async () => {
    const mockSubscription = {
      endpoint: "https://fcm.googleapis.com/fcm/send/push-test-token",
      keys: { p256dh: "mock-p256dh-key", auth: "mock-auth-secret" }
    };

    const userToken = generateToken(testUserId);
    const res = await request(app)
      .post("/api/notifications/subscribe")
      .set("Cookie", [`token=${userToken}`])
      .send({ userId: testUserId, subscription: mockSubscription });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);

    const sub = db.db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get(testUserId);
    expect(sub).toBeDefined();
    expect(sub.endpoint).toBe("https://fcm.googleapis.com/fcm/send/push-test-token");
  });

  it("should allow a user to unsubscribe from push notifications", async () => {
    const userToken = generateToken(testUserId);
    const res = await request(app)
      .post("/api/notifications/unsubscribe")
      .set("Cookie", [`token=${userToken}`])
      .send({ userId: testUserId });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);

    const sub = db.db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get(testUserId);
    expect(sub).toBeUndefined();
  });
});
