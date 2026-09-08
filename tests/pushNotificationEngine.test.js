import { describe, it, expect, beforeEach, vi } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { db } from '../src/lib/db.js';

// Mock Web Push
vi.mock('web-push', () => ({
  default: {
    generateVAPIDKeys: () => ({
      publicKey: 'mock-public-key',
      privateKey: 'mock-private-key'
    }),
    setVapidDetails: vi.fn(),
    sendNotification: vi.fn().mockResolvedValue({})
  }
}));

// Bypass auth and csrf middleware for testing ease
vi.mock('../src/lib/auth.js', () => ({
  authMiddleware: (req, res, next) => {
    req.user = { id: 'usr_guest_01' }; // Mock logged in user
    next();
  },
  csrfMiddleware: (req, res, next) => next()
}));

describe('Push Notifications API', () => {
  beforeEach(() => {
    db.prepare('DELETE FROM push_subscriptions').run();
  });

  it('should save a valid push subscription', async () => {
    const payload = {
      userId: 'usr_guest_01',
      subscription: {
        endpoint: 'https://fcm.googleapis.com/fcm/send/fake-endpoint-123',
        keys: {
          p256dh: 'fake-p256dh-key',
          auth: 'fake-auth-key'
        }
      }
    };

    const res = await request(app)
      .post('/api/notifications/subscribe')
      .send(payload);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);

    const saved = db.prepare('SELECT * FROM push_subscriptions WHERE userId = ?').all('usr_guest_01');
    expect(saved.length).toBe(1);
    expect(saved[0].endpoint).toBe(payload.subscription.endpoint);
    expect(saved[0].keysP).toBe(payload.subscription.keys.p256dh);
    expect(saved[0].keysAuth).toBe(payload.subscription.keys.auth);
  });

  it('should remove a push subscription', async () => {
    // Insert dummy sub
    db.prepare(`
      INSERT INTO push_subscriptions (id, userId, endpoint, keysP, keysAuth)
      VALUES (?, ?, ?, ?, ?)
    `).run('sub_1', 'usr_guest_01', 'fake-endpoint', 'p-key', 'auth-key');

    const res = await request(app)
      .post('/api/notifications/unsubscribe')
      .send({
        userId: 'usr_guest_01',
        endpoint: 'fake-endpoint'
      });

    expect(res.status).toBe(200);

    const saved = db.prepare('SELECT * FROM push_subscriptions WHERE userId = ?').all('usr_guest_01');
    expect(saved.length).toBe(0);
  });

});
