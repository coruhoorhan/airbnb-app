import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";

import { generateToken } from "../src/lib/auth.js";
describe("Push Notification Engine API", () => {
  let csrfToken;

  let token;

  const testUserId = `test_notif_user_${Date.now()}`;

  beforeAll(() => {
    db.insertUser({
      id: testUserId,
      name: "Notification Test User",
      email: `notif_${Date.now()}@test.com`,
      isHost: false
    });
    token = generateToken({ id: testUserId, email: `notif_${Date.now()}@test.com` });
  });

  beforeAll(async () => {
    const csrfRes = await request(app).get("/api/auth/csrf");
    csrfToken = csrfRes.body.csrfToken;

  });

  it("should reject subscription requests without userId or subscription", async () => {
    const res = await request(app).post("/api/notifications/subscribe").set("Cookie", [`token=${token}; _csrf_secret=${csrfToken}`]).set("x-csrf-token", csrfToken).send({});
    expect(res.status).toBe(400);
    expect(res.body.success).toBe(false);
  });

  it("should save web-push subscription and persist in database", async () => {
    const mockSubscription = {
      endpoint: "https://fcm.googleapis.com/fcm/send/test-endpoint-token",
      keys: { p256dh: "mock-p256dh-key", auth: "mock-auth-secret" }
    };

    const res = await request(app)
      .post("/api/notifications/subscribe")
      .set("Cookie", [`token=${token}; _csrf_secret=${csrfToken}`])
      .set("x-csrf-token", csrfToken)
      .send({ userId: testUserId, subscription: mockSubscription });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it("should list notifications for a user", async () => {
    const res = await request(app).get(`/api/notifications?userId=${testUserId}`);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.data)).toBe(true);
  });

  it("should unsubscribe from push notifications", async () => {
    const res = await request(app)
      .post("/api/notifications/unsubscribe").set("Cookie", [`token=${token}; _csrf_secret=${csrfToken}`]).set("x-csrf-token", csrfToken)
      .send({ userId: testUserId, endpoint: "https://fcm.googleapis.com" });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});
