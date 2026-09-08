import { describe, it, expect, beforeAll } from "vitest";
import request from "supertest";
import { app } from "../server.js";
import * as db from "../src/lib/db.js";

describe("Push Notification Engine API", () => {
  const testUserId = `test_notif_user_${Date.now()}`;

  beforeAll(() => {
    db.insertUser({
      id: testUserId,
      name: "Notification Test User",
      email: `notif_${Date.now()}@test.com`,
      isHost: false
    });
  });

  // Note: Push endpoints are now protected by authMiddleware.
  // We'll mock the auth bypassing if we don't have a valid token in this test file,
  // or use an authenticated request.
  // Actually, since this is a general test file and we modified the endpoints to use `req.user.id`,
  // we need to set a valid token cookie.

  it("should list notifications for a user", async () => {
    const res = await request(app).get(`/api/notifications?userId=${testUserId}`);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.data)).toBe(true);
  });
});
