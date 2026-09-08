import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import * as db from '../src/lib/db.js';

describe("Security - Secure Cookies", () => {
  let uniqueEmail;
  beforeAll(() => {
    uniqueEmail = `sec_cookie_${Date.now()}@test.com`;
    const mockUser = { id: `u_cookie_sec_${Date.now()}`, name: 'Cookie Security', email: uniqueEmail, isHost: true };
    db.insertUser(mockUser);
  });

  it("should return cookies with HttpOnly, Secure, and SameSite=Strict", async () => {
    const res = await request(app).post("/api/auth/login").send({ email: uniqueEmail });
    expect(res.status).toBe(200);
    const cookies = res.headers['set-cookie'];
    expect(cookies).toBeDefined();
    for (const cookie of cookies) {
      if (cookie.includes('token=')) {
        expect(cookie).toContain('HttpOnly');
        expect(cookie).toContain('Secure');
        expect(cookie).toContain('SameSite=Strict');
      }
    }
  });

  it("should clear cookies with secure attributes on logout", async () => {
    // Generate CSRF token for logout
    const csrfRes = await request(app).get('/api/auth/csrf');
    const csrfToken = csrfRes.body.csrfToken;
    const csrfCookie = csrfRes.headers['set-cookie'].find(c => c.startsWith('_csrf_secret='));

    const res = await request(app)
      .post("/api/auth/logout")
      .set("x-csrf-token", csrfToken)
      .set("Cookie", csrfCookie);

    expect(res.status).toBe(200);
    const cookies = res.headers['set-cookie'];
    expect(cookies).toBeDefined();
    for (const cookie of cookies) {
      expect(cookie).toContain('HttpOnly');
      expect(cookie).toContain('Secure');
      expect(cookie).toContain('SameSite=Strict');
    }
  });
});
