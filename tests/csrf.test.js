import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as db from '../src/lib/db.js';

describe("CSRF Protection", () => {
  let testUserToken;
  let csrfToken;
  let csrfCookie;

  beforeAll(async () => {
    const userId = `test_csrf_user_${Date.now()}`;
    const mockUser = { id: userId, name: 'CSRF User', email: `csrf_${Date.now()}@test.com`, isHost: true };
    db.insertUser(mockUser);

    // Login to get tokens
    const res = await request(app).post('/api/auth/login').send({ email: mockUser.email });
    testUserToken = res.body.token;

    const setCookie = res.headers['set-cookie'];
    if (setCookie) {
        const csrfCookieHeader = setCookie.find(c => c.startsWith('_csrf_secret='));
        if (csrfCookieHeader) {
            csrfCookie = csrfCookieHeader.split(';')[0];
        }
    }
    csrfToken = res.headers['x-csrf-token'];
  });

  it("should reject POST requests without CSRF token", async () => {
    const res = await request(app)
      .post("/api/admin/guardian/scan")
      .set("Cookie", `token=${testUserToken}`)
      .send({});

    expect(res.status).toBe(403);
  });

  it("should reject POST requests with invalid CSRF token", async () => {
    const res = await request(app)
      .post("/api/admin/guardian/scan")
      .set("Cookie", [`token=${testUserToken}`, csrfCookie])
      .set("x-csrf-token", "invalid_token")
      .send({});

    expect(res.status).toBe(403);
  });
});
