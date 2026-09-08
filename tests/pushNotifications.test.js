import { describe, it, expect, vi } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as auth from '../src/lib/auth.js';

// Mock auth & csrf middleware to bypass security checks for testing
vi.mock('../src/lib/auth.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    authMiddleware: (req, res, next) => {
      req.user = { id: 'usr_guest_01', isHost: false };
      next();
    },
    csrfMiddleware: (req, res, next) => next()
  };
});

describe('Push Notifications Endpoints', () => {
  it('should successfully save a subscription', async () => {
    const res = await request(app)
      .post('/api/notifications/subscribe')
      .send({
        subscription: {
          endpoint: 'https://fcm.googleapis.com/fcm/send/test-endpoint',
          keys: {
            p256dh: 'test-p256dh',
            auth: 'test-auth'
          }
        }
      });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it('should reject missing subscription object', async () => {
    const res = await request(app)
      .post('/api/notifications/subscribe')
      .send({});

    expect(res.status).toBe(400);
    expect(res.body.success).toBe(false);
  });

  it('should successfully remove a subscription', async () => {
    const res = await request(app)
      .post('/api/notifications/unsubscribe')
      .send({});

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});
