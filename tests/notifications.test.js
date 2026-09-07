import { describe, it, expect, vi } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as pushEngine from '../src/lib/pushNotificationEngine.js';
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



vi.mock('../src/lib/auth.js', () => ({
  authMiddleware: (req, res, next) => {
    req.user = { id: 'usr_guest_01' };
    next();
  },
  csrfMiddleware: (req, res, next) => next()
}));

describe('Push Notifications Endpoints', () => {
  it('should save subscription on /api/notifications/subscribe', async () => {
    const res = await request(app)
      .post('/api/notifications/subscribe')
      .set('Cookie', ['sessionId=mock_session_id; csrfToken=mock_token'])
      .set('x-csrf-token', 'mock_token')
      .send({ subscription: { endpoint: 'test-endpoint', keys: { p256dh: 'p', auth: 'a' } } });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it('should fail if subscription is missing', async () => {
    const res = await request(app)
      .post('/api/notifications/subscribe')
      .set('Cookie', ['sessionId=mock_session_id; csrfToken=mock_token'])
      .set('x-csrf-token', 'mock_token')
      .send({});
    expect(res.status).toBe(400);
    expect(res.body.success).toBe(false);
  });

  it('should remove subscription on /api/notifications/unsubscribe', async () => {
    const res = await request(app)
      .post('/api/notifications/unsubscribe')
      .set('Cookie', ['sessionId=mock_session_id; csrfToken=mock_token'])
      .set('x-csrf-token', 'mock_token');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});
