import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";

import { vi } from "vitest";

// Bypass auth and csrf middleware for testing ease
vi.mock('../src/lib/auth.js', () => ({
  authMiddleware: (req, res, next) => {
    req.user = { id: `test_notif_user` }; // Mock logged in user
    next();
  },
  csrfMiddleware: (req, res, next) => next()
}));

describe("Push Notification Engine API", () => {
  const testUserId = `test_notif_user`;

  beforeAll(() => {
    try {
      db.insertUser({
        id: testUserId,
        name: "Notification Test User",
        email: `notif_test@test.com`,
        isHost: false
      });
    } catch(e) {}
  });

  it("should reject subscription requests without userId or subscription", async () => {
    const res = await request(app).post("/api/notifications/subscribe").send({});
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
      .post("/api/notifications/unsubscribe")
      .send({ userId: testUserId, endpoint: "https://fcm.googleapis.com" });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});
