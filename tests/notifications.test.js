import { describe, it, expect, vi } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import { db } from "../src/lib/db.js";
import { sign } from "jsonwebtoken";

vi.mock("web-push", () => ({
  default: {
    setVapidDetails: vi.fn(),
    sendNotification: vi.fn().mockResolvedValue(true)
  }
}));

describe("Push Notifications API", () => {
  const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-key-do-not-use-in-prod-which-is-at-least-thirty-two-chars";
  const token = sign({ id: "usr_guest_01" }, JWT_SECRET, { expiresIn: "1h" });

  it("should subscribe to push notifications", async () => {
    const res = await request(app)
      .post("/api/notifications/subscribe")
      .set("Authorization", `Bearer ${token}`)
      .send({
        subscription: {
          endpoint: "https://example.com/push",
          keys: { p256dh: "p256", auth: "auth" }
        }
      });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    const sub = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get("usr_guest_01");
    expect(sub).toBeDefined();
    expect(sub.endpoint).toBe("https://example.com/push");
  });

  it("should unsubscribe from push notifications", async () => {
    const res = await request(app)
      .post("/api/notifications/unsubscribe")
      .set("Authorization", `Bearer ${token}`);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    const sub = db.prepare("SELECT * FROM push_subscriptions WHERE userId = ?").get("usr_guest_01");
    expect(sub).toBeUndefined();
  });
});
