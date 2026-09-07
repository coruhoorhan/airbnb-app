import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import { generateToken } from "../src/lib/auth.js";

// Mock the CSRF middleware for the test environment
vi.mock("../src/lib/auth.js", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    csrfMiddleware: (req, res, next) => next() // bypass csrf checks in test
  };
});

describe("Push Notification Engine API", () => {
  const token = generateToken({ id: "usr_guest_01", email: "guest@fatsa.bel.tr" });
  const cookieStr = `token=${token}`;

  it("should reject subscription requests without subscription", async () => {
    const res = await request(app)
      .post("/api/notifications/subscribe")
      .set("Cookie", cookieStr)
      .send({});
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
      .set("Cookie", cookieStr)
      .send({ subscription: mockSubscription });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it("should unsubscribe from push notifications", async () => {
    const res = await request(app)
      .post("/api/notifications/unsubscribe")
      .set("Cookie", cookieStr)
      .send();

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});
